import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "/Users/lichuling/Desktop/GH/project/pocket-producer/artifacts/editable_figure1";
const colors = {
  ink: "#20262B", muted: "#6E747B", blue: "#477DC0", blueFill: "#E7F0F8",
  violet: "#65558F", violetFill: "#F0EAF5", rose: "#C9676D", roseFill: "#FBECEE",
  green: "#789B55", greenFill: "#EDF4E4", grayFill: "#F1F3F4", white: "#FFFFFF",
};

function addText(slide, text, left, top, width, height, size, color = colors.ink, bold = false, align = "center") {
  const s = slide.shapes.add({ geometry: "textbox", position: { left, top, width, height }, fill: "none", line: { style: "solid", fill: "none", width: 0 } });
  s.text = text;
  s.text.style = { fontSize: size, color, bold, align, verticalAlign: "middle" };
  return s;
}

function addBox(slide, name, text, x, y, w, h, fill, line, size = 16) {
  const s = slide.shapes.add({ geometry: "roundRect", name, position: { left: x, top: y, width: w, height: h }, fill, line: { style: "solid", fill: line, width: 2 }, borderRadius: 10 });
  s.text = text;
  s.text.style = { fontSize: size, color: colors.ink, bold: false, align: "center", verticalAlign: "middle" };
  return s;
}

function addConnector(slide, from, to, color = colors.muted, dashed = false) {
  return slide.shapes.add({ geometry: "connector", kind: "straight", from, fromIdx: 3, to, toIdx: 1, line: { style: dashed ? "dash" : "solid", fill: color, width: 2 }, head: { type: "triangle", width: "med", length: "med" } });
}
function addRightwardConnector(slide, from, to, color = colors.muted) {
  return slide.shapes.add({ geometry: "connector", kind: "straight", from, fromIdx: 1, to, toIdx: 3, line: { style: "solid", fill: color, width: 2 } });
}

async function writeBlob(path, blob) { await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer())); }

const deck = Presentation.create({ slideSize: { width: 1600, height: 900 } });
const slide = deck.slides.add();
slide.background.fill = colors.white;

addText(slide, "Pocket Producer — editable Figure 1", 80, 34, 900, 42, 28, colors.ink, true, "left");
addText(slide, "Drag any box, label, or connector in PowerPoint", 80, 78, 800, 28, 16, colors.muted, false, "left");

// Frames first. They are intentionally flat and spacious so the user can edit them.
slide.shapes.add({ geometry: "roundRect", name: "outer-frame", position: { left: 70, top: 130, width: 1460, height: 650 }, fill: colors.white, line: { style: "solid", fill: colors.muted, width: 2 }, borderRadius: 16 });
slide.shapes.add({ geometry: "roundRect", name: "why-frame", position: { left: 95, top: 200, width: 250, height: 440 }, fill: colors.grayFill, line: { style: "solid", fill: colors.muted, width: 2 }, borderRadius: 14 });
slide.shapes.add({ geometry: "roundRect", name: "live-frame", position: { left: 370, top: 200, width: 300, height: 440 }, fill: colors.blueFill, line: { style: "solid", fill: colors.blue, width: 2 }, borderRadius: 14 });
slide.shapes.add({ geometry: "roundRect", name: "score-frame", position: { left: 695, top: 200, width: 420, height: 440 }, fill: colors.violetFill, line: { style: "solid", fill: colors.violet, width: 2 }, borderRadius: 14 });
slide.shapes.add({ geometry: "roundRect", name: "decide-frame", position: { left: 1140, top: 200, width: 360, height: 440 }, fill: colors.roseFill, line: { style: "solid", fill: colors.rose, width: 2 }, borderRadius: 14 });
slide.shapes.add({ geometry: "roundRect", name: "offline-frame", position: { left: 370, top: 670, width: 1130, height: 82 }, fill: colors.greenFill, line: { style: "solid", fill: colors.green, width: 2 }, borderRadius: 14 });

addText(slide, "WHY SIMILARITY FAILS", 110, 164, 220, 28, 17, colors.muted, true);
addText(slide, "LIVE SESSION", 390, 164, 260, 28, 17, colors.blue, true);
addText(slide, "PROPOSAL GENERATION", 715, 164, 380, 28, 17, colors.violet, true);
addText(slide, "MUSICIAN DECIDES", 1160, 164, 320, 28, 17, colors.rose, true);
addText(slide, "OFFLINE COLD-START SUPERVISION — not a live session signal", 395, 682, 600, 25, 16, colors.green, true, "left");

