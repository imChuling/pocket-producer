import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "/Users/lichuling/Desktop/GH/project/pocket-producer/artifacts/editable_figure1";
const C = {
  ink: "#20262B", muted: "#69727A", line: "#AAB2B9", white: "#FFFFFF",
  blue: "#477DC0", blueFill: "#E7F0F8", violet: "#65558F", violetFill: "#F0EAF5",
  rose: "#C9676D", roseFill: "#FBECEE", green: "#789B55", greenFill: "#EDF4E4",
  grayFill: "#F5F6F7", amber: "#ED9B69", amberFill: "#FFF1E7",
};

function text(slide, value, x, y, w, h, size, color = C.ink, bold = false, align = "center") {
  const s = slide.shapes.add({ geometry: "textbox", position: { left: x, top: y, width: w, height: h }, fill: "none", line: { style: "solid", fill: "none", width: 0 } });
  s.text = value;
  s.text.style = { fontSize: size, color, bold, align, verticalAlign: "middle" };
  return s;
}

function box(slide, name, title, sub, x, y, w, h, stroke, fill) {
  const s = slide.shapes.add({ geometry: "roundRect", name, position: { left: x, top: y, width: w, height: h }, fill, line: { style: "solid", fill: stroke, width: 2 }, borderRadius: 12, shadow: "1px 3px 8px #000000/10" });
  s.text = `${title}\n${sub}`;
  s.text.style = { fontSize: 17, color: C.ink, align: "center", verticalAlign: "middle" };
  return s;
}

function rightArrow(slide, x, y, w = 34, color = C.muted) {
  return slide.shapes.add({ geometry: "rightArrow", position: { left: x, top: y, width: w, height: 20 }, fill: color, line: { style: "solid", fill: color, width: 0 } });
}

function downArrow(slide, x, y, h = 35, color = C.muted) {
  return slide.shapes.add({ geometry: "downArrow", position: { left: x, top: y, width: 20, height: h }, fill: color, line: { style: "solid", fill: color, width: 0 } });
}
function upArrow(slide, x, y, h = 35, color = C.muted) {
  return slide.shapes.add({ geometry: "upArrow", position: { left: x, top: y, width: 20, height: h }, fill: color, line: { style: "solid", fill: color, width: 0 } });
}

async function writeBlob(path, blob) { await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer())); }

const deck = Presentation.create({ slideSize: { width: 1600, height: 900 } });
const slide = deck.slides.add();
slide.background.fill = C.white;

text(slide, "Pocket Producer: session-conditioned retrieval as a user-controlled proposal", 70, 34, 1460, 48, 30, C.ink, true, "left");
text(slide, "All boxes, labels, arrows, and panels are editable PowerPoint objects", 70, 82, 920, 28, 16, C.muted, false, "left");

// Main canvas and group lanes.
slide.shapes.add({ geometry: "roundRect", position: { left: 65, top: 125, width: 1470, height: 690 }, fill: C.white, line: { style: "solid", fill: C.line, width: 2 }, borderRadius: 16 });
slide.shapes.add({ geometry: "roundRect", position: { left: 90, top: 210, width: 365, height: 330 }, fill: C.blueFill, line: { style: "solid", fill: C.blue, width: 2 }, borderRadius: 14 });
slide.shapes.add({ geometry: "roundRect", position: { left: 470, top: 210, width: 610, height: 330 }, fill: C.violetFill, line: { style: "solid", fill: C.violet, width: 2 }, borderRadius: 14 });
slide.shapes.add({ geometry: "roundRect", position: { left: 1165, top: 210, width: 345, height: 330 }, fill: C.roseFill, line: { style: "solid", fill: C.rose, width: 2 }, borderRadius: 14 });
slide.shapes.add({ geometry: "roundRect", position: { left: 90, top: 575, width: 1420, height: 170 }, fill: C.greenFill, line: { style: "solid", fill: C.green, width: 2 }, borderRadius: 14 });

text(slide, "LIVE SESSION CONTEXT", 110, 225, 325, 28, 19, C.blue, true, "left");
text(slide, "SYSTEM PROPOSES", 495, 225, 565, 28, 19, C.violet, true, "left");
text(slide, "MUSICIAN DECIDES", 1190, 225, 300, 28, 19, C.rose, true, "left");
text(slide, "OFFLINE COLD-START TRAINING", 115, 592, 430, 26, 18, C.green, true, "left");
text(slide, "TRAINING PROXY — never a live-session input", 575, 592, 700, 26, 16, C.green, true, "left");

