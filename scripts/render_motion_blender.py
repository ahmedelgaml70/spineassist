"""
Blender script: build motion clips from a complete anatomy GLB.

Run:
  blender -b --python scripts/render_motion_blender.py
"""

import bpy
import math
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "body.glb"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

BG = (0.965, 0.952, 0.925)
BONE = (0.92, 0.86, 0.74, 1.0)


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


def name_l(o):
    return (o.name or "").lower()


def find_group(objs, include, exclude=()):
    found = []
    for o in objs:
        n = name_l(o)
        if any(w in n for w in include) and not any(w in n for w in exclude):
            found.append(o)
    return found


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


def bounds(objs):
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def center(objs):
    mn, mx = bounds(objs)
    return (mn + mx) / 2


def make_empty(name, loc):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.empty_display_type = "SPHERE"
    e.empty_display_size = 0.12
    e.location = loc
    return e


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 90
    scene.render.fps = 30
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.color = BG

    bpy.ops.object.light_add(type="AREA", location=(0, -4, 6))
    key = bpy.context.object
    key.data.energy = 650
    key.data.size = 5

    bpy.ops.object.light_add(type="AREA", location=(4, 3, 4))
    fill = bpy.context.object
    fill.data.energy = 180
    fill.data.size = 6


def add_camera(location, target, lens=70):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.data.lens = lens
    look_at(cam, target)
    bpy.context.scene.camera = cam
    return cam


def key_rot(obj, frame, rot):
    bpy.context.scene.frame_set(frame)
    obj.rotation_euler = rot
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def render_clip(name, camera_loc, camera_target):
    scene = bpy.context.scene
    add_camera(camera_loc, camera_target)
    scene.frame_set(45)
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


def manifest(objs):
    groups = {
        "humerus": ["humerus"],
        "scapula": ["scapula"],
        "clavicle": ["clavicle"],
        "radius": ["radius"],
        "ulna": ["ulna"],
        "hand": ["carpal", "metacarpal", "phal"],
        "tibia": ["tibia"],
        "fibula": ["fibula"],
        "foot": ["foot", "talus", "calcaneus", "metatars"]
    }
    m = {"mesh_count": len(objs), "sample_names": [o.name for o in objs[:400]], "detected": {}}
    for k, terms in groups.items():
        m["detected"][k] = [o.name for o in find_group(objs, terms)]
    (OUT / "model_manifest.json").write_text(json.dumps(m, indent=2))
    return m


def parent_group(objs, parent):
    for o in objs:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()


def right_side_filter(objs):
    return [o for o in objs if not any(x in name_l(o) for x in ["left", "_l", ".l", " l "])]


def main():
    clean_scene()
    objs = import_model()
    manifest(objs)
    setup_render()

    humerus = right_side_filter(find_group(objs, ["humerus"]))
    scapula = right_side_filter(find_group(objs, ["scapula"]))
    clavicle = right_side_filter(find_group(objs, ["clavicle"]))
    radius = right_side_filter(find_group(objs, ["radius"]))
    ulna = right_side_filter(find_group(objs, ["ulna"]))
    hand = right_side_filter(find_group(objs, ["carpal", "metacarpal", "phal"]))

    shoulder_static = scapula + clavicle
    moving_arm = humerus + radius + ulna + hand

    if not humerus or not shoulder_static:
        raise RuntimeError("Could not identify named humerus/scapula/clavicle meshes. Inspect outputs/model_manifest.json and adjust search terms.")

    for o in shoulder_static + moving_arm:
        set_material(o, "BoneWarm", BONE)

    set_visibility(shoulder_static + moving_arm)
    joint = center(scapula + clavicle)
    arm_parent = make_empty("GH_motion_parent", joint)
    parent_group(moving_arm, arm_parent)

    key_rot(arm_parent, 1, (0, 0, 0))
    key_rot(arm_parent, 45, (math.radians(75), 0, 0))
    key_rot(arm_parent, 90, (0, 0, 0))
    render_clip("shoulder_flexion_from_complete_model", (2.5, -4.0, 1.5), joint)

    arm_parent.rotation_euler = (0, 0, 0)
    arm_parent.animation_data_clear()
    key_rot(arm_parent, 1, (0, 0, 0))
    key_rot(arm_parent, 45, (0, math.radians(-75), 0))
    key_rot(arm_parent, 90, (0, 0, 0))
    render_clip("shoulder_abduction_from_complete_model", (0, -5.2, 1.6), joint)

    foot = right_side_filter(find_group(objs, ["foot", "talus", "calcaneus", "metatars"]))
    tibia = right_side_filter(find_group(objs, ["tibia"]))
    fibula = right_side_filter(find_group(objs, ["fibula"]))
    if foot and tibia:
        set_visibility(tibia + fibula + foot)
        for o in tibia + fibula + foot:
            set_material(o, "BoneWarm", BONE)
        ankle_joint = center(tibia + fibula)
        foot_parent = make_empty("Ankle_motion_parent", ankle_joint)
        parent_group(foot, foot_parent)
        key_rot(foot_parent, 1, (0, 0, 0))
        key_rot(foot_parent, 45, (math.radians(25), 0, 0))
        key_rot(foot_parent, 90, (0, 0, 0))
        render_clip("ankle_dorsiflexion_from_complete_model", (2.2, -3.5, 0.7), ankle_joint)


if __name__ == "__main__":
    main()
