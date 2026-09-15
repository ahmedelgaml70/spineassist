"""Render a strict shoulder teaching pilot from the complete anatomy GLB.

Quality rule: never show unrelated nearby meshes. Select the humerus/scapula pair by
actual mesh proximity, attach the closest clavicle, validate that the chosen bones form
a compact shoulder complex, then render only those three bones. The original humerus
is hidden and a duplicate rotates about an estimated humeral-head centre.
"""
import bpy, math, json, re
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]; ASSET=ROOT/'assets'/'body.glb'; OUT=ROOT/'outputs'; OUT.mkdir(exist_ok=True)
BG=(0.955,0.945,0.925); STATIC=(0.90,0.82,0.64,1); MOVING=(0.92,0.22,0.10,1); ARC=(0.05,0.30,0.82,1)
BAD=['muscle','artery','vein','nerve','ligament','tendon','skin','cartilage','deltoid','pectoralis','trapezius','latissimus']

def clean():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()

def norm(o):
    s=o.name.lower(); s=re.sub(r'\.\d+$','',s); s=re.sub(r'[_\-]+',' ',s); return re.sub(r'\s+',' ',s).strip()

def bones(objs,t): return [o for o in objs if t in norm(o) and not any(x in norm(o) for x in BAD)]
def center(o):
    p=[o.matrix_world@Vector(c) for c in o.bound_box]; return (Vector((min(v.x for v in p),min(v.y for v in p),min(v.z for v in p)))+Vector((max(v.x for v in p),max(v.y for v in p),max(v.z for v in p))))/2
def extent(o):
    p=[o.matrix_world@Vector(c) for c in o.bound_box]; mn=Vector((min(v.x for v in p),min(v.y for v in p),min(v.z for v in p))); mx=Vector((max(v.x for v in p),max(v.y for v in p),max(v.z for v in p))); return max(mx-mn)
