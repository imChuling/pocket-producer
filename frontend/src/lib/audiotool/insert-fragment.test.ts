import { describe, expect, it, vi } from "vitest";

import { createOfflineDocument } from "@audiotool/nexus";
import { createDiskWasmLoader } from "@audiotool/nexus/node";
import { secondsToTicks } from "@audiotool/nexus/utils";

import {
  insertFragment,
  undoInsert,
  type InsertDeps,
} from "./insert-fragment";

const FRAGMENT = {
  fragmentId: "f1",
  title: "Night bass",
  durationSeconds: 4,
  bpm: 120,
};

function fakeUpload(overrides: Record<string, unknown> = {}) {
  return {
    name: "samples/test-sample",
    uploaded: Promise.resolve(undefined),
    ...overrides,
  };
}

async function offlineDocument() {
  return createOfflineDocument({ wasm: createDiskWasmLoader() });
}

describe("insertFragment", () => {
  it("modifies the document only after the sample upload is acknowledged", async () => {
    let resolveUploaded: (value: void | Error) => void = () => {};
    const uploaded = new Promise<void | Error>((resolve) => {
      resolveUploaded = resolve;
    });
    const upload = vi.fn(async () => fakeUpload({ uploaded }));
    const modify = vi.fn(async () => ({ receiptShell: true }));
    const pending = insertFragment(
      {
        samples: { upload },
        document: { modify } as unknown as InsertDeps["document"],
      },
      FRAGMENT,
      { audioBlob: new Blob(["x"]), playheadSeconds: 0, projectBpm: 120 },
    );
    await Promise.resolve();
    expect(upload).toHaveBeenCalledTimes(1);
    expect(modify).not.toHaveBeenCalled();
    resolveUploaded(undefined);
    await pending.catch(() => {});
    expect(modify).toHaveBeenCalledTimes(1);
  });

  it("does not touch the document when the upload fails", async () => {
    const upload = vi.fn(async () => new Error("upload rejected"));
    const modify = vi.fn();
    await expect(
      insertFragment(
        {
        samples: { upload },
        document: { modify } as unknown as InsertDeps["document"],
      },
        FRAGMENT,
        { audioBlob: new Blob(["x"]), playheadSeconds: 0, projectBpm: 120 },
      ),
    ).rejects.toThrow(/upload rejected/);
    expect(modify).not.toHaveBeenCalled();
  });

  it("does not touch the document when the upload acknowledgement errors", async () => {
    const upload = vi.fn(async () =>
      fakeUpload({ uploaded: Promise.resolve(new Error("network lost")) }),
    );
    const modify = vi.fn();
    await expect(
      insertFragment(
        {
        samples: { upload },
        document: { modify } as unknown as InsertDeps["document"],
      },
        FRAGMENT,
        { audioBlob: new Blob(["x"]), playheadSeconds: 0, projectBpm: 120 },
      ),
    ).rejects.toThrow(/network lost/);
    expect(modify).not.toHaveBeenCalled();
  });

  it("creates a region at the playhead in a real nexus document", async () => {
    const doc = await offlineDocument();
    const upload = vi.fn(async () => fakeUpload());
    const receipt = await insertFragment(
      { samples: { upload }, document: doc as unknown as InsertDeps["document"] },
      FRAGMENT,
      { audioBlob: new Blob(["x"]), playheadSeconds: 2, projectBpm: 120 },
    );
    const regions = doc.queryEntities.ofTypes("audioRegion").get();
    expect(regions).toHaveLength(1);
    expect(receipt.regionId).toBe(regions[0].id);
    expect(receipt.createdEntityIds.length).toBeGreaterThan(1);
    expect(receipt.insertedAtSeconds).toBe(2);
    const expectedTicks = Math.round(secondsToTicks(2, 120));
    expect(regions[0].fields.region.fields.positionTicks.value).toBe(
      expectedTicks,
    );
  }, 30000);

  it("undo removes exactly the entities the insert created", async () => {
    const doc = await offlineDocument();
    const idsBefore = new Set(doc.queryEntities.get().map((e) => e.id));
    const upload = vi.fn(async () => fakeUpload());
    const receipt = await insertFragment(
      { samples: { upload }, document: doc as unknown as InsertDeps["document"] },
      FRAGMENT,
      { audioBlob: new Blob(["x"]), playheadSeconds: 0, projectBpm: 120 },
    );
    expect(doc.queryEntities.get().length).toBeGreaterThan(idsBefore.size);
    await undoInsert(doc as unknown as InsertDeps["document"], receipt);
    const idsAfter = new Set(doc.queryEntities.get().map((e) => e.id));
    expect(idsAfter).toEqual(idsBefore);
  }, 30000);

  it("preserves a musician's copy and its playback routing when undoing the insert", async () => {
    const doc = await offlineDocument();
    const deps = {
      samples: { upload: async () => fakeUpload() },
      document: doc as unknown as InsertDeps["document"],
    };
    const receipt = await insertFragment(deps, FRAGMENT, {
      audioBlob: new Blob(["audio"]), playheadSeconds: 0, projectBpm: 120,
    });
    const region = doc.queryEntities.ofTypes("audioRegion").get()[0];
    const positionTicks = 8 * 3840;
    const copy = await doc.modify((t) => t.clone(region, { region: { positionTicks } }));
    const beforeUndo = new Set(doc.queryEntities.get().map((entity) => entity.id));
    beforeUndo.delete(region.id);

    await undoInsert(deps.document, receipt);

    const remaining = doc.queryEntities.ofTypes("audioRegion").get();
    expect(remaining.map((entity) => entity.id)).toEqual([copy.id]);
    expect(remaining[0].fields.region.fields.positionTicks.value).toBe(positionTicks);
    expect(new Set(doc.queryEntities.get().map((entity) => entity.id))).toEqual(beforeUndo);
  }, 30000);

  it("undo is idempotent when entities are already gone", async () => {
    const doc = await offlineDocument();
    const upload = vi.fn(async () => fakeUpload());
    const receipt = await insertFragment(
      { samples: { upload }, document: doc as unknown as InsertDeps["document"] },
      FRAGMENT,
      { audioBlob: new Blob(["x"]), playheadSeconds: 0, projectBpm: 120 },
    );
    await undoInsert(doc as unknown as InsertDeps["document"], receipt);
    await expect(undoInsert(doc as unknown as InsertDeps["document"], receipt)).resolves.toBeUndefined();
  }, 30000);

  it("surfaces transaction failures without a receipt", async () => {
    const upload = vi.fn(async () => fakeUpload());
    const modify = vi.fn(async () => {
      throw new Error("validation failed");
    });
    await expect(
      insertFragment(
        {
        samples: { upload },
        document: { modify } as unknown as InsertDeps["document"],
      },
        FRAGMENT,
        { audioBlob: new Blob(["x"]), playheadSeconds: 0, projectBpm: 120 },
      ),
    ).rejects.toThrow(/validation failed/);
  });
});
