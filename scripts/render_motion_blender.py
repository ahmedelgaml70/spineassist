"""
Blender script: render anatomy motion clips from the complete anatomy GLB.

This revision responds to visual audit of run 5: the previous script produced genuine
3D-derived assets, but the shoulder complex was detached because side selection and
pivot estimation were too crude. This version chooses matched bones by nearest mesh
contact and anchors rotations at closest joint-surface points.
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
CARPALS = {"scaphoid", "lunate", "triquetrum", "pisiform", "trapezium", "trapezoid", "capitate", "hamate"}
FOOT_CORE = {"talus", "calcaneus", "navicular bone", "cuboid bone", "medial cuneiform bone", "intermediate cuneiform bone", "lateral cuneiform bone"}


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


def exact(objs, name):
    return [o for o in objs if base_name(o) == name.lower()]


def hand_bones(objs):
    out = []
    for o in objs:
        n = base_name(o)
        if n in CARPALS or "metacarpal bone" in n or ("phalanx" in n and ("hand" in n or "finger" in n) and "foot" not in n):
            out.append(o)
    return out


def foot_bones(objs):
    out = []
    for o in objs:
        n = base_name(o)
        if n in FOOT_CORE or "metatarsal bone" in n or ("phalanx" in n and ("foot" in n or "toe" in n)):
            out.append(o)
    return out


def object_center(o):
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


def group_center(objs):
    mn, mx = bounds(objs)
    return (mn + mx) / 2


def sampled_vertices(o, step=8):
    verts = []
    for i, v in enumerate(o.data.vertices):
        if i % step == 0:
            verts.append(o.matrix_world @ v.co)
    return verts or [object_center(o)]


def closest_mesh_pair(a, b, step_a=6, step_b=6):
    av = sampled_vertices(a, step_a)
    bv = sampled_vertices(b, step_b)
    best = None
    best_d = None
    for pa in av:
        for pb in bv:
            d = (pa - pb).length_squared
            if best_d is None or d < best_d:
                best_d = d
                best = (pa, pb)
    return best[0], best[1], math.sqrt(best_d)


def closest_object_pair(group_a, group_b, step=10):
    best = None
    best_d = None
    for a in group_a:
        for b in group_b:
            pa, pb, d = closest_mesh_pair(a, b, step, step)
            if best_d is None or d < best_d:
                best_d = d
                best = (a, b, pa, pb, d)
    if best is None:
        raise RuntimeError("No object pair found")
    return best


def nearest_objects(objs, target, n):
    return sorted(objs, key=lambda o: (object_center(o) - target).length)[:n]


def near_objects(objs, target, radius, max_n=None):
    ordered = sorted(objs, key=lambda o: (object_center(o) - target).length)
    selected = [o for o in ordered if (object_center(o) - target).length <= radius]
    if max_n:
        selected = selected[:max_n]
    return selected


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


def parent_group(objs, parent):
    for o in objs:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()


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
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32
    scene.render.film_transparent = False
    bpy.ops.object.light_add(type="AREA", location=(0, -4, 6))
    bpy.context.object.data.energy = 750
    bpy.context.object.data.size = 5
    bpy.ops.object.light_add(type="AREA", location=(4, 3, 4))
    bpy.context.object.data.energy = 220
    bpy.context.object.data.size = 6


def add_camera_framed(name, visible, view):
    mn, mx = bounds(visible)
    ctr = (mn + mx) / 2
    extent = mx - mn
    radius = max(extent.x, extent.y, extent.z, 1.0)
    if view == "front":
        direction = Vector((0, -1, 0.18)).normalized()
    elif view == "lateral":
        direction = Vector((1, -0.12, 0.15)).normalized()
    else:
        direction = Vector((1, -1, 0.35)).normalized()
    bpy.ops.object.camera_add(location=ctr + direction * radius * 3.2)
    cam = bpy.context.object
    cam.name = f"Camera_{name}"
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = radius * 1.18
    look_at(cam, ctr)
    bpy.context.scene.camera = cam


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


def write_manifest(objs, extra=None):
    groups = {
        "humerus": [o.name for o in exact(objs, "humerus")],
        "scapula": [o.name for o in exact(objs, "scapula")],
        "clavicle": [o.name for o in exact(objs, "clavicle")],
        "radius": [o.name for o in exact(objs, "radius")],
        "ulna": [o.name for o in exact(objs, "ulna")],
        "hand_bones": [o.name for o in hand_bones(objs)],
        "tibia": [o.name for o in exact(objs, "tibia")],
        "fibula": [o.name for o in exact(objs, "fibula")],
        "foot_bones": [o.name for o in foot_bones(objs)],
    }
    m = {"mesh_count": len(objs), "detected": groups, "selection_debug": extra or {}}
    (OUT / "model_manifest.json").write_text(json.dumps(m, indent=2))


def main():
    clean_scene()
    objs = import_model()
    setup_render()

    humeri = exact(objs, "humerus")
    scapulae = exact(objs, "scapula")
    clavicles = exact(objs, "clavicle")
    radii = exact(objs, "radius")
    ulnae = exact(objs, "ulna")
    if not (humeri and scapulae and clavicles and radii and ulnae):
        write_manifest(objs)
        raise RuntimeError("Missing exact upper-limb bones in complete GLB")

    humerus, scapula, h_contact, s_contact, hs_dist = closest_object_pair(humeri, scapulae, step=6)
    joint = (h_contact + s_contact) / 2
    clavicle = nearest_objects(clavicles, object_center(scapula), 1)[0]
    radius = nearest_objects(radii, object_center(humerus), 1)[0]
    ulna = nearest_objects(ulnae, object_center(radius), 1)[0]

    # Keep shoulder pilot conservative: humerus + radius + ulna only.
    # Hands were visually noisy in audit run 5 and are unnecessary for teaching glenohumeral motion.
    static_shoulder = [scapula, clavicle]
    moving_arm = [humerus, radius, ulna]
    visible = static_shoulder + moving_arm
    for o in static_shoulder:
        set_material(o, "Static_Bone", BONE)
    for o in moving_arm:
        set_material(o, "Moving_Bone", MOVING_BONE)
    set_visibility(visible)

    arm_parent = make_empty("Glenohumeral_contact_axis", joint)
    parent_group(moving_arm, arm_parent)

    key_rot(arm_parent, 1, (0, 0, 0))
    key_rot(arm_parent, 36, (math.radians(55), 0, 0))
    key_rot(arm_parent, 72, (0, 0, 0))
    render_clip("shoulder_flexion_from_complete_model", visible, "lateral")

    arm_parent.rotation_euler = (0, 0, 0)
    arm_parent.animation_data_clear()
    key_rot(arm_parent, 1, (0, 0, 0))
    key_rot(arm_parent, 36, (0, math.radians(-55), 0))
    key_rot(arm_parent, 72, (0, 0, 0))
    render_clip("shoulder_abduction_from_complete_model", visible, "front")

    tibiae = exact(objs, "tibia")
    tali = exact(objs, "talus")
    fibulae = exact(objs, "fibula")
    feet = foot_bones(objs)
    if not (tibiae and tali and fibulae and feet):
        write_manifest(objs, {"upper_selection": [o.name for o in visible]})
        raise RuntimeError("Missing exact ankle bones; refusing to fake ankle motion")

    tibia, talus, t_contact, ta_contact, tt_dist = closest_object_pair(tibiae, tali, step=8)
    fibula = nearest_objects(fibulae, object_center(tibia), 1)[0]
    foot_core = near_objects(feet, object_center(talus), radius=1.5, max_n=28)
    if talus not in foot_core:
        foot_core.insert(0, talus)
    visible_ankle = [tibia, fibula] + foot_core
    for o in [tibia, fibula]:
        set_material(o, "Static_Bone", BONE)
    for o in foot_core:
        set_material(o, "Moving_Foot", MOVING_BONE)
    set_visibility(visible_ankle)
    ankle_joint = (t_contact + ta_contact) / 2
    foot_parent = make_empty("Talocrural_contact_axis", ankle_joint)
    parent_group(foot_core, foot_parent)
    key_rot(foot_parent, 1, (0, 0, 0))
    key_rot(foot_parent, 36, (math.radians(18), 0, 0))
    key_rot(foot_parent, 72, (0, 0, 0))
    render_clip("ankle_dorsiflexion_from_complete_model", visible_ankle, "lateral")

    write_manifest(objs, {
        "upper_selection": [o.name for o in visible],
        "upper_contact_distance": hs_dist,
        "joint": list(joint),
        "ankle_selection": [o.name for o in visible_ankle],
        "ankle_contact_distance": tt_dist,
        "ankle_joint": list(ankle_joint),
    })


if __name__ == "__main__":
    main()
