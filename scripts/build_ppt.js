const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const outDir = path.join(__dirname, "..", "outputs");
const requiredMedia = [
  "shoulder_flexion_from_complete_model.mp4",
  "shoulder_abduction_from_complete_model.mp4",
  "shoulder_flexion_from_complete_model_poster.png",
  "shoulder_abduction_from_complete_model_poster.png",
  "model_manifest.json"
];
for (const file of requiredMedia) {
  if (!fs.existsSync(path.join(outDir, file))) {
    throw new Error(`Required 3D render output is missing: ${file}. Refusing to build placeholder deck.`);
  }
}

const manifest = JSON.parse(fs.readFileSync(path.join(outDir, "model_manifest.json"), "utf8"));
if (!manifest.pipeline_qa?.hierarchy_contact_preserved) {
  throw new Error("Anatomical transform/contact QA did not pass. Refusing to build the teaching deck.");
}

const ppt = new pptxgen();
ppt.layout = "LAYOUT_WIDE";
ppt.author = "Anatomy 3D teaching pipeline";
ppt.subject = "Validated isolated glenohumeral motion teaching pilot";
ppt.title = "Isolated Glenohumeral Motion — 3D Teaching Pilot";
ppt.company = "Generated from Z-Anatomy-derived complete GLB anatomy mesh";
ppt.theme = { headFontFace: "Aptos Display", bodyFontFace: "Aptos", lang: "en-US" };

const C = {
  bg: "F7F3EA", cream: "FBF8F1", navy: "17304F", text: "263647",
  muted: "6B7785", blue: "1C64D8", coral: "F16D4B", teal: "25A69A",
  line: "E9DED0", white: "FFFFFF", dark: "303234"
};

function footer(slide) {
  slide.addText("3D model: Z-Anatomy-derived body.glb (CC BY-SA 4.0). This pilot isolates GH motion; it does not simulate full shoulder-complex elevation.", {
    x: 0.45, y: 7.04, w: 12.4, h: 0.19, fontSize: 7.4, color: C.muted, margin: 0
  });
}

function header(slide, title, subtitle) {
  slide.background = { color: C.bg };
  slide.addText(title, { x: 0.5, y: 0.28, w: 12, h: 0.48, fontSize: 28, bold: true, color: C.navy, margin: 0 });
  slide.addText(subtitle, { x: 0.52, y: 0.84, w: 12, h: 0.3, fontSize: 12.5, color: C.muted, margin: 0 });
}

function pill(slide, text, x, y, w, color) {
  slide.addShape(ppt.ShapeType.roundRect, { x, y, w, h: 0.34, rectRadius: 0.1, fill: { color }, line: { color } });
  slide.addText(text, { x, y: y + 0.075, w, h: 0.14, fontSize: 9.2, bold: true, color: C.white, align: "center", margin: 0 });
}

function titleSlide() {
  const s = ppt.addSlide();
  s.background = { color: C.bg };
  s.addText("Isolated glenohumeral motion", { x: 0.7, y: 1.0, w: 11.7, h: 0.65, fontSize: 36, bold: true, color: C.navy, margin: 0 });
  s.addText("A validated 3D teaching pilot built from a complete anatomy mesh", { x: 0.72, y: 1.78, w: 9.7, h: 0.35, fontSize: 18, color: C.text, margin: 0 });
  s.addShape(ppt.ShapeType.roundRect, { x: 0.72, y: 2.55, w: 6.0, h: 1.65, rectRadius: 0.12, fill: { color: C.cream }, line: { color: C.line } });
  s.addText("What this pilot proves", { x: 1.0, y: 2.85, w: 3.2, h: 0.25, fontSize: 14, bold: true, color: C.coral, margin: 0 });
  s.addText("• real Blender-rendered model geometry\n• matched humerus–scapula–clavicle\n• hard transform and GH-contact QA\n• embedded MP4 motion, not a reused GIF", {
    x: 1.0, y: 3.18, w: 5.25, h: 0.82, fontSize: 14.5, color: C.text, breakLine: false, margin: 0
  });
  s.addShape(ppt.ShapeType.ellipse, { x: 8.3, y: 1.35, w: 2.9, h: 2.9, fill: { color: C.coral, transparency: 12 }, line: { color: C.coral, transparency: 100 } });
  s.addText("GH", { x: 8.3, y: 2.23, w: 2.9, h: 0.6, fontSize: 34, bold: true, color: C.white, align: "center", margin: 0 });
  s.addText("validation pilot", { x: 8.25, y: 4.55, w: 3.0, h: 0.3, fontSize: 15, bold: true, color: C.navy, align: "center", margin: 0 });
  footer(s);
}

