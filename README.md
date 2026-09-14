# Anatomy PPT 3D Pipeline

This repository builds anatomy teaching PowerPoints from a **complete anatomy GLB model**, then isolates structures only when motion requires it.

## Workflow

1. Download a complete anatomy model (`body.glb`).
2. Inspect the model's object names.
3. Isolate the required anatomical structures inside Blender.
4. Render clean MP4 motion clips.
5. Embed those clips into a PowerPoint deck.

## Build locally

```bash
bash scripts/download_model.sh
blender -b --python scripts/render_motion_blender.py
npm install
node scripts/build_ppt.js
```

Output:

```text
outputs/anatomy_motion_pilot.pptx
```

## Build in GitHub Actions

Push this repo to GitHub, then run the **Build anatomy PPT** workflow. The workflow downloads the complete anatomy model during the build and uploads the finished PPTX as an artifact.

## Quality rule

If the complete model does not expose separable named anatomy objects, the render script should stop rather than produce misleading fake motion.
