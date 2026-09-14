#!/usr/bin/env python3
"""Hard quality gate for generated anatomy PowerPoint artifacts.

This script is intentionally conservative: a green workflow should mean the deck contains
real Blender-derived anatomy media, not placeholders or copied GIFs. It validates the
manifest, rendered videos, poster images, and PPTX package before upload.
"""

import json
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

OUT = Path("outputs")
REQUIRED = [
    "anatomy_motion_pilot.pptx",
    "model_manifest.json",
    "shoulder_flexion_from_complete_model.mp4",
    "shoulder_abduction_from_complete_model.mp4",
    "shoulder_flexion_from_complete_model_poster.png",
    "shoulder_abduction_from_complete_model_poster.png",
]
BAD_TEXT = [
    "motion clip missing",
    "run blender render first",
    "placeholder",
    "missing render output",
    "reused gif",
]


def fail(message: str) -> None:
    raise SystemExit(f"AUDIT FAILED: {message}")


def file_size(path: Path) -> int:
    if not path.exists():
        fail(f"missing required file: {path}")
    return path.stat().st_size


def probe_video(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,nb_frames",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        data = json.loads(result.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
    except Exception as exc:
        fail(f"ffprobe could not inspect {path.name}: {exc}")
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    duration = float(stream.get("duration") or 0)
    if width < 900 or height < 500:
        fail(f"{path.name} resolution too small: {width}x{height}")
    if duration < 2.0:
        fail(f"{path.name} duration too short: {duration:.2f}s")
    return {"width": width, "height": height, "duration": duration, "bytes": path.stat().st_size}


def read_png_size(path: Path) -> tuple[int, int]:
    # Minimal PNG header parser; avoids adding Pillow as a dependency.
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        fail(f"{path.name} is not a PNG")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width < 900 or height < 500:
        fail(f"{path.name} poster resolution too small: {width}x{height}")
    return width, height


def audit_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("mesh_count", 0) < 500:
        fail("manifest mesh_count is too low for complete-model-derived output")
    counts = manifest.get("detected_counts") or {}
    for key in ["humerus", "scapula", "clavicle"]:
        if counts.get(key, 0) < 1:
            fail(f"manifest did not detect {key}")
    debug = manifest.get("selection_debug") or {}
    contact = float(debug.get("mesh_contact_distance", 999))
    if contact > 0.02:
        fail(f"humerus-scapula contact distance too high: {contact}")
    qa = manifest.get("pipeline_qa") or {}
    if not qa.get("hierarchy_contact_preserved"):
        fail("pipeline_qa.hierarchy_contact_preserved is not true")
    if float(qa.get("max_parenting_world_center_shift", 999)) > 1e-5:
        fail("parenting changed humerus world position")
    if float(qa.get("max_pivot_radius_error", 999)) > 1e-4:
        fail("pivot radius changed during animation")
    if float(qa.get("max_gh_contact_drift_ratio", 999)) > 0.25:
        fail("GH contact drift ratio is too high")
    return manifest


def audit_pptx(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        slides = [n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        media = [n for n in names if n.startswith("ppt/media/") and not n.endswith("/")]
        mp4s = [n for n in media if n.lower().endswith(".mp4")]
        if len(slides) < 4:
            fail(f"too few PPT slides: {len(slides)}")
        if len(mp4s) < 2:
            fail(f"PPTX embeds too few MP4 videos: {len(mp4s)}")
        text = "\n".join(zf.read(n).decode("utf-8", errors="ignore") for n in slides).lower()
        offenders = [s for s in BAD_TEXT if s in text]
        if offenders:
            fail(f"PPTX still contains forbidden placeholder text: {offenders}")
        return {"slides": len(slides), "media": len(media), "mp4s": len(mp4s)}


def main() -> None:
    summary = {"files": {}, "videos": {}, "posters": {}, "pptx": {}, "manifest": {}}
    for name in REQUIRED:
        path = OUT / name
        size = file_size(path)
        if size < 10_000:
            fail(f"{name} is suspiciously small: {size} bytes")
        summary["files"][name] = size

    manifest = audit_manifest(OUT / "model_manifest.json")
    summary["manifest"] = {
        "mesh_count": manifest.get("mesh_count"),
        "detected_counts": manifest.get("detected_counts"),
        "selection_debug": manifest.get("selection_debug"),
        "pipeline_qa": manifest.get("pipeline_qa"),
    }

    for name in ["shoulder_flexion_from_complete_model.mp4", "shoulder_abduction_from_complete_model.mp4"]:
        summary["videos"][name] = probe_video(OUT / name)

    for name in ["shoulder_flexion_from_complete_model_poster.png", "shoulder_abduction_from_complete_model_poster.png"]:
        w, h = read_png_size(OUT / name)
        summary["posters"][name] = {"width": w, "height": h, "bytes": (OUT / name).stat().st_size}

    summary["pptx"] = audit_pptx(OUT / "anatomy_motion_pilot.pptx")
    summary["verdict"] = "PASS: genuine complete-model-derived shoulder motion pilot; still requires human visual review before calling it teaching-final."
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
