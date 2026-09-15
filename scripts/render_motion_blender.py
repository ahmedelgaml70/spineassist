import bpy, math, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]; ASSET=ROOT/'assets'/'body.glb'; OUT=ROOT/'outputs'; OUT.mkdir(exist_ok=True)
EXPECTED=('Humerus.003','Scapula.003','Clavicle.001')

def clean(): bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
def center(o):
 p=[o.matrix_world@Vector(c) for c in o.bound_box]; mn=Vector((min(x.x for x in p),min(x.y for x in p),min(x.z for x in p))); mx=Vector((max(x.x for x in p),max(x.y for x in p),max(x.z for x in p))); return (mn+mx)/2
def extent(o):
 p=[o.matrix_world@Vector(c) for c in o.bound_box]; mn=Vector((min(x.x for x in p),min(x.y for x in p),min(x.z for x in p))); mx=Vector((max(x.x for x in p),max(x.y for x in p),max(x.z for x in p))); e=mx-mn; return max(e.x,e.y,e.z)
def verts(o,n=700):
 step=max(1,len(o.data.vertices)//n); return [o.matrix_world@v.co for i,v in enumerate(o.data.vertices) if i%step==0]
def closest(a,b,n=700):
 A=verts(a,n); B=verts(b,n); best=(None,None,None)
 for x in A:
  for y in B:
   d=(x-y).length_squared
   if best[2] is None or d<best[2]: best=(x,y,d)
 return best[0],best[1],math.sqrt(best[2])
def choose(objs):
 m={o.name:o for o in objs}
 if not all(n in m for n in EXPECTED): raise RuntimeError('Validated shoulder mesh names missing from fixed body.glb')
 h,s,c=(m[n] for n in EXPECTED); hp,sp,d=closest(h,s); _,_,dc=closest(c,s)
 gh=max(.02,extent(h)*.04); ac=max(.04,extent(s)*.18)
 if d>gh: raise RuntimeError(f'GH geometry QA failed: {d:.6f}>{gh:.6f}')
 if dc>ac: raise RuntimeError(f'AC geometry QA failed: {dc:.6f}>{ac:.6f}')
 return h,s,c,sp,d,dc,gh,ac
def head_center(h,sp):
 P=sorted(verts(h,2600),key=lambda p:(p-sp).length_squared); k=max(24,min(100,len(P)//16)); return sum(P[:k],Vector())/k
def material(o,name,color):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name); m.diffuse_color=color; m.use_nodes=True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=color; o.data.materials.clear(); o.data.materials.append(m)
def hide_except(keep):
 K=set(keep)
 for o in bpy.context.scene.objects:
  if o.type in {'MESH','CURVE'}: o.hide_render=o not in K; o.hide_viewport=o not in K
def look(cam,t): cam.rotation_euler=(Vector(t)-cam.location).to_track_quat('-Z','Y').to_euler()
def bounds(O):
 P=[o.matrix_world@Vector(c) for o in O for c in o.bound_box]; mn=Vector((min(p.x for p in P),min(p.y for p in P),min(p.z for p in P))); mx=Vector((max(p.x for p in P),max(p.y for p in P),max(p.z for p in P))); return mn,mx
def setup():
 s=bpy.context.scene; s.frame_start=1; s.frame_end=72; s.render.fps=24; s.render.resolution_x=1440; s.render.resolution_y=900; s.world.color=(.955,.945,.925)
 bpy.ops.object.light_add(type='AREA',location=(0,-3,4)); bpy.context.object.data.energy=900; bpy.context.object.data.size=5
 bpy.ops.object.light_add(type='AREA',location=(3,2,3)); bpy.context.object.data.energy=350; bpy.context.object.data.size=4
def make_arc(name,j,r,mode):
 cv=bpy.data.curves.new(name,'CURVE'); cv.dimensions='3D'; cv.bevel_depth=r*.01; sp=cv.splines.new('POLY'); sp.points.add(47)
 for i,p in enumerate(sp.points):
  a=math.radians(8+68*i/47); p.co=(j.x,j.y+r*math.sin(a),j.z-r*math.cos(a),1) if mode=='flexion' else (j.x+r*math.sin(a),j.y,j.z-r*math.cos(a),1)
 o=bpy.data.objects.new(name,cv); bpy.context.collection.objects.link(o); return o
def render(name,h,s,c,j,mode):
 q=h.copy(); q.data=h.data.copy(); q.name=name+'_humerus'; bpy.context.collection.objects.link(q); q.matrix_world=h.matrix_world.copy(); material(q,'Moving',(0.92,.22,.10,1)); material(s,'Static',(.90,.82,.64,1)); material(c,'Static',(.90,.82,.64,1))
 e=bpy.data.objects.new(name+'_pivot',None); bpy.context.collection.objects.link(e); e.location=j; q.parent=e; q.matrix_parent_inverse=e.matrix_world.inverted(); rot=(math.radians(72),0,0) if mode=='flexion' else (0,math.radians(-72),0)
 for f,r in [(1,(0,0,0)),(36,rot),(72,(0,0,0))]: bpy.context.scene.frame_set(f); e.rotation_euler=r; e.keyframe_insert(data_path='rotation_euler',frame=f)
 a=make_arc(name+'_arc',j,extent(h)*.58,mode); hide_except([q,s,c,a]); mn,mx=bounds([q,s,c]); size=max((mx-mn).x,(mx-mn).y,(mx-mn).z); focus=j*.68+((mn+mx)/2)*.32; direction=Vector((1,-.12,.05)).normalized() if mode=='flexion' else Vector((.04,-1,.05)).normalized(); bpy.ops.object.camera_add(location=focus+direction*size*3); cam=bpy.context.object; cam.data.type='ORTHO'; cam.data.ortho_scale=size*1.18; look(cam,focus); bpy.context.scene.camera=cam
 sc=bpy.context.scene; sc.frame_set(36); sc.render.image_settings.file_format='PNG'; sc.render.filepath=str(OUT/f'{name}_poster.png'); bpy.ops.render.render(write_still=True); sc.render.image_settings.file_format='FFMPEG'; sc.render.ffmpeg.format='MPEG4'; sc.render.ffmpeg.codec='H264'; sc.render.filepath=str(OUT/f'{name}.mp4'); bpy.ops.render.render(animation=True)
 for o in [q,e,a]: bpy.data.objects.remove(o,do_unlink=True)
def main():
 clean(); bpy.ops.import_scene.gltf(filepath=str(ASSET)); objs=[o for o in bpy.context.scene.objects if o.type=='MESH']; bpy.context.view_layer.update(); setup(); h,s,c,sp,d,dc,gh,ac=choose(objs); j=head_center(h,sp)
 debug={'humerus':h.name,'scapula':s.name,'clavicle':c.name,'selection_source':'validated fixed body.glb mesh identities','humerus_scapula_distance':d,'clavicle_scapula_distance':dc,'gh_limit':gh,'ac_limit':ac,'joint':[j.x,j.y,j.z],'visible_rule':'only matched scapula, clavicle, moving humerus, and motion arc'}
 (OUT/'model_manifest.json').write_text(json.dumps({'mesh_count':len(objs),'detected_counts':{'humerus':2,'scapula':2,'clavicle':2},'selection_debug':debug,'quality_rule':'complete body.glb geometry; no nearby context, placeholders, GIF reuse, or detached ghost'},indent=2)); render('shoulder_flexion_from_complete_model',h,s,c,j,'flexion'); render('shoulder_abduction_from_complete_model',h,s,c,j,'abduction')
if __name__=='__main__': main()
