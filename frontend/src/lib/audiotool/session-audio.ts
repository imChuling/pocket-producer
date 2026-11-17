// Extract unique audio samples from the open Nexus document and send them to
// the backend for CLAP encoding. Returns the resulting embeddings so the
// caller can populate SessionFingerprint.region_audio_embeddings.
//
// Audio blobs are read via the Nexus samples.download() API; audio never
// touches our backend in any other form. The backend receives raw WAV bytes,
// CLAP-encodes them, and returns float vectors. Deduplication is by sampleName
// so a sample used in multiple regions is only downloaded and encoded once.

import type { NexusDocumentPort, NexusSamplesPort, SessionBeats } from "@/types/audiotool";

type EntityLike = {
  id: string;
  entityType: string;
  fields: Record<string, { value?: unknown; fields?: Record<string, { value?: unknown }> } | undefined>;
};

/** Nexus timeline resolution: ticks in one quarter-note beat. */
const TICKS_PER_BEAT = 3840;

export type RegionPlacement = { start_beats: number; duration_beats: number | null };

/** Where a region sits on the timeline, in beats from zero; null if unreadable. */
function regionPlacement(region: EntityLike): RegionPlacement | null {
  const span = region.fields.region?.fields;
  const start = span?.positionTicks?.value;
  const duration = span?.durationTicks?.value;
  if (typeof start !== "number" || !Number.isFinite(start) || start < 0) return null;
  return {
    start_beats: start / TICKS_PER_BEAT,
    duration_beats:
      typeof duration === "number" && duration > 0 ? duration / TICKS_PER_BEAT : null,
  };
}

type QueryPort = {
  ofTypes: (...types: string[]) => { get: () => EntityLike[] };
};

export type SessionAudioResult = {
  embeddings: number[][];
  /** 12-dim chroma per encoded sample, aligned with `embeddings`. */
  chroma: number[][];
  sampleCount: number;
  /** Samples that could not be downloaded from Audiotool. */
  failedCount: number;
  /** Samples the backend could not decode or encode, with its reason. */
  encodeFailures: { file: string; reason: string }[];
  timedOut: boolean;
  /** Set when the backend refused outright (e.g. CLAP disabled, HTTP 503). */
  backendError: string | null;
  /** The session on its beat grid; null without a project tempo or region positions. */
  sessionBeats: SessionBeats | null;
};

const EMPTY: SessionAudioResult = {
  embeddings: [],
  chroma: [],
  sampleCount: 0,
  failedCount: 0,
  encodeFailures: [],
  timedOut: false,
  backendError: null,
  sessionBeats: null,
};

const MAX_SAMPLES = 8;

/**
 * Results keyed by the sorted set of sample names they were computed from.
 * A session whose regions did not change re-uses its vectors instead of
 * downloading and re-encoding up to eight samples on every request, which
 * also kept `/session-embed`'s 10/min allowance from being spent on repeats.
 */
export type SessionAudioCache = Map<string, SessionAudioResult>;

const CACHE_MAX_ENTRIES = 8;

