import { afterEach, describe, expect, it, vi } from "vitest";

import {
  importProjectAsFragments,
  listImportableSampleNames,
} from "./import-project";
import type { NexusDocumentPort } from "@/types/audiotool";

function fakeDocument(
  regions: { id: string; sampleRef: string | { entityId: string } }[],
  samples: { id: string; sampleName: string }[],
): NexusDocumentPort {
  const entities = [
    ...regions.map((r) => ({
      id: r.id,
      entityType: "audioRegion",
      fields: { sample: { value: r.sampleRef } },
    })),
    ...samples.map((s) => ({
      id: s.id,
      entityType: "sample",
      fields: { sampleName: { value: s.sampleName } },
    })),
  ];
  return {
    start: vi.fn(async () => {}),
    stop: vi.fn(async () => {}),
    queryEntities: {
      ofTypes: (...types: string[]) => ({
        get: () => entities.filter((e) => types.includes(e.entityType)),
      }),
    },
  } as unknown as NexusDocumentPort;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listImportableSampleNames", () => {
  it("returns empty for a document without queryEntities", () => {
    const doc = { start: vi.fn(), stop: vi.fn() } as unknown as NexusDocumentPort;
    expect(listImportableSampleNames(doc)).toEqual([]);
  });

  it("deduplicates samples referenced by multiple regions", () => {
    const doc = fakeDocument(
      [
        { id: "r1", sampleRef: { entityId: "s1" } },
        { id: "r2", sampleRef: { entityId: "s1" } },
        { id: "r3", sampleRef: "s2" },
      ],
      [
        { id: "s1", sampleName: "samples/uuid-1" },
        { id: "s2", sampleName: "samples/uuid-2" },
      ],
    );
    expect(listImportableSampleNames(doc)).toEqual([
      "samples/uuid-1",
      "samples/uuid-2",
    ]);
  });

  it("caps at eight samples to stay under the ingest rate limit", () => {
    const regions = Array.from({ length: 12 }, (_, i) => ({
      id: `r${i}`,
      sampleRef: `s${i}`,
    }));
    const samples = Array.from({ length: 12 }, (_, i) => ({
      id: `s${i}`,
      sampleName: `samples/uuid-${i}`,
    }));
    expect(listImportableSampleNames(fakeDocument(regions, samples))).toHaveLength(8);
  });
});

describe("importProjectAsFragments", () => {
  it("posts each downloaded sample to /api/ingest with a provenance note", async () => {
    const doc = fakeDocument(
      [
        { id: "r1", sampleRef: { entityId: "s1" } },
        { id: "r2", sampleRef: { entityId: "s2" } },
      ],
      [
        { id: "s1", sampleName: "samples/uuid-1" },
        { id: "s2", sampleName: "samples/uuid-2" },
      ],
    );
    const download = vi.fn(async () => new Blob(["wav"]));
    const fetchMock = vi.fn(async () => ({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const progress: [number, number][] = [];
    const result = await importProjectAsFragments(doc, { download }, {
      projectDisplayName: "Night Sketch",
      getAuthToken: async () => "tok",
      onProgress: (done, total) => progress.push([done, total]),
    });

    expect(result).toEqual({ imported: 2, failed: 0, totalSamples: 2 });
    expect(download).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      { headers: Record<string, string>; body: FormData },
    ];
    expect(url).toBe("/api/ingest");
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(init.body.get("text")).toContain('Audiotool project "Night Sketch"');
    // The ingest endpoint 415s on non-audio content types, so an untyped
    // Nexus blob must be re-wrapped as audio/wav before upload.
    const uploaded = init.body.get("file") as File;
    expect(uploaded.type).toBe("audio/wav");
    expect(uploaded.name).toBe("samples_uuid-1.wav");
    expect(progress).toEqual([
      [1, 2],
      [2, 2],
    ]);
  });

  it("counts failed downloads and failed uploads without aborting the rest", async () => {
    const doc = fakeDocument(
      [
        { id: "r1", sampleRef: "s1" },
        { id: "r2", sampleRef: "s2" },
        { id: "r3", sampleRef: "s3" },
      ],
      [
        { id: "s1", sampleName: "samples/uuid-1" },
        { id: "s2", sampleName: "samples/uuid-2" },
        { id: "s3", sampleName: "samples/uuid-3" },
      ],
    );
    const download = vi
      .fn()
      .mockResolvedValueOnce(new Error("gone"))
      .mockResolvedValue(new Blob(["wav"]));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    const result = await importProjectAsFragments(doc, { download }, {
      projectDisplayName: "Night Sketch",
      getAuthToken: async () => "tok",
    });

    expect(result).toEqual({ imported: 1, failed: 2, totalSamples: 3 });
  });

  it("returns zeros when the project has no importable samples", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const result = await importProjectAsFragments(
      fakeDocument([], []),
      { download: vi.fn() },
      { projectDisplayName: "Empty", getAuthToken: async () => "tok" },
    );
    expect(result).toEqual({ imported: 0, failed: 0, totalSamples: 0 });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
