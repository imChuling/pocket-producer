// Derive a stable, minimal SessionFingerprint from a Nexus document.
//
// Only information needed for ranking leaves the browser; the full Audiotool
// project is never uploaded. Fields the document does not provide (e.g. key
// signature) are reported as null — never guessed.

import type { SessionFingerprint } from "@/types/audiotool";

type FieldLike = { value: unknown } | undefined;

type EntityLike = {
  id: string;
  entityType: string;
  fields: Record<string, FieldLike>;
};

type QueryPort = {
  ofTypes: (...types: string[]) => { get: () => EntityLike[] };
};

export type FingerprintSource = {
  queryEntities: unknown;
};

const TRACK_TYPES = [
  "audioTrack",
  "noteTrack",
  "patternTrack",
  "automationTrack",
] as const;

const TRACK_LABEL: Record<(typeof TRACK_TYPES)[number], string> = {
  audioTrack: "audio",
  noteTrack: "note",
  patternTrack: "pattern",
  automationTrack: "automation",
};

export function fingerprintFromDocument(
  source: FingerprintSource,
  options: {
    projectId: string;
    playheadSeconds?: number;
    textIntent?: string;
    recentEntityIds?: string[];
  },
): SessionFingerprint {
  const query = source.queryEntities as QueryPort;
  const tracks = query
    .ofTypes(...TRACK_TYPES)
    .get()
    .filter((entity) => entity.entityType in TRACK_LABEL);
  const config = query.ofTypes("config").get()[0];

  const activeTypes = [
    ...new Set(
      tracks.map(
        (track) => TRACK_LABEL[track.entityType as (typeof TRACK_TYPES)[number]],
      ),
    ),
  ].sort();

  return {
    project_id: options.projectId,
    bpm: finiteOrNull(config?.fields.tempoBpm?.value),
    // Audiotool documents carry no key signature; never fabricate one.
    key: null,
    playhead_seconds: clampPlayhead(options.playheadSeconds),
    track_count: tracks.length,
    active_track_types: activeTypes,
    recent_entity_ids: uniqueSortedCapped(options.recentEntityIds ?? [], 20),
    text_intent: (options.textIntent ?? "").trim().slice(0, 240),
  };
}

function finiteOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function clampPlayhead(value: number | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return Math.max(0, value);
}

function uniqueSortedCapped(ids: string[], cap: number): string[] {
  return [...new Set(ids)].slice(0, cap).sort();
}