export async function extractSessionAudio(
  document: NexusDocumentPort,
  samplesApi: { download: NexusSamplesPort["download"] },
  options: {
    backendUrl: string;
    authToken: string;
    signal?: AbortSignal;
    cache?: SessionAudioCache;
    /** Project tempo; with it the backend places regions on the beat grid. */
    bpm?: number | null;
  },
): Promise<SessionAudioResult> {
  const query = document.queryEntities as QueryPort | undefined;
  if (!query) {
    console.info("[session-audio] document has no queryEntities port");
    return { ...EMPTY };
  }

  const regions = query.ofTypes("audioRegion").get();
  if (regions.length === 0) {
    console.info("[session-audio] no audioRegion entities in document");
    return { ...EMPTY };
  }

  // Each audioRegion references a sample entity via the `sample` field.
  // The sample entity's `sampleName` field is the `samples/{uuid}` resource name.
  const sampleEntities = query.ofTypes("sample").get();
  const sampleNameById = new Map<string, string>();
  for (const entity of sampleEntities) {
    const name = entity.fields.sampleName?.value;
    if (typeof name === "string" && name) {
      sampleNameById.set(entity.id, name);
    }
  }

  // Deduplicate: collect unique sampleNames referenced by audioRegions.
  const seen = new Set<string>();
  const uniqueSampleNames: string[] = [];
  const placementsBySample = new Map<string, RegionPlacement[]>();
  for (const region of regions) {
    // The live Nexus SDK returns entity references as objects
    // ({ entityId, entityType }); older fixtures use plain string ids.
    const raw = region.fields.sample?.value;
    const sampleRef =
      typeof raw === "string"
        ? raw
        : typeof (raw as { entityId?: unknown })?.entityId === "string"
          ? (raw as { entityId: string }).entityId
          : null;
    if (!sampleRef) continue;
    const sampleName = sampleNameById.get(sampleRef);
    if (!sampleName) continue;
    const placement = regionPlacement(region);
    if (placement) {
      const list = placementsBySample.get(sampleName) ?? [];
      list.push(placement);
      placementsBySample.set(sampleName, list);
    }
    if (seen.has(sampleName)) continue;
    if (uniqueSampleNames.length >= MAX_SAMPLES) continue;
    seen.add(sampleName);
    uniqueSampleNames.push(sampleName);
  }
  const bpm =
    typeof options.bpm === "number" && Number.isFinite(options.bpm) && options.bpm > 0
      ? options.bpm
      : null;

  if (uniqueSampleNames.length === 0) {
    console.info(
      "[session-audio] no resolvable sample refs: " +
        `regions=${regions.length} sampleEntities=${sampleEntities.length} ` +
        `named=${sampleNameById.size}`,
    );
    console.info(
      "[session-audio] shapes: regionSampleField=",
      regions[0]?.fields.sample?.value,
      "sampleEntityId=",
      sampleEntities[0]?.id,
      "regionFieldKeys=",
      Object.keys(regions[0]?.fields ?? {}),
    );
    return { ...EMPTY };
  }

  // Moving a region or changing the tempo changes the beat data, not the vectors,
  // but both live in one result, so either invalidates it. Each sample keeps
  // its own placements in the key: sorting names on their own would let two
  // samples swap positions and still hit the old beat data.
  const cacheKey = JSON.stringify([
    bpm,
    [...uniqueSampleNames]
      .sort()
      .map((name) => [name, placementsBySample.get(name) ?? []]),
  ]);
  const cached = options.cache?.get(cacheKey);
  if (cached) {
    return {
      ...cached,
      embeddings: cached.embeddings.map((v) => [...v]),
      chroma: cached.chroma.map((v) => [...v]),
    };
  }

  // Download each sample as WAV and send to the backend for CLAP encoding.
  let failedCount = 0;
  const blobs: Blob[] = [];
  const names: string[] = [];
  for (const name of uniqueSampleNames) {
    try {
      const result = await samplesApi.download(name, { format: "wav" });
      if (result instanceof Error) {
        failedCount++;
        continue;
      }
      blobs.push(result);
      names.push(name);
    } catch {
      failedCount++;
    }
  }

  if (blobs.length === 0) {
    return { ...EMPTY, failedCount };
  }

  const formData = new FormData();
  for (let i = 0; i < blobs.length; i++) {
    formData.append("files", blobs[i], `${names[i].replace(/\//g, "_")}.wav`);
  }
  if (bpm !== null) {
    formData.append("bpm", String(bpm));
    formData.append(
      "placements",
      JSON.stringify(names.map((name) => placementsBySample.get(name) ?? [])),
    );
  }

  const response = await fetch(options.backendUrl, {
    method: "POST",
    headers: { Authorization: `Bearer ${options.authToken}` },
    body: formData,
    signal: options.signal,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep the status text
    }
    return { ...EMPTY, sampleCount: blobs.length, failedCount, backendError: detail };
  }

  const data = (await response.json()) as {
    embeddings: number[][];
    chroma?: number[][];
    failed?: { file: string; reason: string }[];
    timed_out?: boolean;
    session_beats?: SessionBeats | null;
  };
  const result: SessionAudioResult = {
    embeddings: data.embeddings,
    chroma: data.chroma ?? [],
    sampleCount: blobs.length,
    failedCount,
    encodeFailures: data.failed ?? [],
    timedOut: data.timed_out ?? false,
    backendError: null,
    sessionBeats: data.session_beats ?? null,
  };
  // Only a complete, successful encode is worth re-using; a partial one
  // should be retried next time.
  if (
    options.cache &&
    result.embeddings.length > 0 &&
    failedCount === 0 &&
    result.encodeFailures.length === 0 &&
    !result.timedOut
  ) {
    if (options.cache.size >= CACHE_MAX_ENTRIES) {
      const oldest = options.cache.keys().next().value;
      if (oldest !== undefined) options.cache.delete(oldest);
    }
    options.cache.set(cacheKey, result);
  }
  return result;
}

/** One-line explanation of why session audio may be missing, for the UI. */
export function describeSessionAudio(result: SessionAudioResult): string | null {
  if (result.backendError) return `Session audio unavailable: ${result.backendError}`;
  const parts: string[] = [];
  if (result.failedCount > 0) parts.push(`${result.failedCount} could not be downloaded`);
  if (result.encodeFailures.length > 0) parts.push(`${result.encodeFailures.length} could not be encoded`);
  if (result.timedOut) parts.push("encoding timed out");
  if (result.embeddings.length === 0 && result.sampleCount === 0 && parts.length === 0) {
    return "No audio regions in this session; audio-based rankers fall back to rules.";
  }
  if (parts.length === 0) return null;
  return `${result.embeddings.length}/${result.sampleCount + result.failedCount} session samples encoded (${parts.join(", ")}).`;
}
