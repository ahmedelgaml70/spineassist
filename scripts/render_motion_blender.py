"""
Blender script: render a cleaner shoulder-motion pilot from a complete anatomy GLB.

Design decision after audit: the prior 3D output proved the pipeline works, but it was not
teaching-quality because too many limb structures were animated with a crude pivot. This
version narrows the pilot to the shoulder only, uses matched scapula/clavicle/humerus meshes
from the complete model, estimates a humeral-head pivot from mesh contact, and renders larger,
cleaner close-up motion clips.
"""

import bpy
import math
import json
import re
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "body.glb"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

BG = (0.955, 0.945, 0.925)
STATIC_BONE = (0.92, 0.86, 0.74, 1.0)
MOVING_BONE = (0.98, 0.48, 0.28, 1.0)
GHOST_BONE = (0.50, 0.70, 0.98, 0.22)

BAD_NAME_PARTS = [
    "muscle", "artery", "vein", "nerve", "ligament", "tendon", "skin",
    "cartilage", "deltoid", "pectoralis", "trapezius", "latissimus"
]


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_model():
    if not ASSET.exists():
        raise FileNotFoundError(f"Missing {ASSET}. Run scripts/download_model.sh first.")
    bpy.ops.import_scene.gltf(filepath=str(ASSET))
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objs:
        raise RuntimeError("No mesh objects found after importing body.glb")
    bpy.context.view_layer.update()
    return objs


def norm_name(obj_or_name):
    s = obj_or_name.name if hasattr(obj_or_name, "name") else str(obj_or_name)
    s = s.lower()
    s = re.sub(r"\.\d+$", "", s)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^a-z0-9\. ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_bone(obj, token):
    n = norm_name(obj)
    if any(bad in n for bad in BAD_NAME_PARTS):
        return False
    return token in n


def find_bones(objs, token):
    return [o for o in objs if is_bone(o, token)]


def side_hint(obj):
    n = norm_name(obj)
    if any(x in n for x in ["right", ".r", " r", "dexter"]):
        return "right"
    if any(x in n for x in ["left", ".l", " l", "sinister"]):
        return "left"
    return "unknown"


