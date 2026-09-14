"""
Fast corrective shoulder renderer.

This entry point keeps the world-baked humerus fix, but deliberately renders a small
anatomical proof before we spend CI time on polished assets. The proof contains only the
matched humerus, scapula, clavicle and a motion arc. It uses exact bone-name matching,
preserves the source humerus world pose during re-parenting, and records hard transform QA.

The rendered movements are isolated glenohumeral demonstrations: the scapula and clavicle
are static references. They must not be described as full shoulder-complex elevation.
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

qa_events = {"duplicates": [], "parenting": [], "render_profile": {}}


def exact_is_bone(obj, token):
    n = base.norm_name(obj)
    if any(bad in n for bad in base.BAD_NAME_PARTS):
        return False
    return re.search(rf"(^|\s){re.escape(token)}($|\s)", n) is not None


def duplicate_world_baked(obj, name):
    base.bpy.context.view_layer.update()
    source_center = base.object_center(obj)
    source_world = obj.matrix_world.copy()
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    base.bpy.context.collection.objects.link(dup)
    dup.parent = None
    dup.matrix_parent_inverse.identity()
    dup.data.transform(source_world)
    dup.data.update()
    dup.matrix_world = Matrix.Identity(4)
    base.bpy.context.view_layer.update()
    baked_center = base.object_center(dup)
    shift = (baked_center - source_center).length
    qa_events["duplicates"].append({"object": dup.name, "source_to_baked_center_shift": shift})
    print(f"DUPLICATE_QA {dup.name}: source-to-baked center shift={shift:.9f}")
    if shift > 1e-5:
        raise RuntimeError(f"World-baking displaced {dup.name} by {shift:.9f}")
    return dup


def parent_baked_world_mesh(obj, parent):
    base.bpy.context.view_layer.update()
    before = base.object_center(obj)
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    base.bpy.context.view_layer.update()
    after = base.object_center(obj)
    shift = (after - before).length
    qa_events["parenting"].append({"object": obj.name, "world_center_shift": shift})
    print(f"PARENT_QA {obj.name}: world-center shift={shift:.9f}")
    if shift > 1e-5:
        raise RuntimeError(f"Animation parenting displaced {obj.name} by {shift:.9f}")


def fast_setup_render():
    scene = base.bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 36
    scene.render.fps = 18
    scene.render.resolution_x = 960
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.world = scene.world or base.bpy.data.worlds.new("World")
    scene.world.color = base.BG
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except Exception:
            pass
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 16
    base.bpy.ops.object.light_add(type="AREA", location=(0, -3.5, 5))
    key = base.bpy.context.object
    key.data.energy = 650
    key.data.size = 5
    base.bpy.ops.object.light_add(type="AREA", location=(3.5, 2.5, 4))
    fill = base.bpy.context.object
    fill.data.energy = 190
    fill.data.size = 5
    qa_events["render_profile"] = {
        "purpose": "fast anatomical proof before polished rendering",
        "resolution": [960, 600], "fps": 18, "frames": 36,
        "context": "matched scapula and clavicle only",
        "motion_scope": "isolated glenohumeral motion; scapula/clavicle held static"
    }


def shoulder_only_context(objs, joint, chosen, radius):
    return list(dict.fromkeys(chosen))


def contact_distance(obj_a, obj_b):
    _, _, d = base.closest_pair(obj_a, obj_b)
    return d


def fast_render_clip(name, humerus_source, scapula, clavicle, context, joint, view, plane, rot_mid):
    moving_humerus = duplicate_world_baked(humerus_source, name + "_moving_humerus")
    base.set_material(moving_humerus, "Moving_Humerus", base.MOVING_BONE)
    base.set_material(scapula, "Static_Shoulder", base.STATIC_BONE)
    base.set_material(clavicle, "Static_Shoulder", base.STATIC_BONE)

    mover = base.make_empty(name + "_motion_parent", joint)
    parent_baked_world_mesh(moving_humerus, mover)
    start, mid, end = 1, 18, 36
    base.key_rot(mover, start, (0, 0, 0))
    base.key_rot(mover, mid, rot_mid)
    base.key_rot(mover, end, (0, 0, 0))

    # Smaller arc stays inside the close-up frame instead of being clipped off-screen.
    arc = base.make_arc(name + "_arc", joint, base.object_extent(humerus_source) * 0.43, plane)
    visible_meshes = [scapula, clavicle, moving_humerus]
    base.set_visibility(visible_meshes + [arc])
    base.camera_for(name, visible_meshes, joint, view)

    scene = base.bpy.context.scene
    scene.frame_set(start)
    start_radii = sorted((p - joint).length for p in base.sampled_vertices(moving_humerus, 500))
    start_contact = contact_distance(moving_humerus, scapula)
    scene.frame_set(mid)
    mid_radii = sorted((p - joint).length for p in base.sampled_vertices(moving_humerus, 500))
    mid_contact = contact_distance(moving_humerus, scapula)
    radius_error = max((abs(a - b) for a, b in zip(start_radii, mid_radii)), default=0.0)
    extent = max(base.object_extent(humerus_source), 1e-6)
    contact_drift = abs(mid_contact - start_contact)
    contact_limit = max(0.004, extent * 0.04)
    qa_events.setdefault("pivot_radius", []).append({"clip": name, "max_radius_error": radius_error})
    qa_events.setdefault("gh_contact", []).append({
        "clip": name,
        "start_contact_distance": start_contact,
        "mid_contact_distance": mid_contact,
        "contact_distance_drift": contact_drift,
        "allowed_drift": contact_limit
    })
    print(f"PIVOT_QA {name}: radial error={radius_error:.9f}")
    print(f"CONTACT_QA {name}: start={start_contact:.6f} mid={mid_contact:.6f} drift={contact_drift:.6f} limit={contact_limit:.6f}")
    if radius_error > 1e-4:
        raise RuntimeError(f"{name} does not rotate rigidly around the GH pivot; error={radius_error:.9f}")
    if contact_drift > contact_limit:
        raise RuntimeError(f"{name} loses GH surface relationship during motion; drift={contact_drift:.6f}")

    scene.frame_set(mid)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(base.OUT / f"{name}_poster.png")
    base.bpy.ops.render.render(write_still=True)
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "REALTIME"
    scene.render.filepath = str(base.OUT / f"{name}.mp4")
    base.bpy.ops.render.render(animation=True)

    base.bpy.data.objects.remove(moving_humerus, do_unlink=True)
    base.bpy.data.objects.remove(mover, do_unlink=True)
    base.bpy.data.objects.remove(arc, do_unlink=True)


base.is_bone = exact_is_bone
base.duplicate_mesh = duplicate_world_baked
base.parent_to_empty = parent_baked_world_mesh
base.setup_render = fast_setup_render
base.nearby_context = shoulder_only_context
base.render_clip = fast_render_clip
base.main()

manifest_path = base.OUT / "model_manifest.json"
manifest = json.loads(manifest_path.read_text())
max_duplicate_shift = max((e["source_to_baked_center_shift"] for e in qa_events["duplicates"]), default=0.0)
max_parent_shift = max((e["world_center_shift"] for e in qa_events["parenting"]), default=0.0)
max_radius_error = max((e["max_radius_error"] for e in qa_events.get("pivot_radius", [])), default=0.0)
max_contact_ratio = max((e["contact_distance_drift"] / e["allowed_drift"] for e in qa_events.get("gh_contact", []) if e["allowed_drift"]), default=0.0)
passed = max_duplicate_shift <= 1e-5 and max_parent_shift <= 1e-5 and max_radius_error <= 1e-4 and max_contact_ratio <= 1.0
manifest["pipeline_qa"] = {
    "fix_version": "fast-world-baked-gh-contact-proof-v5",
    "hierarchy_contact_preserved": passed,
    "max_source_to_baked_center_shift": max_duplicate_shift,
    "max_parenting_world_center_shift": max_parent_shift,
    "max_pivot_radius_error": max_radius_error,
    "max_gh_contact_drift_ratio": max_contact_ratio,
    "events": qa_events,
    "bone_matching": "exact normalized token match",
    "motion_geometry": "world-baked detached humerus rotated around estimated GH pivot",
    "teaching_scope": "isolated glenohumeral flexion/abduction; not full shoulder-complex elevation"
}
manifest["selection_debug"]["corrective_change"] = (
    "Preserve the world-baked hierarchy fix, add start-to-mid humerus/scapula contact-distance QA, "
    "and reduce the motion-arc radius so the visual cue remains inside the close-up frame."
)
manifest_path.write_text(json.dumps(manifest, indent=2))
if not passed:
    raise RuntimeError("Fast shoulder transform/contact QA failed")
