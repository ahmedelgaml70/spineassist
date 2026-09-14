const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const outDir = path.join(__dirname, "..", "outputs");
const ppt = new pptxgen();
ppt.layout = "LAYOUT_WIDE";
ppt.author = "Anatomy PPT 3D Pipeline";
ppt.subject = "3D anatomy motion teaching pilot";
ppt.title = "3D Anatomy Motion Pilot";

ppt.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US"
};

const C = {
  bg: "F7F3EA",
  navy: "17304F",
  text: "263647",
  muted: "6B7785",
  blue: "1C64D8",
  coral: "F16D4B",
  teal: "25A69A",
  white: "FFFFFF"
};

function addTop(slide, title, subtitle) {
  slide.background = { color: C.bg };
  slide.addText(title, {
    x: 0.45, y: 0.28, w: 10.5, h: 0.48,
    fontFace: "Aptos Display", fontSize: 25, bold: true, color: C.navy, margin: 0
  });
  slide.addText(subtitle, {
    x: 0.48, y: 0.80, w: 10.8, h: 0.32,
    fontSize: 11.5, color: C.muted, margin: 0
  });
}

function addVideoOrPoster(slide, baseName, x, y, w, h) {
  const mp4 = path.join(outDir, `${baseName}.mp4`);
  const poster = path.join(outDir, `${baseName}_poster.png`);
  if (fs.existsSync(poster)) {
    slide.addImage({ path: poster, x, y, w, h });
  }
  if (fs.existsSync(mp4)) {
    slide.addMedia({ type: "video", path: mp4, x, y, w, h, poster });
  } else {
    slide.addText("Motion clip missing. Run Blender render first.", {
      x, y: y + h / 2 - 0.2, w, h: 0.4, fontSize: 16,
      color: C.coral, align: "center"
    });
  }
}

function cue(slide, label, text, x, y, color) {
  slide.addShape(ppt.ShapeType.roundRect, {
    x, y, w: 2.45, h: 0.54,
    rectRadius: 0.1,
    fill: { color },
    line: { color },
  });
  slide.addText(label, {
    x: x + 0.12, y: y + 0.08, w: 2.2, h: 0.16,
    fontSize: 11, bold: true, color: C.white, margin: 0
  });
  slide.addText(text, {
    x: x + 0.12, y: y + 0.28, w: 2.2, h: 0.16,
    fontSize: 8.5, color: C.white, margin: 0
  });
}

function makeSlide(title, subtitle, baseName, movement, plane, cueText) {
  const slide = ppt.addSlide();
  addTop(slide, title, subtitle);

  slide.addShape(ppt.ShapeType.roundRect, {
    x: 0.55, y: 1.25, w: 8.2, h: 5.55,
    rectRadius: 0.12,
    fill: { color: "FBF8F1" },
    line: { color: "E9DED0", transparency: 10 }
  });

  addVideoOrPoster(slide, baseName, 0.75, 1.45, 7.8, 5.05);

  slide.addText(movement, {
    x: 9.0, y: 1.32, w: 3.6, h: 0.55,
    fontSize: 24, bold: true, color: C.navy, margin: 0
  });

  slide.addText(plane, {
    x: 9.0, y: 1.90, w: 3.45, h: 0.35,
    fontSize: 13, bold: true, color: C.coral, margin: 0
  });

  slide.addText(cueText, {
    x: 9.0, y: 2.55, w: 3.4, h: 1.2,
    fontSize: 18, color: C.text,
    fit: "shrink",
    margin: 0.02
  });

  cue(slide, "Source", "complete anatomy GLB", 9.0, 4.25, C.blue);
  cue(slide, "Motion", "rendered from mesh", 9.0, 4.92, C.teal);
  cue(slide, "Design", "classroom scale", 9.0, 5.59, C.coral);
}

makeSlide(
  "Shoulder flexion",
  "Rendered from a complete anatomy model; structures are isolated only for motion.",
  "shoulder_flexion_from_complete_model",
  "Flexion",
  "Sagittal plane",
  "The arm moves anteriorly from anatomical position while the shoulder complex remains the reference."
);

makeSlide(
  "Shoulder abduction",
  "Same complete model source, different camera angle to clarify movement recognition.",
  "shoulder_abduction_from_complete_model",
  "Abduction",
  "Frontal plane",
  "The arm moves away from the trunk. Students should recognize the movement before reading the label."
);

makeSlide(
  "Ankle dorsiflexion",
  "Foot and leg structures are isolated from the complete model when named meshes are available.",
  "ankle_dorsiflexion_from_complete_model",
  "Dorsiflexion",
  "Sagittal plane",
  "The dorsum of the foot moves toward the anterior leg; the lateral camera clarifies the ankle angle."
);

ppt.writeFile({ fileName: path.join(outDir, "anatomy_motion_pilot.pptx") });
