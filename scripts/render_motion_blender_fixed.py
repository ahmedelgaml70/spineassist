"""
Corrective entry point for the shoulder teaching render.

The imported GLB keeps a node hierarchy. A copied humerus therefore inherits transforms from
its original parent. Re-parenting that copy to an animation pivot can move it far from the
glenoid even when Blender completes successfully. This wrapper solves that at the geometry
level: it bakes the source humerus' evaluated world transform into a detached duplicate's mesh,
then animates that world-space mesh around the estimated GH pivot. Exact anatomical token
matching and hard transform QA remain enabled.
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

qa_events = {"duplicates": [], "parenting": []}


def exact_is_bone(obj, token):
    n = base.norm_name(obj)
    if any(bad in n for bad in base.BAD_NAME_PARTS):
        return False
    return re.search(rf"(^|\s){re.escape(token)}($|\s)", n) is not None


def duplicate_world_baked(obj, name):
    """Make a detached duplicate whose mesh vertices are already in model/world coordinates."""
    base.bpy.context.view_layer.update()
    source_center = base.object_center(obj)
    source_world = obj.matrix_world.copy()

    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    base.bpy.context.collection.objects.link(dup)

    # Remove every inherited transform source, then bake the evaluated source world matrix
    # directly into the mesh. From here on the object transform is identity and independent of
    # the GLB hierarchy.
    dup.parent = None
    dup.matrix_parent_inverse.identity()
    dup.data.transform(source_world)
    dup.data.update()
    dup.matrix_world = Matrix.Identity(4)
    base.bpy.context.view_layer.update()

    baked_center = base.object_center(dup)
    shift = (baked_center - source_center).length
    qa_events["duplicates"].append({
        "object": dup.name,
        "source_to_baked_center_shift": shift,
    })
    print(f"DUPLICATE_QA {dup.name}: source-to-baked center shift={shift:.9f}")
    if shift > 1e-5:
        raise RuntimeError(
            f"World-baking changed {dup.name} start position by {shift:.9f}; refusing bad anatomy render"
        )
    return dup


def parent_baked_world_mesh(obj, parent):
    """Attach an identity-transform, world-baked mesh to a pivot without changing its pose."""
    base.bpy.context.view_layer.update()
    before = base.object_center(obj)
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    base.bpy.context.view_layer.update()
    after = base.object_center(obj)
    shift = (after - before).length
    qa_events["parenting"].append({
        "object": obj.name,
        "world_center_shift": shift,
    })
    print(f"PARENT_QA {obj.name}: world-center shift={shift:.9f}")
    if shift > 1e-5:
        raise RuntimeError(
            f"Animation parenting displaced {obj.name} by {shift:.9f}; refusing detached shoulder motion"
        )


base.is_bone = exact_is_bone
base.duplicate_mesh = duplicate_world_baked
base.parent_to_empty = parent_baked_world_mesh
base.main()

manifest_path = base.OUT / "model_manifest.json"
manifest = json.loads(manifest_path.read_text())
max_duplicate_shift = max((e["source_to_baked_center_shift"] for e in qa_events["duplicates"]), default=0.0)
max_parent_shift = max((e["world_center_shift"] for e in qa_events["parenting"]), default=0.0)
passed = max_duplicate_shift <= 1e-5 and max_parent_shift <= 1e-5
manifest["pipeline_qa"] = {
    "fix_version": "world-baked-moving-mesh-v3",
    "hierarchy_contact_preserved": passed,
    "max_source_to_baked_center_shift": max_duplicate_shift,
    "max_parenting_world_center_shift": max_parent_shift,
    "events": qa_events,
    "bone_matching": "exact normalized token match",
    "motion_geometry": "detached duplicate with source matrix_world baked into mesh vertices"
}
manifest["selection_debug"]["corrective_change"] = (
    "Bake the selected humerus' world transform into a detached duplicate mesh before animation, "
    "then rotate that identity-transform geometry around the GH pivot; exact-token matching and "
    "hard transform QA prevent detached-bone output."
)
manifest_path.write_text(json.dumps(manifest, indent=2))

if not passed:
    raise RuntimeError("World-baked shoulder transform QA failed")
