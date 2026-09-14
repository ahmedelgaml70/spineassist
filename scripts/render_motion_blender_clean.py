"""Clean validated glenohumeral teaching renderer.

Renders only the matched humerus, scapula and clavicle. The moving humerus is detached by
baking its imported world transform into its mesh, then rotated around the estimated GH
pivot. No decorative 3D motion arc is rendered; the actual bone motion is the teaching cue.
"""
import importlib.util
import json
import re
from pathlib import Path
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("anatomy_render_base", HERE / "render_motion_blender.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
qa = {"duplicates": [], "parenting": [], "pivot_radius": [], "gh_contact": []}


def exact_is_bone(obj, token):
    n = base.norm_name(obj)
    return not any(b in n for b in base.BAD_NAME_PARTS) and re.search(rf"(^|\s){re.escape(token)}($|\s)", n) is not None


def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def duplicate_world_baked(obj, name):
    base.bpy.context.view_layer.update()
    before = base.object_center(obj)
    world = obj.matrix_world.copy()
    dup = obj.copy(); dup.data = obj.data.copy(); dup.name = name
    base.bpy.context.collection.objects.link(dup)
    dup.parent = None; dup.matrix_parent_inverse.identity()
    dup.data.transform(world); dup.data.update(); dup.matrix_world = Matrix.Identity(4)
    smooth(dup)
    base.bpy.context.view_layer.update()
    shift = (base.object_center(dup) - before).length
    qa["duplicates"].append({"object": name, "shift": shift})
    if shift > 1e-5:
        raise RuntimeError(f"World-baked duplicate shifted by {shift}")
    return dup


def parent_preserve(obj, parent):
    base.bpy.context.view_layer.update()
    before = base.object_center(obj)
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    base.bpy.context.view_layer.update()
    shift = (base.object_center(obj) - before).length
    qa["parenting"].append({"object": obj.name, "shift": shift})
    if shift > 1e-5:
        raise RuntimeError(f"Parenting displaced {obj.name} by {shift}")


def setup():
    s = base.bpy.context.scene
    s.frame_start = 1; s.frame_end = 36; s.render.fps = 18
    s.render.resolution_x = 960; s.render.resolution_y = 600; s.render.resolution_percentage = 100
    s.render.film_transparent = False
    s.world = s.world or base.bpy.data.worlds.new("World"); s.world.color = base.BG
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            s.render.engine = engine; break
        except Exception:
            pass
    if hasattr(s, "eevee"): s.eevee.taa_render_samples = 16
    base.bpy.ops.object.light_add(type="AREA", location=(0,-3.5,5)); base.bpy.context.object.data.energy=650; base.bpy.context.object.data.size=5
    base.bpy.ops.object.light_add(type="AREA", location=(3.5,2.5,4)); base.bpy.context.object.data.energy=190; base.bpy.context.object.data.size=5


def only_shoulder(objs, joint, chosen, radius):
    return list(dict.fromkeys(chosen))


def render_clip(name, humerus_source, scapula, clavicle, context, joint, view, plane, rot_mid):
    moving = duplicate_world_baked(humerus_source, name + "_moving_humerus")
    for obj in (scapula, clavicle):
        smooth(obj); base.set_material(obj, "Static_Shoulder", base.STATIC_BONE)
    base.set_material(moving, "Moving_Humerus", base.MOVING_BONE)

    mover = base.make_empty(name + "_pivot", joint)
    parent_preserve(moving, mover)
    base.key_rot(mover, 1, (0,0,0)); base.key_rot(mover, 18, rot_mid); base.key_rot(mover, 36, (0,0,0))
    visible = [scapula, clavicle, moving]
    base.set_visibility(visible)
    base.camera_for(name, visible, joint, view)

    scene = base.bpy.context.scene
    scene.frame_set(1)
    r0 = sorted((p-joint).length for p in base.sampled_vertices(moving,500))
    _,_,c0 = base.closest_pair(moving, scapula)
    scene.frame_set(18)
    r1 = sorted((p-joint).length for p in base.sampled_vertices(moving,500))
    _,_,c1 = base.closest_pair(moving, scapula)
    radial = max((abs(a-b) for a,b in zip(r0,r1)), default=0.0)
    drift = abs(c1-c0); limit = max(0.004, base.object_extent(humerus_source)*0.04)
    qa["pivot_radius"].append({"clip":name,"error":radial})
    qa["gh_contact"].append({"clip":name,"start":c0,"mid":c1,"drift":drift,"limit":limit})
    print(f"GH_QA {name}: radial={radial:.9f} contact_start={c0:.6f} contact_mid={c1:.6f} drift={drift:.6f} limit={limit:.6f}")
    if radial > 1e-4 or drift > limit:
        raise RuntimeError(f"GH QA failed for {name}")

    scene.frame_set(18)
    scene.render.image_settings.file_format="PNG"; scene.render.filepath=str(base.OUT/f"{name}_poster.png")
    base.bpy.ops.render.render(write_still=True)
    scene.render.image_settings.file_format="FFMPEG"; scene.render.ffmpeg.format="MPEG4"; scene.render.ffmpeg.codec="H264"
    scene.render.ffmpeg.constant_rate_factor="MEDIUM"; scene.render.ffmpeg.ffmpeg_preset="REALTIME"
    scene.render.filepath=str(base.OUT/f"{name}.mp4"); base.bpy.ops.render.render(animation=True)
    base.bpy.data.objects.remove(moving, do_unlink=True); base.bpy.data.objects.remove(mover, do_unlink=True)


base.is_bone = exact_is_bone
base.duplicate_mesh = duplicate_world_baked
base.parent_to_empty = parent_preserve
base.setup_render = setup
base.nearby_context = only_shoulder
base.render_clip = render_clip
base.main()

p = base.OUT/"model_manifest.json"
m = json.loads(p.read_text())
max_dup=max((e["shift"] for e in qa["duplicates"]),default=0); max_par=max((e["shift"] for e in qa["parenting"]),default=0)
max_rad=max((e["error"] for e in qa["pivot_radius"]),default=0); max_ratio=max((e["drift"]/e["limit"] for e in qa["gh_contact"]),default=0)
passed=max_dup<=1e-5 and max_par<=1e-5 and max_rad<=1e-4 and max_ratio<=1
m["pipeline_qa"]={
 "fix_version":"clean-no-arc-gh-v6","hierarchy_contact_preserved":passed,
 "max_source_to_baked_center_shift":max_dup,"max_parenting_world_center_shift":max_par,
 "max_pivot_radius_error":max_rad,"max_gh_contact_drift_ratio":max_ratio,"events":qa,
 "bone_matching":"exact normalized token match","motion_geometry":"world-baked humerus about estimated GH pivot",
 "teaching_scope":"isolated glenohumeral motion; scapula and clavicle deliberately fixed",
 "visual_cue":"bone motion only; no decorative 3D arc"
}
m["selection_debug"]["corrective_change"]="Removed the confusing 3D motion arc, kept only matched shoulder bones, enabled smooth shading, and retained transform/pivot/contact QA."
p.write_text(json.dumps(m,indent=2))
if not passed: raise RuntimeError("Clean GH QA failed")