def object_center(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (mn + mx) / 2


def sampled_vertices(obj, max_count=650):
    total = max(1, len(obj.data.vertices))
    step = max(1, total // max_count)
    pts = [obj.matrix_world @ v.co for i, v in enumerate(obj.data.vertices) if i % step == 0]
    return pts or [object_center(obj)]


def closest_pair(obj_a, obj_b):
    pts_a = sampled_vertices(obj_a)
    pts_b = sampled_vertices(obj_b)
    best = None
    best_d = None
    for a in pts_a:
        for b in pts_b:
            d = (a - b).length_squared
            if best_d is None or d < best_d:
                best_d = d
                best = (a, b)
    return best[0], best[1], math.sqrt(best_d)


def choose_shoulder(objs):
    humeri = find_bones(objs, "humerus")
    scapulae = find_bones(objs, "scapula")
    clavicles = find_bones(objs, "clavicle")
    if not humeri or not scapulae or not clavicles:
        write_manifest(objs, {"error": "missing shoulder bones"})
        raise RuntimeError("Could not find humerus, scapula, and clavicle meshes in complete model")

    best = None
    for h in humeri:
        for s in scapulae:
            hp, sp, d = closest_pair(h, s)
            side_bonus = 0.0 if side_hint(h) == side_hint(s) else 0.25
            score = d + side_bonus
            if best is None or score < best["score"]:
                best = {"humerus": h, "scapula": s, "humerus_contact": hp, "scapula_contact": sp, "distance": d, "score": score}

    clavicle = min(clavicles, key=lambda c: (object_center(c) - object_center(best["scapula"])).length)
    best["clavicle"] = clavicle
    best["side_humerus"] = side_hint(best["humerus"])
    best["side_scapula"] = side_hint(best["scapula"])
    return best


def humeral_head_center(humerus, scapula_contact):
    pts = sampled_vertices(humerus, max_count=2500)
    ordered = sorted(pts, key=lambda p: (p - scapula_contact).length_squared)
    n = max(18, min(90, len(ordered) // 18))
    ctr = Vector((0, 0, 0))
    for p in ordered[:n]:
        ctr += p
    return ctr / n


def duplicate_for_ghost(obj, name, mat_name, rgba):
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    set_material(dup, mat_name, rgba)
    return dup


def bounds(objs):
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        raise RuntimeError("No bounds available")
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def set_material(obj, name, rgba):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Alpha"].default_value = rgba[3]
        bsdf.inputs["Roughness"].default_value = 0.55
        bsdf.inputs["Metallic"].default_value = 0.0
    mat.blend_method = "BLEND" if rgba[3] < 1.0 else "OPAQUE"
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def set_visibility(visible):
    visible = set(visible)
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.hide_render = o not in visible
            o.hide_viewport = o not in visible


def make_empty(name, loc):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.empty_display_type = "SPHERE"
    e.empty_display_size = 0.08
    e.location = loc
    return e


def parent_to_empty(obj, parent):
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 72
    scene.render.fps = 24
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 900
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.color = BG
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 64
    bpy.ops.object.light_add(type="AREA", location=(0, -3.5, 5))
    bpy.context.object.data.energy = 600
    bpy.context.object.data.size = 5
    bpy.ops.object.light_add(type="AREA", location=(3.5, 2.5, 4))
    bpy.context.object.data.energy = 180
    bpy.context.object.data.size = 5


def camera_for(name, visible, view):
    bpy.context.view_layer.update()
    mn, mx = bounds(visible)
    ctr = (mn + mx) / 2
    ext = mx - mn
    max_extent = max(ext.x, ext.y, ext.z, 1.0)
    if view == "lateral":
        direction = Vector((1.0, -0.18, 0.10)).normalized()
    else:
        direction = Vector((0.05, -1.0, 0.10)).normalized()
    bpy.ops.object.camera_add(location=ctr + direction * max_extent * 3.8)
    cam = bpy.context.object
    cam.name = "Camera_" + name
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max_extent * 1.55
    look_at(cam, ctr)
    bpy.context.scene.camera = cam


def key_rot(obj, frame, rot):
    bpy.context.scene.frame_set(frame)
    obj.rotation_euler = rot
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def render_clip(name, humerus, scapula, clavicle, joint, view, rot_mid):
    # static ghost at the target angle gives students a destination cue without using pasted graphics
    ghost_parent = make_empty(name + "_ghost_parent", joint)
    ghost = duplicate_for_ghost(humerus, name + "_target_ghost", "Ghost_Bone", GHOST_BONE)
    parent_to_empty(ghost, ghost_parent)
    ghost_parent.rotation_euler = rot_mid

    mover = make_empty(name + "_motion_parent", joint)
    parent_to_empty(humerus, mover)
    key_rot(mover, 1, (0, 0, 0))
    key_rot(mover, 36, rot_mid)
    key_rot(mover, 72, (0, 0, 0))

    visible = [scapula, clavicle, humerus, ghost]
    set_visibility(visible)
    camera_for(name, visible, view)

    scene = bpy.context.scene
    scene.frame_set(36)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUT / f"{name}_poster.png")
    bpy.ops.render.render(write_still=True)
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.filepath = str(OUT / f"{name}.mp4")
    bpy.ops.render.render(animation=True)

    # Restore humerus for the next clip.
    humerus.parent = None
    humerus.matrix_world = humerus.matrix_world.copy()
    mover.animation_data_clear()
    bpy.data.objects.remove(mover, do_unlink=True)
    bpy.data.objects.remove(ghost, do_unlink=True)
    bpy.data.objects.remove(ghost_parent, do_unlink=True)


def write_manifest(objs, extra):
    m = {
        "mesh_count": len(objs),
        "detected_counts": {
            "humerus": len(find_bones(objs, "humerus")),
            "scapula": len(find_bones(objs, "scapula")),
            "clavicle": len(find_bones(objs, "clavicle")),
        },
        "selection_debug": extra,
        "quality_rule": "Shoulder pilot must use complete-model mesh geometry and must not reuse original GIFs or placeholder assets."
    }
    (OUT / "model_manifest.json").write_text(json.dumps(m, indent=2))


def main():
    clean_scene()
    objs = import_model()
    setup_render()
    selection = choose_shoulder(objs)
    humerus = selection["humerus"]
    scapula = selection["scapula"]
    clavicle = selection["clavicle"]

    joint = humeral_head_center(humerus, selection["scapula_contact"])
    for o in [scapula, clavicle]:
        set_material(o, "Static_Bone", STATIC_BONE)
    set_material(humerus, "Moving_Humerus", MOVING_BONE)

    render_clip(
        "shoulder_flexion_from_complete_model",
        humerus, scapula, clavicle, joint,
        "lateral",
        (math.radians(58), 0, 0)
    )
    render_clip(
        "shoulder_abduction_from_complete_model",
        humerus, scapula, clavicle, joint,
        "front",
        (0, math.radians(-58), 0)
    )

    write_manifest(objs, {
        "selected_humerus": humerus.name,
        "selected_scapula": scapula.name,
        "selected_clavicle": clavicle.name,
        "humerus_side_hint": selection["side_humerus"],
        "scapula_side_hint": selection["side_scapula"],
        "mesh_contact_distance": selection["distance"],
        "estimated_humeral_head_center": [joint.x, joint.y, joint.z],
        "audit_note": "This is intentionally a two-slide shoulder-only pilot; ankle and full-arm segments are deferred until the shoulder visual passes inspection."
    })


if __name__ == "__main__":
    main()
