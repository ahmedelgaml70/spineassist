"""Validated glenohumeral teaching renderer using genuine meshes from the complete body.glb.

The animation is intentionally simplified to isolated GH motion: scapula and clavicle are fixed.
The camera is fitted to the complete neutral-to-terminal excursion so neither flexion nor abduction
can leave the teaching frame. GH seating is independently audited throughout the motion.
"""
import importlib.util, json, math
from pathlib import Path
from mathutils import Matrix, Vector
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('anatomy_render_base', HERE/'render_motion_blender.py')
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
qa={'duplicates':[],'parenting':[],'pivot_radius':[],'gh_contact':[],'head_center':[]}
def smooth(o):
    for p in o.data.polygons: p.use_smooth=True
def duplicate_world_baked(o,name):
    base.bpy.context.view_layer.update(); before=base.center(o); world=o.matrix_world.copy()
    q=o.copy(); q.data=o.data.copy(); q.name=name; base.bpy.context.collection.objects.link(q)
    q.parent=None; q.data.transform(world); q.data.update(); q.matrix_world=Matrix.Identity(4); smooth(q)
    base.bpy.context.view_layer.update(); shift=(base.center(q)-before).length
    qa['duplicates'].append({'object':name,'shift':shift})
    if shift>1e-5: raise RuntimeError(f'World-baked duplicate shifted by {shift}')
    return q
def parent_preserve(o,parent):
    base.bpy.context.view_layer.update(); before=base.center(o); o.parent=parent; o.matrix_parent_inverse=parent.matrix_world.inverted()
    base.bpy.context.view_layer.update(); shift=(base.center(o)-before).length; qa['parenting'].append({'object':o.name,'shift':shift})
    if shift>1e-5: raise RuntimeError(f'Parenting displaced {o.name} by {shift}')
def proximal_head_center(h, scapula):
    hv=base.verts(h,12000); sv=base.verts(scapula,12000)
    if not hv or not sv: raise RuntimeError('Missing vertices for humeral-head pivot estimation')
    hp,sp,_=base.closest(h,scapula,2500)
    radius=max(base.extent(h)*.11, .01)
    local=[p for p in hv if (p-hp).length <= radius]
    if len(local)<20: local=sorted(hv,key=lambda p:(p-hp).length)[:max(20,min(300,len(hv)))]
    mn=Vector((min(p.x for p in local),min(p.y for p in local),min(p.z for p in local)))
    mx=Vector((max(p.x for p in local),max(p.y for p in local),max(p.z for p in local)))
    return (mn+mx)/2, hp, sp, len(local)
def clean_setup():
    s=base.bpy.context.scene; s.frame_start=1; s.frame_end=72; s.render.fps=24; s.render.resolution_x=1440; s.render.resolution_y=900; s.render.resolution_percentage=100
    s.render.film_transparent=False; s.world=s.world or base.bpy.data.worlds.new('World'); s.world.color=(.035,.035,.035)
    for engine in ('BLENDER_EEVEE_NEXT','BLENDER_EEVEE'):
        try: s.render.engine=engine; break
        except Exception: pass
    base.bpy.ops.object.light_add(type='AREA',location=(0,-3.5,5)); base.bpy.context.object.data.energy=850; base.bpy.context.object.data.size=5
    base.bpy.ops.object.light_add(type='AREA',location=(3.5,2.5,4)); base.bpy.context.object.data.energy=280; base.bpy.context.object.data.size=5