def verts(o,n=900):
    step=max(1,len(o.data.vertices)//n); return [o.matrix_world@v.co for i,v in enumerate(o.data.vertices) if i%step==0] or [center(o)]
def closest(a,b):
    A=verts(a); B=verts(b); best=(None,None,1e9)
    for x in A:
        for y in B:
            d=(x-y).length_squared
            if d<best[2]: best=(x,y,d)
    return best[0],best[1],math.sqrt(best[2])

def choose(objs):
    H,S,C=bones(objs,'humerus'),bones(objs,'scapula'),bones(objs,'clavicle')
    if not H or not S or not C: raise RuntimeError('Missing humerus/scapula/clavicle meshes')
    candidates=[]
    for h in H:
        for s in S:
            hp,sp,d=closest(h,s); candidates.append((d,h,s,hp,sp))
    d,h,s,hp,sp=min(candidates,key=lambda q:q[0])
    c=min(C,key=lambda x:closest(x,s)[2])
    dc=closest(c,s)[2]
    if d>0.08 or dc>0.12: raise RuntimeError(f'Chosen shoulder is not contiguous: humerus-scapula={d:.4f}, clavicle-scapula={dc:.4f}')
    return h,s,c,hp,sp,d,dc

def head_center(h,sp):
    P=sorted(verts(h,2600),key=lambda p:(p-sp).length_squared); k=max(30,min(120,len(P)//14)); q=Vector((0,0,0))
    for p in P[:k]: q+=p
    return q/k

def mat(o,name,color):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name); m.diffuse_color=color; m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=color; bs.inputs['Roughness'].default_value=.48
    o.data.materials.clear(); o.data.materials.append(m)
def visible(keep):
    K=set(keep)
    for o in bpy.context.scene.objects:
        if o.type in {'MESH','CURVE'}: o.hide_render=o not in K; o.hide_viewport=o not in K

def dup(o,name):
    q=o.copy(); q.data=o.data.copy(); q.name=name; bpy.context.collection.objects.link(q); q.matrix_world=o.matrix_world.copy(); return q

def empty(name,p):
    e=bpy.data.objects.new(name,None); bpy.context.collection.objects.link(e); e.location=p; return e

def parent(o,e): o.parent=e; o.matrix_parent_inverse=e.matrix_world.inverted()
def look(cam,t): cam.rotation_euler=(Vector(t)-cam.location).to_track_quat('-Z','Y').to_euler()
def bounds(O):
    P=[o.matrix_world@Vector(c) for o in O for c in o.bound_box]; mn=Vector((min(p.x for p in P),min(p.y for p in P),min(p.z for p in P))); mx=Vector((max(p.x for p in P),max(p.y for p in P),max(p.z for p in P))); return mn,mx

def setup():
    s=bpy.context.scene; s.frame_start=1; s.frame_end=72; s.render.fps=24; s.render.resolution_x=1440; s.render.resolution_y=900; s.world.color=BG
    bpy.ops.object.light_add(type='AREA',location=(0,-3,4)); bpy.context.object.data.energy=900; bpy.context.object.data.size=5
    bpy.ops.object.light_add(type='AREA',location=(3,2,3)); bpy.context.object.data.energy=350; bpy.context.object.data.size=4

def arc(name,j,r,mode):
    cv=bpy.data.curves.new(name,'CURVE'); cv.dimensions='3D'; cv.bevel_depth=r*.012; cv.bevel_resolution=3
    sp=cv.splines.new('POLY'); sp.points.add(47)
    for i,p in enumerate(sp.points):
        a=math.radians(5+80*i/47)
        if mode=='flexion': co=(j.x,j.y+r*math.sin(a),j.z-r*math.cos(a),1)
        else: co=(j.x+r*math.sin(a),j.y,j.z-r*math.cos(a),1)
        p.co=co
    o=bpy.data.objects.new(name,cv); bpy.context.collection.objects.link(o); m=bpy.data.materials.get('MotionArc') or bpy.data.materials.new('MotionArc'); m.diffuse_color=ARC; cv.materials.append(m); return o

def camera(O,j,mode):
    bpy.context.view_layer.update(); mn,mx=bounds(O); e=max(mx-mn); focus=j*.65+((mn+mx)/2)*.35
    direction=Vector((1,-.12,.05)).normalized() if mode=='flexion' else Vector((.04,-1,.05)).normalized()
    bpy.ops.object.camera_add(location=focus+direction*e*3.0); c=bpy.context.object; c.data.type='ORTHO'; c.data.ortho_scale=e*1.22; look(c,focus); bpy.context.scene.camera=c

def key(e,f,rot): bpy.context.scene.frame_set(f); e.rotation_euler=rot; e.keyframe_insert(data_path='rotation_euler',frame=f)
def render(name,h,s,c,j,mode):
    q=dup(h,name+'_humerus'); mat(q,'MovingHumerus',MOVING); mat(s,'StaticShoulder',STATIC); mat(c,'StaticShoulder',STATIC)
    e=empty(name+'_pivot',j); parent(q,e)
    # Model uses Z as superior-inferior; flexion rotates about mediolateral X, abduction about AP Y.
    rot=(math.radians(82),0,0) if mode=='flexion' else (0,math.radians(-82),0)
    key(e,1,(0,0,0)); key(e,36,rot); key(e,72,(0,0,0))
    a=arc(name+'_arc',j,extent(h)*.66,mode); visible([q,s,c,a]); camera([q,s,c],j,mode)
    sc=bpy.context.scene; sc.frame_set(36); sc.render.image_settings.file_format='PNG'; sc.render.filepath=str(OUT/f'{name}_poster.png'); bpy.ops.render.render(write_still=True)
    sc.render.image_settings.file_format='FFMPEG'; sc.render.ffmpeg.format='MPEG4'; sc.render.ffmpeg.codec='H264'; sc.render.ffmpeg.constant_rate_factor='MEDIUM'; sc.render.filepath=str(OUT/f'{name}.mp4'); bpy.ops.render.render(animation=True)
    for o in [q,e,a]: bpy.data.objects.remove(o,do_unlink=True)

def main():
    clean(); bpy.ops.import_scene.gltf(filepath=str(ASSET)); objs=[o for o in bpy.context.scene.objects if o.type=='MESH']; bpy.context.view_layer.update(); setup()
    h,s,c,hp,sp,d,dc=choose(objs); j=head_center(h,sp)
    debug={'humerus':h.name,'scapula':s.name,'clavicle':c.name,'humerus_scapula_distance':d,'clavicle_scapula_distance':dc,'joint':[j.x,j.y,j.z],'visible_rule':'ONLY selected humerus duplicate + matched scapula + matched clavicle + motion arc'}
    (OUT/'model_manifest.json').write_text(json.dumps({'mesh_count':len(objs),'selection_debug':debug,'quality_rule':'Strict matched shoulder complex from body.glb; no nearby-context meshes, placeholders, GIF reuse, or detached ghost.'},indent=2))
    render('shoulder_flexion_from_complete_model',h,s,c,j,'flexion'); render('shoulder_abduction_from_complete_model',h,s,c,j,'abduction')
    print('STRICT_SHOULDER_RENDER_COMPLETE',json.dumps(debug))
if __name__=='__main__': main()