function motionSlide({title, subtitle, baseName, plane, cue, muscles}) {
  const s = ppt.addSlide();
  header(s, title, subtitle);
  const poster = path.join(outDir, `${baseName}_poster.png`);
  const mp4 = path.join(outDir, `${baseName}.mp4`);

  // Keep the actual anatomy visible even in renderers that replace embedded video with a black play tile.
  s.addShape(ppt.ShapeType.roundRect, { x: 0.62, y: 1.35, w: 8.12, h: 5.35, rectRadius: 0.1, fill: { color: C.dark }, line: { color: C.line } });
  s.addImage({ path: poster, x: 0.7, y: 1.43, w: 7.96, h: 4.98 });
  s.addText("MID-RANGE MODEL VIEW", { x: 0.92, y: 6.12, w: 2.6, h: 0.2, fontSize: 8.5, bold: true, color: C.muted, margin: 0 });

  s.addText(plane, { x: 9.05, y: 1.34, w: 3.4, h: 0.28, fontSize: 14, bold: true, color: C.coral, margin: 0 });
  s.addText(cue, { x: 9.03, y: 1.92, w: 3.55, h: 1.5, fontSize: 17.5, color: C.text, fit: "shrink", margin: 0.02 });
  s.addText(muscles, { x: 9.03, y: 3.46, w: 3.55, h: 0.82, fontSize: 12.8, color: C.muted, fit: "shrink", margin: 0.02 });
  pill(s, "isolated GH motion", 9.03, 4.45, 2.8, C.teal);
  pill(s, "contact QA passed", 9.03, 4.89, 2.8, C.blue);

  s.addText("PLAY 2 s MOTION", { x: 9.03, y: 5.43, w: 2.8, h: 0.2, fontSize: 8.5, bold: true, color: C.muted, align: "center", margin: 0 });
  s.addMedia({ type: "video", path: mp4, x: 9.18, y: 5.67, w: 2.5, h: 1.25, poster });
  footer(s);
}

function auditSlide() {
  const d = manifest.selection_debug || {};
  const q = manifest.pipeline_qa || {};
  const gh = q.events?.gh_contact || [];
  const s = ppt.addSlide();
  header(s, "What has been validated — and what has not", "The model is now mechanically coherent enough for a teaching pilot, but its scope is deliberately narrow.");

  s.addText("Validated", { x: 0.75, y: 1.55, w: 2.5, h: 0.35, fontSize: 22, bold: true, color: C.teal, margin: 0 });
  s.addText(`Matched meshes: ${d.selected_humerus || "?"}, ${d.selected_scapula || "?"}, ${d.selected_clavicle || "?"}\nStart mesh contact: ${Number(d.mesh_contact_distance || 0).toFixed(4)} model units\nTransform displacement: ${Number(q.max_parenting_world_center_shift || 0).toExponential(2)}\nMax pivot radial error: ${Number(q.max_pivot_radius_error || 0).toExponential(2)}\nFlexion contact drift: ${gh[0] ? Number(gh[0].contact_distance_drift).toFixed(4) : "?"}\nAbduction contact drift: ${gh[1] ? Number(gh[1].contact_distance_drift).toFixed(4) : "?"}`, {
    x: 0.78, y: 2.05, w: 5.7, h: 2.2, fontSize: 15, color: C.text, margin: 0.02
  });

  s.addText("Not claimed", { x: 7.0, y: 1.55, w: 2.8, h: 0.35, fontSize: 22, bold: true, color: C.coral, margin: 0 });
  s.addText("• not a simulation of full shoulder elevation\n• no scapular upward rotation or clavicular motion is modeled\n• no muscle force or arthrokinematic roll–glide is being simulated\n• this is a visualization pilot, not a biomechanical research model", {
    x: 7.02, y: 2.05, w: 5.3, h: 1.9, fontSize: 15, color: C.text, margin: 0.02
  });

  s.addText("Teaching references", { x: 0.78, y: 4.8, w: 2.8, h: 0.3, fontSize: 15, bold: true, color: C.navy, margin: 0 });
  s.addText("Wuelker et al., J Shoulder Elbow Surg. 1995;4:462–468 (PMID 7552678): deltoid/supraspinatus force contributions vary with elevation angle.\nMcClure et al./in-vivo scapulohumeral literature: normal arm elevation includes coordinated glenohumeral and scapular motion; a fixed scapula therefore represents isolated GH motion, not whole-shoulder elevation.", {
    x: 0.78, y: 5.2, w: 11.4, h: 0.85, fontSize: 11.5, color: C.muted, margin: 0.02
  });
  footer(s);
}

titleSlide();
motionSlide({
  title: "Isolated glenohumeral flexion",
  subtitle: "The scapula and clavicle are intentionally fixed so students can isolate the humeral component.",
  baseName: "shoulder_flexion_from_complete_model",
  plane: "Sagittal-plane GH motion",
  cue: "The humerus moves anteriorly about the estimated humeral-head pivot. This clip isolates GH flexion; real arm elevation also includes shoulder-girdle motion.",
  muscles: "Major flexors include anterior deltoid and clavicular pectoralis major; coracobrachialis and biceps brachii can assist."
});
motionSlide({
  title: "Isolated glenohumeral abduction",
  subtitle: "The scapula and clavicle remain fixed references; this is not the complete scapulohumeral rhythm of arm elevation.",
  baseName: "shoulder_abduction_from_complete_model",
  plane: "Frontal-plane GH motion",
  cue: "The humerus moves away from the body midline while the modeled shoulder girdle remains fixed. Use this to identify the GH component only.",
  muscles: "Deltoid and supraspinatus both contribute to GH abduction; their relative mechanical contribution varies with elevation angle."
});
auditSlide();

ppt.writeFile({ fileName: path.join(outDir, "anatomy_motion_pilot.pptx") });