def clean_render(name,h,s,c,j_unused,mode):
    q=duplicate_world_baked(h,name+'_moving_humerus'); smooth(s); smooth(c)
    base.material(q,'Moving_Humerus',(0.92,.22,.10,1)); base.material(s,'Static_Shoulder',(.90,.82,.64,1)); base.material(c,'Static_Shoulder',(.90,.82,.64,1))
    j,hp,sp,nlocal=proximal_head_center(q,s)
    e=base.bpy.data.objects.new(name+'_pivot',None); base.bpy.context.collection.objects.link(e); e.location=j; parent_preserve(q,e)
    rot=(math.radians(72),0,0) if mode=='flexion' else (0,math.radians(-72),0)
    for f,r in ((1,(0,0,0)),(60,rot),(72,rot)):
        base.bpy.context.scene.frame_set(f); e.rotation_euler=r; e.keyframe_insert(data_path='rotation_euler',frame=f)
    if e.animation_data and e.animation_data.action:
        for fc in e.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation='LINEAR'
    base.hide_except([q,s,c]); sc=base.bpy.context.scene
    # Fit the camera to the union of neutral and terminal poses, not merely the neutral pose.
    sc.frame_set(1); mn0,mx0=base.bounds([q,s,c]); r0=sorted((p-j).length for p in base.verts(q,700)); _,_,d0=base.closest(q,s,1200); hc0=j.copy()
    sc.frame_set(60); mn1,mx1=base.bounds([q,s,c]); r1=sorted((p-j).length for p in base.verts(q,700)); _,_,d1=base.closest(q,s,1200); hc1=e.matrix_world @ Vector((0,0,0))
    mn=Vector((min(mn0.x,mn1.x),min(mn0.y,mn1.y),min(mn0.z,mn1.z)))
    mx=Vector((max(mx0.x,mx1.x),max(mx0.y,mx1.y),max(mx0.z,mx1.z)))
    span=mx-mn; size=max(span.x,span.y,span.z); focus=(mn+mx)/2
    direction=Vector((1,0,0.03)).normalized() if mode=='flexion' else Vector((0,-1,0.03)).normalized()
    base.bpy.ops.object.camera_add(location=focus+direction*size*2.5); cam=base.bpy.context.object; cam.data.type='ORTHO'; cam.data.ortho_scale=size*1.28; base.look(cam,focus); base.bpy.context.scene.camera=cam
    radial=max((abs(a-b) for a,b in zip(r0,r1)),default=0.0); drift=abs(d1-d0); head_shift=(hc1-hc0).length
    limit=max(.004,base.extent(h)*.025)
    qa['pivot_radius'].append({'clip':name,'error':radial}); qa['gh_contact'].append({'clip':name,'start':d0,'end':d1,'drift':drift,'limit':limit}); qa['head_center'].append({'clip':name,'translation':head_shift,'local_vertices':nlocal,'pivot':[j.x,j.y,j.z]})
    print(f'CLEAN_RENDER_ACTIVE {name} head_shift={head_shift:.9f} radial={radial:.9f} contact_start={d0:.6f} contact_end={d1:.6f} drift={drift:.6f} limit={limit:.6f}')
    if radial>1e-4 or head_shift>1e-5 or drift>limit: raise RuntimeError(f'GH seating QA failed for {name}')
    sc.frame_set(60); sc.render.image_settings.file_format='PNG'; sc.render.filepath=str(base.OUT/f'{name}_poster.png'); base.bpy.ops.render.render(write_still=True)
    sc.frame_set(1); sc.render.image_settings.file_format='FFMPEG'; sc.render.ffmpeg.format='MPEG4'; sc.render.ffmpeg.codec='H264'; sc.render.ffmpeg.constant_rate_factor='MEDIUM'; sc.render.ffmpeg.ffmpeg_preset='REALTIME'; sc.render.filepath=str(base.OUT/f'{name}.mp4'); base.bpy.ops.render.render(animation=True)
    for o in (q,e,cam):
        if o.name in base.bpy.data.objects: base.bpy.data.objects.remove(o,do_unlink=True)
base.setup=clean_setup; base.render=clean_render; base.main()
p=base.OUT/'model_manifest.json'; m=json.loads(p.read_text()); max_dup=max((x['shift'] for x in qa['duplicates']),default=0); max_par=max((x['shift'] for x in qa['parenting']),default=0); max_rad=max((x['error'] for x in qa['pivot_radius']),default=0); max_ratio=max((x['drift']/x['limit'] for x in qa['gh_contact']),default=0); max_head=max((x['translation'] for x in qa['head_center']),default=0)
passed=max_dup<=1e-5 and max_par<=1e-5 and max_rad<=1e-4 and max_ratio<=1 and max_head<=1e-5 and len(qa['gh_contact'])==2
m['pipeline_qa']={'fix_version':'full-excursion-framing-v10','hierarchy_contact_preserved':passed,'clean_renderer_executed':len(qa['gh_contact'])==2,'decorative_arc_created':False,'max_source_to_baked_center_shift':max_dup,'max_parenting_world_center_shift':max_par,'max_pivot_radius_error':max_rad,'max_gh_contact_drift_ratio':max_ratio,'max_humeral_head_center_translation':max_head,'events':qa,'motion_geometry':'world-baked humerus rotated about locally estimated humeral-head centre','teaching_scope':'isolated glenohumeral motion; scapula and clavicle deliberately fixed','temporal_rule':'neutral to named terminal pose, then hold; no antagonist return','poster_rule':'terminal movement pose','camera_rule':'orthographic teaching view fitted to union of neutral and terminal shoulder-complex bounds','visual_cue':'moving humerus only; no decorative 3D arc'}
m['selection_debug']['visible_rule']='only matched scapula, clavicle, and moving humerus; imported source humerus hidden'; m['selection_debug']['corrective_change']='v10 preserves the seated-head motion from v9 but fits each orthographic camera to the complete neutral-to-terminal excursion with teaching-view padding so the moving humerus cannot leave the frame.'
p.write_text(json.dumps(m,indent=2))
if not passed: raise RuntimeError('Clean renderer GH seating QA failed')
