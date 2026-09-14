"""
Corrective entry point for the shoulder teaching render.

The source GLB retains a node hierarchy. The base renderer previously re-parented an imported
mesh by changing parent/matrix_parent_inverse without first preserving matrix_world. That can
teleport a copied humerus away from its glenoid even though Blender renders successfully.
This wrapper preserves world space explicitly, uses exact bone-token matching, records the
measured parenting shift, and makes the manifest/build fail if hierarchy preservation regresses.
"""

import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("anatomy_render_base", HERE / "render_motion_blender.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

parent_events = []


def exact_is_bone(obj, token):
    n = base.norm_name(obj)
    if any(bad in n for bad in base.BAD_NAME_PARTS):
        return False
    return re.search(rf"(^|\s){re.escape(token)}($|\s)", n) is not None


def parent_preserve_world(obj, parent):
    world_before = obj.matrix_world.copy()
    center_before = base.object_center(obj)

    obj.parent = parent
    obj.matrix_parent_inverse.identity()
    obj.matrix_world = world_before
    base.bpy.context.view_layer.update()

    center_after = base.object_center(obj)
    shift = (center_after - center_before).length
    parent_events.append({"object": obj.name, "world_center_shift": shift})
    print(f"PARENT_QA {obj.name}: world-center shift={shift:.9f}")
    if shift > 1e-5:
        raise RuntimeError(
            f"Re-parenting displaced {obj.name} by {shift:.9f}; refusing to render anatomically detached motion"
        )


base.is_bone = exact_is_bone
base.parent_to_empty = parent_preserve_world
base.main()

manifest_path = base.OUT / "model_manifest.json"
manifest = json.loads(manifest_path.read_text())
max_shift = max((e["world_center_shift"] for e in parent_events), default=0.0)
manifest["pipeline_qa"] = {
    "fix_version": "preserve-imported-world-transform-v2",
    "hierarchy_contact_preserved": max_shift <= 1e-5,
    "max_parenting_world_center_shift": max_shift,
    "parent_events": parent_events,
    "bone_matching": "exact normalized token match"
}
manifest["selection_debug"]["corrective_change"] = (
    "Preserve matrix_world across animation re-parenting; exact-token shoulder-bone matching; "
    "hard-fail if parenting moves the mesh in world space."
)
manifest_path.write_text(json.dumps(manifest, indent=2))

if max_shift > 1e-5:
    raise RuntimeError("Parenting world-transform QA failed")
