// Extract unique audio samples from the open Nexus document and send them to
// the backend for CLAP encoding. Returns the resulting embeddings so the
// caller can populate SessionFingerprint.region_audio_embeddings.
//
// Audio blobs are read via the Nexus samples.download() API — audio never
// touches our backend in any other form. The backend receives raw WAV bytes,
// CLAP-encodes them, and returns float vectors. Deduplication is by sampleName
// so a sample used in multiple regions is only downloaded and encoded once.

import type { NexusDocumentPort, NexusSamplesPort } from "@/types/audiotool";

type EntityLike = {
  id: string;
  entityType: string;
  fields: Record<string, { value: unknown } | undefined>;
};

type QueryPort = {
  ofTypes: (...types: string[]) => { get: () => EntityLike[] };
};

export type SessionAudioResult = {
  embeddings: number[][];
  sampleCount: number;
  failedCount: number;
};

const MAX_SAMPLES = 8;

export async function extractSessionAudio(
  document: NexusDocumentPort,
  samplesApi: { download: NexusSamplesPort["download"] },
  options: {
    backendUrl: string;
    authToken: string;
    signal?: AbortSignal;
  },
): Promise<SessionAudioResult> {
  const query = document.queryEntities as QueryPort | undefined;
  if (!query) {
    console.info("[session-audio] document has no queryEntities port");
    return { embeddings: [], sampleCount: 0, failedCount: 0 };
  }

  const regions = query.ofTypes("audioRegion").get();
  if (regions.length === 0) {
    console.info("[session-audio] no audioRegion entities in document");
    return { embeddings: [], sampleCount: 0, failedCount: 0 };
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
    if (!sampleName || seen.has(sampleName)) continue;
    seen.add(sampleName);
    uniqueSampleNames.push(sampleName);
    if (uniqueSampleNames.length >= MAX_SAMPLES) break;
  }

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
    return { embeddings: [], sampleCount: 0, failedCount: 0 };
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
    return { embeddings: [], sampleCount: 0, failedCount };
  }

  const formData = new FormData();
  for (let i = 0; i < blobs.length; i++) {
    formData.append("files", blobs[i], `${names[i].replace(/\//g, "_")}.wav`);
  }

  const response = await fetch(options.backendUrl, {
    method: "POST",
    headers: { Authorization: `Bearer ${options.authToken}` },
    body: formData,
    signal: options.signal,
  });

  if (!response.ok) {
    return { embeddings: [], sampleCount: blobs.length, failedCount };
  }

  const data = (await response.json()) as { embeddings: number[][] };
  return {
    embeddings: data.embeddings,
    sampleCount: blobs.length,
    failedCount,
  };
}
