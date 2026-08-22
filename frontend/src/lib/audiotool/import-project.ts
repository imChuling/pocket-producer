// Import the audio samples of an open Audiotool project into the user's
// fragment library. Each unique sample referenced by an audioRegion is
// downloaded via the Nexus samples.download() API and posted to the existing
// /api/ingest pipeline as a normal audio fragment, with a provenance note so
// the fragment is traceable back to its source project. No new backend
// surface: ingest, tagging, and CLAP embedding all reuse the standard path.

import type { NexusDocumentPort, NexusSamplesPort } from "@/types/audiotool";

type EntityLike = {
  id: string;
  entityType: string;
  fields: Record<string, { value: unknown } | undefined>;
};

type QueryPort = {
  ofTypes: (...types: string[]) => { get: () => EntityLike[] };
};

export type ProjectImportResult = {
  imported: number;
  failed: number;
  totalSamples: number;
};

// Matches the session-audio extraction cap and stays under the backend's
// 12/minute ingest rate limit.
const MAX_IMPORT_SAMPLES = 8;

export function listImportableSampleNames(
  document: NexusDocumentPort,
): string[] {
  const query = document.queryEntities as QueryPort | undefined;
  if (!query) return [];

  const regions = query.ofTypes("audioRegion").get();
  if (regions.length === 0) return [];

  const sampleNameById = new Map<string, string>();
  for (const entity of query.ofTypes("sample").get()) {
    const name = entity.fields.sampleName?.value;
    if (typeof name === "string" && name) {
      sampleNameById.set(entity.id, name);
    }
  }

  const seen = new Set<string>();
  const uniqueSampleNames: string[] = [];
  for (const region of regions) {
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
    if (uniqueSampleNames.length >= MAX_IMPORT_SAMPLES) break;
  }
  return uniqueSampleNames;
}

export async function importProjectAsFragments(
  document: NexusDocumentPort,
  samplesApi: { download: NexusSamplesPort["download"] },
  options: {
    projectDisplayName: string;
    getAuthToken: () => Promise<string>;
    onProgress?: (done: number, total: number) => void;
    signal?: AbortSignal;
  },
): Promise<ProjectImportResult> {
  const sampleNames = listImportableSampleNames(document);
  if (sampleNames.length === 0) {
    return { imported: 0, failed: 0, totalSamples: 0 };
  }

  let imported = 0;
  let failed = 0;
  for (const name of sampleNames) {
    options.signal?.throwIfAborted();
    try {
      const blob = await samplesApi.download(name, { format: "wav" });
      if (blob instanceof Error) {
        failed++;
        continue;
      }
      const shortName = name.replace(/\//g, "_");
      const formData = new FormData();
      formData.append("file", blob, `${shortName}.wav`);
      formData.append(
        "text",
        `Imported from Audiotool project "${options.projectDisplayName}" ` +
          `(sample ${shortName}).`,
      );
      const token = await options.getAuthToken();
      const response = await fetch("/api/ingest", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
        signal: options.signal,
      });
      if (response.ok) {
        imported++;
      } else {
        failed++;
      }
    } catch (cause) {
      if (options.signal?.aborted) throw cause;
      failed++;
    }
    options.onProgress?.(imported + failed, sampleNames.length);
  }

  return { imported, failed, totalSamples: sampleNames.length };
}
