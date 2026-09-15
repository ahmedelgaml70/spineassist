#!/usr/bin/env python3
import json, subprocess, zipfile
from pathlib import Path
OUT=Path('outputs')
REQ=['anatomy_motion_pilot.pptx','model_manifest.json','shoulder_flexion_from_complete_model.mp4','shoulder_abduction_from_complete_model.mp4','shoulder_flexion_from_complete_model_poster.png','shoulder_abduction_from_complete_model_poster.png']
BAD=['motion clip missing','run blender render first','placeholder','missing render output','reused gif']
def fail(x): raise SystemExit('AUDIT FAILED: '+x)
def video(p):
 r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,duration','-of','json',str(p)],capture_output=True,text=True,check=True); s=json.loads(r.stdout)['streams'][0]; w=int(s.get('width',0)); h=int(s.get('height',0)); d=float(s.get('duration',0));
 if w<900 or h<500 or d<2: fail(f'bad video {p.name}: {w}x{h}, {d}s')
 return {'width':w,'height':h,'duration':d,'bytes':p.stat().st_size}
def png(p):
 b=p.read_bytes();
 if not b.startswith(b'\x89PNG\r\n\x1a\n'): fail(p.name+' is not PNG')
 w=int.from_bytes(b[16:20],'big'); h=int.from_bytes(b[20:24],'big');
 if w<900 or h<500: fail(f'bad poster {p.name}: {w}x{h}')
 return {'width':w,'height':h,'bytes':p.stat().st_size}
def manifest(p):
 m=json.loads(p.read_text());
 if m.get('mesh_count',0)<500: fail('complete-model mesh count too low')
 q=m.get('selection_debug') or {}; expected={'humerus':'Humerus.003','scapula':'Scapula.003','clavicle':'Clavicle.001'}
 for k,v in expected.items():
  if q.get(k)!=v: fail(f'unexpected {k}: {q.get(k)}')
 d=float(q.get('humerus_scapula_distance',999)); dc=float(q.get('clavicle_scapula_distance',999)); gh=float(q.get('gh_limit',0)); ac=float(q.get('ac_limit',0))
 if d>gh or dc>ac: fail(f'shoulder continuity failed: GH {d}/{gh}, AC {dc}/{ac}')
 rule=(m.get('quality_rule') or '').lower();
 if 'body.glb' not in rule or 'no nearby context' not in rule: fail('strict complete-model visibility rule missing')
 qa=m.get('pipeline_qa') or {}
 if qa.get('fix_version')!='clean-render-hook-v7' or not qa.get('clean_renderer_executed'): fail('clean renderer execution not proven')
 if qa.get('decorative_arc_created') is not False: fail('decorative arc must not be created')
 if len((qa.get('events') or {}).get('gh_contact',[]))!=2: fail('expected GH QA events for both clips')
 if 'moving humerus' not in (q.get('visible_rule') or '').lower(): fail('strict visible-object rule missing')
 return m
def ppt(p):
 with zipfile.ZipFile(p) as z:
  names=z.namelist(); slides=[n for n in names if n.startswith('ppt/slides/slide') and n.endswith('.xml')]; media=[n for n in names if n.startswith('ppt/media/') and not n.endswith('/')]; mp4=[n for n in media if n.lower().endswith('.mp4')]
  if len(slides)<4 or len(mp4)<2: fail(f'PPT package incomplete: slides={len(slides)}, mp4={len(mp4)}')
  text='\n'.join(z.read(n).decode('utf-8','ignore') for n in slides).lower(); off=[x for x in BAD if x in text]
  if off: fail('forbidden placeholder text: '+str(off))
  sizes=[len(z.read(n)) for n in mp4]
  if min(sizes)<10000: fail('embedded MP4 suspiciously small')
  return {'slides':len(slides),'media':len(media),'mp4s':len(mp4),'embedded_mp4_bytes':sizes}
def main():
 for n in REQ:
  p=OUT/n
  if not p.exists() or p.stat().st_size<10000: fail('missing/small '+n)
 s={'manifest':manifest(OUT/'model_manifest.json'),'videos':{},'posters':{}}
 for n in REQ[2:4]: s['videos'][n]=video(OUT/n)
 for n in REQ[4:]: s['posters'][n]=png(OUT/n)
 s['pptx']=ppt(OUT/'anatomy_motion_pilot.pptx'); s['verdict']='PASS technical authenticity/clean-render routing/packaging gate; human visual teaching review still required.'; (OUT/'audit_summary.json').write_text(json.dumps(s,indent=2)); print(json.dumps(s,indent=2))
if __name__=='__main__': main()
