import { describe, expect, it, vi } from "vitest";

import { describeSessionAudio, extractSessionAudio } from "./session-audio";
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
  };
}

describe("extractSessionAudio", () => {
  it("returns empty when document has no queryEntities", async () => {
    const doc = { start: vi.fn(), stop: vi.fn() } as unknown as NexusDocumentPort;
    const result = await extractSessionAudio(doc, { download: vi.fn() }, {
      backendUrl: "/embed",
      authToken: "tok",
    });
    expect(result.embeddings).toEqual([]);
    expect(result.sampleCount).toBe(0);
  });

  it("returns empty when there are no audio regions", async () => {
    const doc = fakeDocument([], []);
    const result = await extractSessionAudio(doc, { download: vi.fn() }, {
      backendUrl: "/embed",
      authToken: "tok",
    });
    expect(result.embeddings).toEqual([]);
  });

  it("resolves object-shaped entity references from the live SDK", async () => {
    const doc = fakeDocument(
      [{ id: "r1", sampleRef: { entityId: "s1" } }],
      [{ id: "s1", sampleName: "samples/uuid-1" }],
    );
    const download = vi.fn(async () => new Blob(["wav"]));
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ embeddings: [[0.1, 0.2]] }),
    }));
    vi.stubGlobal("fetch", fetchMock);
    try {
      const result = await extractSessionAudio(doc, { download }, {
        backendUrl: "/embed",
        authToken: "tok",
      });
      expect(download).toHaveBeenCalledWith("samples/uuid-1", { format: "wav" });
      expect(result.embeddings).toEqual([[0.1, 0.2]]);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("deduplicates samples referenced by multiple regions", async () => {
    const doc = fakeDocument(
      [
        { id: "r1", sampleRef: "s1" },
        { id: "r2", sampleRef: "s1" },
        { id: "r3", sampleRef: "s2" },
      ],
      [
        { id: "s1", sampleName: "samples/aaa" },
        { id: "s2", sampleName: "samples/bbb" },
      ],
    );
    const download = vi.fn(async () => new Blob(["wav"]));
    const fetchSpy = vi.fn(async () => ({
      ok: true,
      json: async () => ({ embeddings: [[1, 2], [3, 4]] }),
    }));
    vi.stubGlobal("fetch", fetchSpy);

    const result = await extractSessionAudio(doc, { download }, {
      backendUrl: "/embed",
      authToken: "tok",
    });

    expect(download).toHaveBeenCalledTimes(2);
    expect(download).toHaveBeenCalledWith("samples/aaa", { format: "wav" });
    expect(download).toHaveBeenCalledWith("samples/bbb", { format: "wav" });
    expect(result.embeddings).toEqual([[1, 2], [3, 4]]);
    expect(result.sampleCount).toBe(2);

    vi.unstubAllGlobals();
  });

  it("re-uses a complete result for the same sample set", async () => {
    const doc = fakeDocument(
      [{ id: "r1", sampleRef: "s1" }],
      [{ id: "s1", sampleName: "samples/aaa" }],
    );
    const download = vi.fn(async () => new Blob(["wav"]));
    const fetchSpy = vi.fn(async () => ({
      ok: true,
      json: async () => ({ embeddings: [[1, 2]], chroma: [[0.5]] }),
    }));
    vi.stubGlobal("fetch", fetchSpy);
    const cache = new Map();

    const first = await extractSessionAudio(doc, { download }, {
      backendUrl: "/embed",
      authToken: "tok",
      cache,
    });
    const second = await extractSessionAudio(doc, { download }, {
      backendUrl: "/embed",
      authToken: "tok",
      cache,
    });

    expect(download).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(second.embeddings).toEqual(first.embeddings);
    expect(second.chroma).toEqual(first.chroma);

    vi.unstubAllGlobals();
  });

  it("does not cache a partial encode", async () => {
    const doc = fakeDocument(
      [{ id: "r1", sampleRef: "s1" }],
      [{ id: "s1", sampleName: "samples/aaa" }],
    );
    const download = vi.fn(async () => new Blob(["wav"]));
    const fetchSpy = vi.fn(async () => ({
      ok: true,
      json: async () => ({ embeddings: [[1, 2]], timed_out: true }),
    }));
    vi.stubGlobal("fetch", fetchSpy);
    const cache = new Map();

    await extractSessionAudio(doc, { download }, { backendUrl: "/embed", authToken: "tok", cache });
    await extractSessionAudio(doc, { download }, { backendUrl: "/embed", authToken: "tok", cache });

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(cache.size).toBe(0);

    vi.unstubAllGlobals();
  });

  it("carries chroma, encode failures and timeout from the backend", async () => {
    const doc = fakeDocument(
      [{ id: "r1", sampleRef: "s1" }],
      [{ id: "s1", sampleName: "samples/aaa" }],
    );
    const download = vi.fn(async () => new Blob(["wav"]));
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          embeddings: [[1, 2]],
          chroma: [[0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0]],
          failed: [{ file: "b.wav", reason: "LibsndfileError" }],
          timed_out: true,
        }),
      })),
    );
    try {
      const result = await extractSessionAudio(doc, { download }, {
        backendUrl: "/embed",
        authToken: "tok",
      });
      expect(result.chroma).toHaveLength(1);
      expect(result.encodeFailures).toEqual([{ file: "b.wav", reason: "LibsndfileError" }]);
      expect(result.timedOut).toBe(true);
      expect(describeSessionAudio(result)).toMatch(/1 could not be encoded, encoding timed out/);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("surfaces a backend refusal as the reason for falling back", async () => {
    const doc = fakeDocument(
      [{ id: "r1", sampleRef: "s1" }],
      [{ id: "s1", sampleName: "samples/aaa" }],
    );
    const download = vi.fn(async () => new Blob(["wav"]));
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({ detail: "CLAP encoding is not enabled on this server" }),
      })),
    );
    try {
      const result = await extractSessionAudio(doc, { download }, {
        backendUrl: "/embed",
        authToken: "tok",
      });
      expect(result.embeddings).toEqual([]);
      expect(result.backendError).toBe("CLAP encoding is not enabled on this server");
      expect(describeSessionAudio(result)).toMatch(/not enabled/);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("counts download failures without crashing", async () => {
    const doc = fakeDocument(
      [{ id: "r1", sampleRef: "s1" }],
      [{ id: "s1", sampleName: "samples/aaa" }],
    );
    const download = vi.fn(async () => new Error("network"));

    const result = await extractSessionAudio(doc, { download }, {
      backendUrl: "/embed",
      authToken: "tok",
    });

    expect(result.failedCount).toBe(1);
    expect(result.sampleCount).toBe(0);
    expect(result.embeddings).toEqual([]);
  });
});
