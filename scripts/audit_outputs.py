#!/usr/bin/env python3
import json, subprocess, zipfile
from pathlib import Path
OUT=Path('outputs')
REQ=['anatomy_motion_pilot.pptx','model_manifest.json','shoulder_flexion_from_complete_model.mp4','shoulder_abduction_from_complete_model.mp4','shoulder_flexion_from_complete_model_poster.png','shoulder_abduction_from_complete_model_poster.png']
MIN_BYTES={'anatomy_motion_pilot.pptx':10000,'model_manifest.json':500,'shoulder_flexion_from_complete_model.mp4':10000,'shoulder_abduction_from_complete_model.mp4':10000,'shoulder_flexion_from_complete_model_poster.png':10000,'shoulder_abduction_from_complete_model_poster.png':10000}
BAD=['motion clip missing','run blender render first','placeholder','missing render output']
def fail(x): raise SystemExit('AUDIT FAILED: '+x)
def video(p):
 r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,duration','-of','json',str(p)],capture_output=True,text=True,check=True); s=json.loads(r.stdout)['streams'][0]; w=int(s.get('width',0)); h=int(s.get('height',0)); d=float(s.get('duration',0));
 if s.get('codec_name')!='h264' or w<900 or h<500 or d<2: fail(f'bad video {p.name}: codec={s.get("codec_name")} {w}x{h}, {d}s')
 return {'codec':s.get('codec_name'),'width':w,'height':h,'duration':d,'bytes':p.stat().st_size}
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
 qa=m.get('pipeline_qa') or {}; version=qa.get('fix_version','')
 if version!='full-excursion-framing-v10' or not qa.get('clean_renderer_executed'): fail(f'current full-excursion renderer execution not proven: {version}')
 if 'union of neutral and terminal' not in (qa.get('camera_rule') or '').lower(): fail('full-excursion camera rule missing')
 if qa.get('decorative_arc_created') is not False: fail('decorative arc must not be created')
 if not qa.get('hierarchy_contact_preserved'): fail('transform/contact QA did not pass')
 if len((qa.get('events') or {}).get('gh_contact',[]))!=2: fail('expected GH QA events for both clips')
 if float(qa.get('max_humeral_head_center_translation',999))>1e-5: fail('humeral-head centre translated during isolated rotation')
 if float(qa.get('max_gh_contact_drift_ratio',999))>1: fail('GH contact drift exceeded renderer limit')
 if 'moving humerus' not in (q.get('visible_rule') or '').lower(): fail('strict visible-object rule missing')
 return m
def ppt(p):
 with zipfile.ZipFile(p) as z:
  names=z.namelist(); slides=[n for n in names if n.startswith('ppt/slides/slide') and n.endswith('.xml')]; media=[n for n in names if n.startswith('ppt/media/') and not n.endswith('/')]; mp4=[n for n in media if n.lower().endswith('.mp4')]; gifs=[n for n in media if n.lower().endswith('.gif')]
  if len(slides)<4 or len(mp4)<2: fail(f'PPT package incomplete: slides={len(slides)}, mp4={len(mp4)}')
  if gifs: fail('GIF media present in deck: '+str(gifs))
  text='\n'.join(z.read(n).decode('utf-8','ignore') for n in slides).lower(); off=[x for x in BAD if x in text]
  if off: fail('forbidden placeholder text: '+str(off))
  sizes=[len(z.read(n)) for n in mp4]
  if min(sizes)<10000: fail('embedded MP4 suspiciously small')
  payloads=[z.read(n) for n in mp4]
  if len({__import__('hashlib').sha256(b).hexdigest() for b in payloads})!=len(mp4): fail('duplicate/reused embedded MP4 payloads')
  return {'slides':len(slides),'media':len(media),'mp4s':len(mp4),'gifs':len(gifs),'embedded_mp4_bytes':sizes}
def main():
 for n in REQ:
  p=OUT/n; minimum=MIN_BYTES[n]
  if not p.exists() or p.stat().st_size<minimum: fail(f'missing/small {n}: {p.stat().st_size if p.exists() else 0} bytes, minimum {minimum}')
 s={'manifest':manifest(OUT/'model_manifest.json'),'videos':{},'posters':{}}
 for n in REQ[2:4]: s['videos'][n]=video(OUT/n)
 for n in REQ[4:]: s['posters'][n]=png(OUT/n)
 s['pptx']=ppt(OUT/'anatomy_motion_pilot.pptx'); s['verdict']='PASS technical authenticity/full-excursion renderer/packaging gate; human visual teaching review still required.'; (OUT/'audit_summary.json').write_text(json.dumps(s,indent=2)); print(json.dumps(s,indent=2))
if __name__=='__main__': main()