const why1 = addBox(slide, "why-audio", "Audio match\n≠ continuation", 120, 245, 200, 80, colors.white, colors.muted, 17);
const why2 = addBox(slide, "why-proxy", "Pack membership\nis only a proxy", 120, 355, 200, 80, colors.white, colors.muted, 17);
const why3 = addBox(slide, "why-design", "Therefore: inspect\npreview · undo", 120, 465, 200, 80, colors.white, colors.muted, 17);

const daw = addBox(slide, "daw", "Audiotool / Nexus\ntracks · regions · intent", 410, 245, 220, 80, colors.white, colors.blue, 16);
const finger = addBox(slide, "fingerprint", "Session fingerprint\ntempo · CLAP · tags", 410, 355, 220, 80, colors.white, colors.blue, 16);
const fallback = addBox(slide, "fallback", "Fallback\nnon-audio rules", 410, 465, 220, 80, colors.white, colors.blue, 16);

const candidates = addBox(slide, "candidate-library", "Candidate\nlibrary", 735, 250, 150, 78, colors.white, colors.violet, 16);
const vector = addBox(slide, "signal-vector", "Five-signal vector\ncosine · tempo · key · tags · role", 915, 250, 170, 78, colors.white, colors.violet, 14);
const evidence = addBox(slide, "evidence", "Evidence chips\nper-signal rationale", 735, 390, 150, 78, colors.white, colors.violet, 15);
const ranker = addBox(slide, "ranker", "Ranker\nrules / fusion", 915, 390, 170, 78, colors.white, colors.violet, 16);
addText(slide, "φ(s,x) ∈ R⁵", 780, 505, 290, 30, 17, colors.violet, true);

const inspect = addBox(slide, "inspect", "Inspect\nper-signal rationale", 1180, 245, 280, 78, colors.white, colors.rose, 16);
const preview = addBox(slide, "preview", "Preview / audition\nbefore commit", 1180, 365, 280, 78, colors.white, colors.rose, 16);
const txn = addBox(slide, "transaction", "Insert / undo\nreversible transaction", 1180, 485, 280, 78, colors.white, colors.rose, 16);
addText(slide, "feedback logged", 1360, 590, 120, 24, 14, colors.muted, false);

const pack = addBox(slide, "pack-membership", "Pack\nco-membership", 430, 705, 190, 42, colors.white, colors.green, 14);
const loo = addBox(slide, "loo-pairs", "LOO pairs", 665, 705, 190, 42, colors.white, colors.green, 14);
const bpr = addBox(slide, "bpr", "Source-grouped BPR", 900, 705, 210, 42, colors.white, colors.green, 14);
const weights = addBox(slide, "weights", "Export weights", 1155, 705, 190, 42, colors.white, colors.green, 14);

// Connectors are added after frames but remain behind the editable node shapes in the export.
addConnector(slide, why1, why2);
addConnector(slide, why2, why3);
addConnector(slide, why3, daw, colors.muted, true);
addConnector(slide, daw, finger, colors.blue);
addConnector(slide, finger, fallback, colors.blue);
addConnector(slide, finger, vector, colors.blue);
addConnector(slide, candidates, vector, colors.violet);
addConnector(slide, vector, ranker, colors.violet);
addConnector(slide, ranker, evidence, colors.violet);
addConnector(slide, ranker, inspect, colors.rose);
addConnector(slide, inspect, preview, colors.rose);
addConnector(slide, preview, txn, colors.rose);
addRightwardConnector(slide, pack, loo, colors.green);
addRightwardConnector(slide, loo, bpr, colors.green);
addRightwardConnector(slide, bpr, weights, colors.green);
addText(slide, "→", 625, 711, 34, 25, 18, colors.green, true);
addText(slide, "→", 860, 711, 34, 25, 18, colors.green, true);
addText(slide, "→", 1120, 711, 34, 25, 18, colors.green, true);
addConnector(slide, weights, ranker, colors.green, true);

addText(slide, "All elements on this slide are editable PowerPoint shapes.", 80, 825, 700, 28, 14, colors.muted, false, "left");

await fs.mkdir(OUT, { recursive: true });
await writeBlob(`${OUT}/editable-figure1.png`, await deck.export({ slide, format: "png", scale: 1 }));
await fs.writeFile(`${OUT}/editable-figure1.layout.json`, await (await slide.export({ format: "layout" })).text());
const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(`${OUT}/pocket-producer-figure1-editable.pptx`);
console.log(`${OUT}/pocket-producer-figure1-editable.pptx`);
