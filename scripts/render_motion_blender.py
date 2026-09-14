"""
Render shoulder-motion teaching clips from the complete anatomy GLB.

Audit fix: the previous successful build proved the GLB/Blender pipeline works, but the
visual was not teaching-quality because it showed an isolated humerus plus a detached target
position. This version keeps nearby torso/shoulder bones as faint context, highlights scapula
and clavicle, animates only a duplicated humerus, removes the detached ghost, and adds a
native 3D arc so the motion reads as a purposeful undergraduate teaching visual.
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
CONTEXT_BONE = (0.82, 0.80, 0.75, 0.30)
STATIC_BONE = (0.94, 0.86, 0.68, 0.98)
MOVING_BONE = (1.0, 0.33, 0.18, 1.0)
ARC_BLUE = (0.08, 0.34, 0.90, 1.0)

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


def object_extent(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    ext = mx - mn
    return max(ext.x, ext.y, ext.z)


def sampled_vertices(obj, max_count=700):
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
            bonus = 0.0 if side_hint(h) == side_hint(s) else 0.18
            score = d + bonus
            if best is None or score < best["score"]:
                best = {"humerus": h, "scapula": s, "humerus_contact": hp, "scapula_contact": sp, "distance": d, "score": score}

    clavicle = min(clavicles, key=lambda c: (object_center(c) - object_center(best["scapula"])).length)
    best["clavicle"] = clavicle
    best["side_humerus"] = side_hint(best["humerus"])
    best["side_scapula"] = side_hint(best["scapula"])
    return best


def humeral_head_center(humerus, scapula_contact):
    pts = sampled_vertices(humerus, max_count=2600)
    ordered = sorted(pts, key=lambda p: (p - scapula_contact).length_squared)
    n = max(24, min(110, len(ordered) // 16))
    ctr = Vector((0, 0, 0))
    for p in ordered[:n]:
        ctr += p
    return ctr / n


def set_material(obj, name, rgba):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Alpha"].default_value = rgba[3]
        bsdf.inputs["Roughness"].default_value = 0.52
        bsdf.inputs["Metallic"].default_value = 0.0
    mat.blend_method = "BLEND" if rgba[3] < 1.0 else "OPAQUE"
    mat.show_transparent_back = True
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def set_visibility(visible):
    visible = set(visible)
    for o in bpy.context.scene.objects:
        if o.type == "MESH" or o.type == "CURVE":
            o.hide_render = o not in visible
            o.hide_viewport = o not in visible


def duplicate_mesh(obj, name):
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    dup.matrix_world = obj.matrix_world.copy()
    return dup


def make_empty(name, loc):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.empty_display_type = "SPHERE"
    e.empty_display_size = 0.06
    e.location = loc
    return e


def parent_to_empty(obj, parent):
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()


def bounds(objs):
    pts = []
    for o in objs:
        if o.type == "MESH":
            for c in o.bound_box:
                pts.append(o.matrix_world @ Vector(c))
    if not pts:
        raise RuntimeError("No bounds available")
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


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
    key = bpy.context.object
    key.data.energy = 700
    key.data.size = 5
    bpy.ops.object.light_add(type="AREA", location=(3.5, 2.5, 4))
    fill = bpy.context.object
    fill.data.energy = 220
    fill.data.size = 5


def make_arc(name, joint, radius, plane):
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = radius * 0.018
    curve.bevel_resolution = 4
    spl = curve.splines.new("POLY")
    spl.points.add(47)
    start = math.radians(7)
    end = math.radians(50)
    for i, p in enumerate(spl.points):
        a = start + (end - start) * i / 47
        if plane == "sagittal":
            co = (joint.x, joint.y + radius * math.sin(a), joint.z - radius * math.cos(a), 1)
        else:
            co = (joint.x + radius * math.sin(a), joint.y, joint.z - radius * math.cos(a), 1)
        p.co = co
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.get("Motion_Arc") or bpy.data.materials.new("Motion_Arc")
    mat.diffuse_color = ARC_BLUE
    curve.materials.append(mat)
    return obj


def nearby_context(objs, joint, chosen, radius):
    chosen_set = set(chosen)
    ctx = []
    for o in objs:
        if o in chosen_set:
            continue
        n = norm_name(o)
        if any(bad in n for bad in BAD_NAME_PARTS):
            continue
        c = object_center(o)
        if (c - joint).length <= radius:
            ctx.append(o)
    # Avoid losing the anatomic frame if the radius is too tight.
    for o in chosen:
        if o not in ctx:
            ctx.append(o)
    return ctx


def camera_for(name, visible_meshes, joint, view):
    bpy.context.view_layer.update()
    mn, mx = bounds(visible_meshes)
    ctr = (mn + mx) / 2
    # Bias focus toward the joint rather than the distal humerus to avoid empty backgrounds.
    focus = joint * 0.62 + ctr * 0.38
    ext = mx - mn
    max_extent = max(ext.x, ext.y, ext.z, 0.35)
    if view == "lateral":
        direction = Vector((1.0, -0.15, 0.08)).normalized()
    else:
        direction = Vector((0.05, -1.0, 0.08)).normalized()
    bpy.ops.object.camera_add(location=focus + direction * max_extent * 3.4)
    cam = bpy.context.object
    cam.name = "Camera_" + name
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max_extent * 1.18
    look_at(cam, focus)
    bpy.context.scene.camera = cam


def key_rot(obj, frame, rot):
    bpy.context.scene.frame_set(frame)
    obj.rotation_euler = rot
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def render_clip(name, humerus_source, scapula, clavicle, context, joint, view, plane, rot_mid):
    moving_humerus = duplicate_mesh(humerus_source, name + "_moving_humerus")
    set_material(moving_humerus, "Moving_Humerus", MOVING_BONE)
    for o in context:
        set_material(o, "Context_Bone", CONTEXT_BONE)
    for o in [scapula, clavicle]:
        set_material(o, "Static_Shoulder", STATIC_BONE)

    mover = make_empty(name + "_motion_parent", joint)
    parent_to_empty(moving_humerus, mover)
    key_rot(mover, 1, (0, 0, 0))
    key_rot(mover, 36, rot_mid)
    key_rot(mover, 72, (0, 0, 0))

    arc = make_arc(name + "_arc", joint, object_extent(humerus_source) * 0.72, plane)
    visible_meshes = [o for o in context if o is not humerus_source] + [moving_humerus]
    set_visibility(visible_meshes + [arc])
    camera_for(name, visible_meshes, joint, view)

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

    bpy.data.objects.remove(moving_humerus, do_unlink=True)
    bpy.data.objects.remove(mover, do_unlink=True)
    bpy.data.objects.remove(arc, do_unlink=True)


def write_manifest(objs, extra):
    m = {
        "mesh_count": len(objs),
        "detected_counts": {
            "humerus": len(find_bones(objs, "humerus")),
            "scapula": len(find_bones(objs, "scapula")),
            "clavicle": len(find_bones(objs, "clavicle")),
        },
        "selection_debug": extra,
        "quality_rule": "Uses complete body.glb mesh geometry; nearby shoulder/torso context is visible; no original GIFs, placeholders, or detached target ghost."
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

    radius = max(0.48, object_extent(humerus) * 1.05)
    context = nearby_context(objs, joint, [scapula, clavicle], radius)

    render_clip(
        "shoulder_flexion_from_complete_model",
        humerus, scapula, clavicle, context, joint,
        "lateral", "sagittal",
        (math.radians(42), 0, 0)
    )
    render_clip(
        "shoulder_abduction_from_complete_model",
        humerus, scapula, clavicle, context, joint,
        "front", "frontal",
        (0, math.radians(-42), 0)
    )

    write_manifest(objs, {
        "selected_humerus": humerus.name,
        "selected_scapula": scapula.name,
        "selected_clavicle": clavicle.name,
        "humerus_side_hint": selection["side_humerus"],
        "scapula_side_hint": selection["side_scapula"],
        "mesh_contact_distance": selection["distance"],
        "estimated_humeral_head_center": [joint.x, joint.y, joint.z],
        "nearby_context_meshes": len(context),
        "audit_note": "Revision removes the detached ghost render and adds shoulder/torso context so the moving humerus is no longer floating in empty space."
    })


if __name__ == "__main__":
    main()
