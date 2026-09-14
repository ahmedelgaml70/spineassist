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

const ppt = new pptxgen();
ppt.layout = "LAYOUT_WIDE";
ppt.author = "Anatomy PPT 3D Pipeline";
ppt.subject = "3D anatomy motion teaching pilot";
ppt.title = "Shoulder Motion From Complete Anatomy Model";
ppt.company = "Generated from complete GLB anatomy mesh";

ppt.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US"
};

const C = {
  bg: "F7F3EA",
  cream: "FBF8F1",
  navy: "17304F",
  text: "263647",
  muted: "6B7785",
  blue: "1C64D8",
  coral: "F16D4B",
  teal: "25A69A",
  line: "E9DED0",
  white: "FFFFFF"
};

function footer(slide) {
  slide.addText("3D mesh source: complete body.glb anatomy model; derived output requires BodyParts3D/Z-Anatomy attribution in final distribution.", {
    x: 0.45, y: 7.05, w: 12.4, h: 0.18,
    fontSize: 7.5, color: C.muted, margin: 0
  });
}

function titleSlide() {
  const slide = ppt.addSlide();
  slide.background = { color: C.bg };
  slide.addText("Shoulder motion", {
    x: 0.65, y: 1.0, w: 11.8, h: 0.7,
    fontFace: "Aptos Display", fontSize: 38, bold: true, color: C.navy, margin: 0
  });
  slide.addText("Pilot generated from a complete 3D anatomy model — not reused GIFs, not placeholders.", {
    x: 0.68, y: 1.78, w: 10.8, h: 0.35,
    fontSize: 18, color: C.text, margin: 0
  });
  slide.addShape(ppt.ShapeType.roundRect, {
    x: 0.68, y: 2.55, w: 5.6, h: 1.15,
    rectRadius: 0.12,
    fill: { color: C.cream },
    line: { color: C.line }
  });
  slide.addText("Quality standard", {
    x: 0.95, y: 2.78, w: 2.4, h: 0.22,
    fontSize: 13, bold: true, color: C.coral, margin: 0
  });
  slide.addText("Large motion first. Minimal text. Real mesh-derived movement. Critique before scaling to the full deck.", {
    x: 0.95, y: 3.12, w: 4.95, h: 0.28,
    fontSize: 14, color: C.text, margin: 0
  });
  slide.addShape(ppt.ShapeType.rect, { x: 7.25, y: 1.05, w: 4.75, h: 4.7, fill: { color: C.coral, transparency: 18 }, line: { color: C.coral, transparency: 100 } });
  slide.addShape(ppt.ShapeType.arc, { x: 8.15, y: 1.75, w: 3.2, h: 2.2, adjustPoint: 0.35, line: { color: C.blue, width: 5, beginArrowType: "none", endArrowType: "triangle" } });
  slide.addText("Pilot v2", { x: 8.15, y: 4.45, w: 3.1, h: 0.35, fontSize: 20, bold: true, color: C.navy, align: "center", margin: 0 });
  footer(slide);
}

function addHeader(slide, title, subtitle) {
  slide.background = { color: C.bg };
  slide.addText(title, {
    x: 0.45, y: 0.28, w: 10.5, h: 0.48,
    fontFace: "Aptos Display", fontSize: 28, bold: true, color: C.navy, margin: 0
  });
  slide.addText(subtitle, {
    x: 0.48, y: 0.84, w: 10.8, h: 0.32,
    fontSize: 12.5, color: C.muted, margin: 0
  });
}

function addVideo(slide, baseName, x, y, w, h) {
  const mp4 = path.join(outDir, `${baseName}.mp4`);
  const poster = path.join(outDir, `${baseName}_poster.png`);
  slide.addShape(ppt.ShapeType.roundRect, {
    x: x - 0.08, y: y - 0.08, w: w + 0.16, h: h + 0.16,
    rectRadius: 0.12,
    fill: { color: C.cream },
    line: { color: C.line }
  });
  slide.addImage({ path: poster, x, y, w, h });
  slide.addMedia({ type: "video", path: mp4, x, y, w, h, poster });
}