// Top design premise — a compact thesis banner for the three live lanes.
slide.shapes.add({ geometry: "roundRect", position: { left: 500, top: 140, width: 600, height: 48 }, fill: C.amberFill, line: { style: "solid", fill: C.amber, width: 2 }, borderRadius: 12 });
text(slide, "Similarity proposes; the musician decides what comes next", 520, 150, 560, 26, 17, C.ink, true);
downArrow(slide, 790, 188, 20, C.amber);

// Flow geometry is created before the boxes so it stays behind them.
rightArrow(slide, 252, 370, 30, C.blue);
rightArrow(slide, 432, 370, 30, C.violet);
rightArrow(slide, 612, 370, 30, C.violet);
rightArrow(slide, 792, 370, 30, C.violet);
rightArrow(slide, 972, 370, 30, C.violet);
rightArrow(slide, 1152, 370, 30, C.rose);
rightArrow(slide, 1332, 370, 30, C.rose);

rightArrow(slide, 335, 667, 34, C.green);
rightArrow(slide, 555, 667, 34, C.green);
rightArrow(slide, 775, 667, 34, C.green);
upArrow(slide, 890, 520, 50, C.green);
downArrow(slide, 1435, 530, 42, C.rose);

// Main live path: one horizontal baseline, no crossings.
box(slide, "audiotool", "Audiotool / Nexus", "tracks · regions · intent", 110, 325, 140, 110, C.blue, C.white);
box(slide, "fingerprint", "Session fingerprint", "tempo · CLAP · tags", 290, 325, 140, 110, C.blue, C.white);
box(slide, "candidate-library", "Candidate library", "audio fragments", 470, 325, 140, 110, C.violet, C.white);
box(slide, "signal-vector", "Five-signal vector", "φ(s,x) ∈ R⁵", 650, 325, 140, 110, C.violet, C.white);
box(slide, "ranker", "Ranker", "rules / selectable fusion", 830, 325, 140, 110, C.violet, C.white);
box(slide, "evidence", "Evidence", "per-signal rationale", 1010, 325, 140, 110, C.violet, C.white);
box(slide, "preview", "Preview", "audition before commit", 1190, 325, 140, 110, C.rose, C.white);
box(slide, "transaction", "Insert / undo", "reversible transaction", 1370, 325, 120, 110, C.rose, C.white);

// Decision boundary and fallback annotation.
slide.shapes.add({ geometry: "line", position: { left: 1160, top: 270, width: 0, height: 230 }, fill: "none", line: { style: "dash", fill: C.rose, width: 2 } });
text(slide, "proposal boundary", 1090, 492, 150, 22, 14, C.rose, false);
// These are scoped annotations, not free-floating claims: fallback belongs to
// the live-context lane; the signal list belongs to the ranker lane.
slide.shapes.add({ geometry: "roundRect", position: { left: 112, top: 458, width: 320, height: 34 }, fill: C.blueFill, line: { style: "dash", fill: C.blue, width: 1.5 }, borderRadius: 8 });
text(slide, "Fallback: no session audio → non-audio", 122, 462, 300, 24, 12, C.blue, true);
slide.shapes.add({ geometry: "roundRect", position: { left: 645, top: 458, width: 380, height: 34 }, fill: C.violetFill, line: { style: "dash", fill: C.violet, width: 1.5 }, borderRadius: 8 });
text(slide, "Ranker signals: cosine · tempo · key · tags · role", 655, 462, 360, 24, 13, C.violet, true);

// Offline training: weights sit directly below the ranker, so injection is vertical.
box(slide, "pack", "Pack co-membership", "positive proxy", 150, 635, 180, 72, C.green, C.white);
box(slide, "loo", "Leave-one-out pairs", "three negative regimes", 370, 635, 180, 72, C.green, C.white);
box(slide, "bpr", "Source-grouped BPR", "five-signal weights", 590, 635, 180, 72, C.green, C.white);
box(slide, "weights", "Export weights", "to selectable fusion", 810, 635, 180, 72, C.green, C.white);

// Feedback is deliberately outside the ranking path.
box(slide, "feedback", "Feedback log", "accept · reject · undo", 1310, 635, 165, 72, C.rose, C.white);
text(slide, "future personalization\n(not evaluated)", 1295, 720, 200, 42, 14, C.muted, false);

await fs.mkdir(OUT, { recursive: true });
await writeBlob(`${OUT}/editable-figure1-v2.png`, await deck.export({ slide, format: "png", scale: 1 }));
await fs.writeFile(`${OUT}/editable-figure1-v2.layout.json`, await (await slide.export({ format: "layout" })).text());
const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(`${OUT}/pocket-producer-figure1-editable-v2.pptx`);
console.log(`${OUT}/pocket-producer-figure1-editable-v2.pptx`);
