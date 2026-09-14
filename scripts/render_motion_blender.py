"""
Blender script: render anatomy motion clips from a complete anatomy GLB.

This revision fixes the first successful-but-bad visual output:
- it no longer selects both left and right limbs,
- it no longer includes muscles/tendons just because their names contain "scapula" or "ulna",
- it chooses one anatomical side by spatial clustering,
- it frames each render from the actual animated bounds.
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
BONE = (0.92, 0.86, 0.74, 1.0)
MOVING_BONE = (0.98, 0.91, 0.68, 1.0)

CARPALS = {
    "scaphoid", "lunate", "triquetrum", "pisiform", "trapezium",
    "trapezoid", "capitate", "hamate"
}
FOOT_BONES = {
    "talus", "calcaneus", "navicular bone", "cuboid bone",
    "medial cuneiform bone", "intermediate cuneiform bone", "lateral cuneiform bone"
}


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
    return objs


def base_name(o):
    return re.sub(r"\.\d+$", "", (o.name or "")).strip().lower()


def is_exact_bone(o, name):
    return base_name(o) == name.lower()


def is_hand_bone(o):
    n = base_name(o)
    return (
        n in CARPALS
        or "metacarpal bone" in n
        or ("phalanx" in n and "hand" in n)
        or ("phalanx" in n and "finger" in n and "foot" not in n)
    )


def is_foot_bone(o):
    n = base_name(o)
    return (
        n in FOOT_BONES
        or "metatarsal bone" in n
        or ("phalanx" in n and "foot" in n)
        or ("phalanx" in n and "toe" in n)
    )


def center_of_object(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (mn + mx) / 2


def bounds(objs):
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        raise RuntimeError("Cannot compute bounds for empty object list")
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def center(objs):
    mn, mx = bounds(objs)
    return (mn + mx) / 2


def set_material(obj, name, rgba):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
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
    e.empty_display_size = 0.10
    e.location = loc
    return e


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 72
    scene.render.fps = 24
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.color = BG
    scene.eevee.taa_render_samples = 32
    scene.render.film_transparent = False

    bpy.ops.object.light_add(type="AREA", location=(0, -4, 6))
    key = bpy.context.object
    key.name = "Key_Light"
    key.data.energy = 750
    key.data.size = 5

    bpy.ops.object.light_add(type="AREA", location=(4, 3, 4))
    fill = bpy.context.object
    fill.name = "Fill_Light"
    fill.data.energy = 220
    fill.data.size = 6


def add_camera_framed(name, visible, view="oblique"):
    mn, mx = bounds(visible)
    ctr = (mn + mx) / 2
    extent = mx - mn
    radius = max(extent.x, extent.y, extent.z, 1.0)

    if view == "front":
        direction = Vector((0, -1, 0.18)).normalized()
    elif view == "lateral":
        direction = Vector((1, -0.10, 0.12)).normalized()
    else:
        direction = Vector((1, -1, 0.35)).normalized()

    bpy.ops.object.camera_add(location=ctr + direction * radius * 3.2)
    cam = bpy.context.object
    cam.name = f"Camera_{name}"
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = radius * 1.28
    look_at(cam, ctr)
    bpy.context.scene.camera = cam
    bpy.context.scene.render.film_transparent = False
    return cam


def key_rot(obj, frame, rot):
    bpy.context.scene.frame_set(frame)
    obj.rotation_euler = rot
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def render_clip(name, visible, view):
    scene = bpy.context.scene
    scene.frame_set(36)
    bpy.context.view_layer.update()
    add_camera_framed(name, visible, view)
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


def mesh_point_closest_to(obj, target, sample_step=4):
    verts = obj.data.vertices
    if not verts:
        return center_of_object(obj)
    best = None
    best_d = None
    for i, v in enumerate(verts):
        if i % sample_step:
            continue
        p = obj.matrix_world @ v.co
        d = (p - target).length_squared
        if best is None or d < best_d:
            best, best_d = p, d
    return best or center_of_object(obj)


def choose_one_side(pair_candidates):
    if len(pair_candidates) < 2:
        return None, None, None
    cs = sorted([center_of_object(o) for o in pair_candidates], key=lambda v: (v.x, v.y, v.z))
    a, b = cs[0], cs[-1]
    axis = (b - a).normalized()
    mid = (a + b) / 2
    chosen = max(pair_candidates, key=lambda o: (center_of_object(o) - mid).dot(axis))
    return chosen, axis, mid


def same_side(objs, axis, mid, side_sign=1):
    selected = []
    for o in objs:
        val = (center_of_object(o) - mid).dot(axis)
        if val * side_sign >= -0.02:
            selected.append(o)
    return selected


def closest_n(objs, target, n=None):
    ordered = sorted(objs, key=lambda o: (center_of_object(o) - target).length)
    return ordered if n is None else ordered[:n]


def manifest(objs):
    groups = {
        "humerus_exact": [o.name for o in objs if is_exact_bone(o, "humerus")],
        "scapula_exact": [o.name for o in objs if is_exact_bone(o, "scapula")],
        "clavicle_exact": [o.name for o in objs if is_exact_bone(o, "clavicle")],
        "radius_exact": [o.name for o in objs if is_exact_bone(o, "radius")],
        "ulna_exact": [o.name for o in objs if is_exact_bone(o, "ulna")],
        "hand_bone_exact": [o.name for o in objs if is_hand_bone(o)],
        "tibia_exact": [o.name for o in objs if is_exact_bone(o, "tibia")],
        "fibula_exact": [o.name for o in objs if is_exact_bone(o, "fibula")],
        "foot_bone_exact": [o.name for o in objs if is_foot_bone(o)],
    }
    m = {"mesh_count": len(objs), "sample_names": [o.name for o in objs[:500]], "detected": groups}
    (OUT / "model_manifest.json").write_text(json.dumps(m, indent=2))


def parent_group(objs, parent):
    for o in objs:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()


def main():
    clean_scene()
    objs = import_model()
    manifest(objs)
    setup_render()

    humeri = [o for o in objs if is_exact_bone(o, "humerus")]
    humerus, axis, mid = choose_one_side(humeri)
    if humerus is None:
        raise RuntimeError("Expected two exact humerus meshes for left/right side selection.")
    chosen_sign = 1
    h_ctr = center_of_object(humerus)

    scapula = same_side([o for o in objs if is_exact_bone(o, "scapula")], axis, mid, chosen_sign)
    clavicle = same_side([o for o in objs if is_exact_bone(o, "clavicle")], axis, mid, chosen_sign)
    radius = same_side([o for o in objs if is_exact_bone(o, "radius")], axis, mid, chosen_sign)
    ulna = same_side([o for o in objs if is_exact_bone(o, "ulna")], axis, mid, chosen_sign)
    hand = same_side([o for o in objs if is_hand_bone(o)], axis, mid, chosen_sign)

    if not scapula or not clavicle or not radius or not ulna:
        raise RuntimeError("Failed to isolate one-side exact upper-limb bones. Inspect model_manifest.json.")

    static_shoulder = closest_n(scapula, h_ctr, 1) + closest_n(clavicle, h_ctr, 1)
    moving_arm = [humerus] + closest_n(radius, h_ctr, 1) + closest_n(ulna, h_ctr, 1) + hand
    visible = static_shoulder + moving_arm

    for o in static_shoulder:
        set_material(o, "Static_Bone", BONE)
    for o in moving_arm:
        set_material(o, "Moving_Bone", MOVING_BONE)

    set_visibility(visible)
    shoulder_anchor = center(static_shoulder)
    joint = mesh_point_closest_to(humerus, shoulder_anchor, sample_step=3)
    arm_parent = make_empty("Glenohumeral_axis", joint)
    parent_group(moving_arm, arm_parent)

    # Shoulder flexion: controlled sagittal-plane approximation from the actual model geometry.
    key_rot(arm_parent, 1, (0, 0, 0))
    key_rot(arm_parent, 36, (math.radians(65), 0, 0))
    key_rot(arm_parent, 72, (0, 0, 0))
    render_clip("shoulder_flexion_from_complete_model", visible, "lateral")

    arm_parent.rotation_euler = (0, 0, 0)
    arm_parent.animation_data_clear()
    key_rot(arm_parent, 1, (0, 0, 0))
    key_rot(arm_parent, 36, (0, math.radians(-65), 0))
    key_rot(arm_parent, 72, (0, 0, 0))
    render_clip("shoulder_abduction_from_complete_model", visible, "front")

    # Ankle: exact lower-limb bones, same side by the humerus-derived body side axis.
    tibia = same_side([o for o in objs if is_exact_bone(o, "tibia")], axis, mid, chosen_sign)
    fibula = same_side([o for o in objs if is_exact_bone(o, "fibula")], axis, mid, chosen_sign)
    foot = same_side([o for o in objs if is_foot_bone(o)], axis, mid, chosen_sign)

    if tibia and fibula and foot:
        leg_static = closest_n(tibia, h_ctr, 1) + closest_n(fibula, h_ctr, 1)
        # For foot, choose bones below the selected tibia/fibula and on the same side.
        ankle_ref = center(leg_static)
        foot = [o for o in foot if (center_of_object(o) - ankle_ref).length < 2.0]
        visible_ankle = leg_static + foot
        for o in visible_ankle:
            set_material(o, "Foot_Bone", MOVING_BONE if o in foot else BONE)
        set_visibility(visible_ankle)
        ankle_joint = mesh_point_closest_to(closest_n(tibia, ankle_ref, 1)[0], center(foot), sample_step=3)
        foot_parent = make_empty("Talocrural_axis", ankle_joint)
        parent_group(foot, foot_parent)
        key_rot(foot_parent, 1, (0, 0, 0))
        key_rot(foot_parent, 36, (math.radians(22), 0, 0))
        key_rot(foot_parent, 72, (0, 0, 0))
        render_clip("ankle_dorsiflexion_from_complete_model", visible_ankle, "lateral")
    else:
        raise RuntimeError("Could not isolate exact ankle bones; refusing to create a fake ankle slide.")


if __name__ == "__main__":
    main()