function pill(slide, label, x, y, color) {
  slide.addShape(ppt.ShapeType.roundRect, {
    x, y, w: 2.65, h: 0.34,
    rectRadius: 0.12,
    fill: { color },
    line: { color }
  });
  slide.addText(label, { x, y: y + 0.08, w: 2.65, h: 0.12, fontSize: 9.5, bold: true, color: C.white, align: "center", margin: 0 });
}

function movementSlide({title, subtitle, baseName, movement, plane, teachingCue, muscleCue}) {
  const slide = ppt.addSlide();
  addHeader(slide, title, subtitle);
  addVideo(slide, baseName, 0.7, 1.45, 7.95, 5.1);

  slide.addText(movement, {
    x: 9.0, y: 1.30, w: 3.7, h: 0.55,
    fontSize: 27, bold: true, color: C.navy, margin: 0
  });
  slide.addText(plane, {
    x: 9.02, y: 1.93, w: 3.45, h: 0.28,
    fontSize: 14, bold: true, color: C.coral, margin: 0
  });
  slide.addText(teachingCue, {
    x: 9.0, y: 2.55, w: 3.45, h: 1.2,
    fontSize: 19, color: C.text, fit: "shrink", margin: 0.02
  });
  slide.addText(muscleCue, {
    x: 9.0, y: 3.78, w: 3.45, h: 0.62,
    fontSize: 13.5, color: C.muted, fit: "shrink", margin: 0.02
  });
  pill(slide, "real complete-model mesh", 9.0, 4.72, C.blue);
  pill(slide, "humeral-head pivot", 9.0, 5.20, C.teal);
  pill(slide, "poster + embedded MP4", 9.0, 5.68, C.coral);
  footer(slide);
}

titleSlide();

movementSlide({
  title: "Shoulder flexion",
  subtitle: "Close-up shoulder-only pilot: scapula/clavicle remain reference; humerus is the moving mesh.",
  baseName: "shoulder_flexion_from_complete_model",
  movement: "Flexion",
  plane: "Sagittal plane",
  teachingCue: "The humerus moves anteriorly from anatomical position. Students should track the humeral head, not just the distal arm.",
  muscleCue: "Primary contributors: anterior deltoid, clavicular pectoralis major, coracobrachialis, biceps brachii."
});

movementSlide({
  title: "Shoulder abduction",
  subtitle: "Same matched shoulder meshes; camera changes so students see movement away from the trunk.",
  baseName: "shoulder_abduction_from_complete_model",
  movement: "Abduction",
  plane: "Frontal plane",
  teachingCue: "The humerus moves away from the body midline. The scapula/clavicle provide the fixed comparison reference.",
  muscleCue: "Primary contributors: supraspinatus initiates; middle deltoid is dominant through most of the range."
});

const debug = manifest.selection_debug || {};
const slide = ppt.addSlide();
slide.background = { color: C.bg };
slide.addText("Audit notes for this pilot", { x: 0.55, y: 0.55, w: 11.2, h: 0.45, fontSize: 28, bold: true, color: C.navy, margin: 0 });
slide.addText(`Selected humerus: ${debug.selected_humerus || "unknown"}\nSelected scapula: ${debug.selected_scapula || "unknown"}\nSelected clavicle: ${debug.selected_clavicle || "unknown"}\nMesh contact distance: ${debug.mesh_contact_distance ?? "unknown"}\nNext critique: judge whether this shoulder-only render is visually teachable before adding elbow, wrist, ankle, and full deck styling.`, {
  x: 0.75, y: 1.45, w: 11.2, h: 2.0,
  fontSize: 18, color: C.text, breakLine: false, fit: "shrink", margin: 0.03
});
footer(slide);

ppt.writeFile({ fileName: path.join(outDir, "anatomy_motion_pilot.pptx") });
