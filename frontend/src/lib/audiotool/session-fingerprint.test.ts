import { describe, expect, it } from "vitest";

import { createOfflineDocument, type OfflineDocument } from "@audiotool/nexus";
import { createDiskWasmLoader } from "@audiotool/nexus/node";

import { fingerprintFromDocument } from "./session-fingerprint";

async function emptyDocument(): Promise<OfflineDocument> {
  return createOfflineDocument({ wasm: createDiskWasmLoader() });
}

async function documentWithTracks(order: "audio-first" | "note-first") {
  const doc = await emptyDocument();
  await doc.modify((t) => {
    const device = t.create("audioDevice", { displayName: "Player" });
    const synth = t.create("heisenberg", {});
    if (order === "audio-first") {
      t.create("audioTrack", { player: device.location, orderAmongTracks: 1 });
      t.create("noteTrack", { player: synth.location, orderAmongTracks: 2 });
    } else {
      t.create("noteTrack", { player: synth.location, orderAmongTracks: 1 });
      t.create("audioTrack", { player: device.location, orderAmongTracks: 2 });
    }
  });
  return doc;
}

describe("fingerprintFromDocument", () => {
  it("is deterministic across entity creation order", async () => {
    const first = await documentWithTracks("audio-first");
    const second = await documentWithTracks("note-first");
    const a = fingerprintFromDocument(first, { projectId: "p1" });
    const b = fingerprintFromDocument(second, { projectId: "p1" });
    expect(a).toEqual(b);
  }, 30000);

  it("reads real track counts and types from a nexus document", async () => {
    const doc = await documentWithTracks("audio-first");
    const fingerprint = fingerprintFromDocument(doc, { projectId: "p1" });
    expect(fingerprint.track_count).toBe(2);
    expect(fingerprint.active_track_types).toEqual(["audio", "note"]);
  }, 30000);

  it("reports missing tempo as null instead of inventing one", async () => {
    const doc = await emptyDocument();
    const fingerprint = fingerprintFromDocument(doc, { projectId: "p1" });
    expect(fingerprint.bpm).toBeNull();
    expect(fingerprint.key).toBeNull();
    expect(fingerprint.track_count).toBe(0);
    expect(fingerprint.active_track_types).toEqual([]);
  }, 30000);

  it("clamps playhead, trims intent, caps recent entity ids", async () => {
    const doc = await emptyDocument();
    const fingerprint = fingerprintFromDocument(doc, {
      projectId: "p1",
      playheadSeconds: Number.NaN,
      textIntent: `  ${"x".repeat(500)}  `,
      recentEntityIds: Array.from({ length: 30 }, (_, i) => `e${29 - i}`),
    });
    expect(fingerprint.playhead_seconds).toBe(0);
    expect(fingerprint.text_intent).toHaveLength(240);
    expect(fingerprint.recent_entity_ids).toHaveLength(20);
    const sorted = [...fingerprint.recent_entity_ids].sort();
    expect(fingerprint.recent_entity_ids).toEqual(sorted);
  }, 30000);

  it("ignores negative playhead values", async () => {
    const doc = await emptyDocument();
    const fingerprint = fingerprintFromDocument(doc, {
      projectId: "p1",
      playheadSeconds: -12,
    });
    expect(fingerprint.playhead_seconds).toBe(0);
  }, 30000);

  it("only reports fields the document actually provides", async () => {
    const doc = await emptyDocument();
    const fingerprint = fingerprintFromDocument(doc, { projectId: "p1" });
    // Nexus documents have no key signature concept; it must never be faked.
    expect(fingerprint.key).toBeNull();
  }, 30000);
});
