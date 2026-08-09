// Stable frontend contract types. Field names mirror backend/ranking/schemas.py
// and must not be renamed independently.

export type SessionFingerprint = {
  project_id: string;
  bpm: number | null;
  key: string | null;
  playhead_seconds: number;
  track_count: number;
  active_track_types: string[];
  recent_entity_ids: string[];
  text_intent: string;
  /** Tags of fragments inserted this session; context for the fusion ranker. */
  context_tags?: string[];
  /** Server-populated when session region audio is available; never set by the browser. */
  region_audio_embeddings?: number[][] | null;
};

export type RecommendationEvent =
  | "preview"
  | "accept"
  | "reject"
  | "insert"
  | "undo";

export type RankEvidence = {
  code:
    | "tempo_match"
    | "key_match"
    | "track_gap"
    | "intent_match"
    | "novelty"
    | "recency"
    | "model_signal"
    | "role_gap_fill"
    | "harmonic_fit";
  label: string;
  contribution: number;
};

export type RankedCandidate = {
  fragment_id: string;
  score: number;
  evidence: RankEvidence[];
};

export type RankResponse = {
  request_id: string;
  model_id: string;
  fallback_used: boolean;
  candidates: RankedCandidate[];
};

export type AudiotoolStatus =
  | "idle"
  | "authorizing"
  | "connected"
  | "project-open"
  | "error";

export type ProjectSummary = {
  name: string;
  displayName: string;
};

/**
 * Structural ports over the parts of @audiotool/nexus we use.
 * Narrow on purpose: tests inject fakes, production adapts the real SDK.
 * OAuth tokens live inside the Nexus client only and are never exported
 * or sent to the Pocket Producer backend.
 */
export type NexusDocumentPort = {
  start: () => Promise<void>;
  stop: () => Promise<void>;
  /** Entity query surface of the real SyncedDocument; optional in fakes. */
  queryEntities?: unknown;
  dawUrl?: string;
};

export type NexusSamplesPort = {
  upload: (options: {
    file: Blob;
    displayName: string;
    bpm?: number;
  }) => Promise<{ name: string; uploaded: Promise<void | Error> } | Error>;
  download: (
    sample: string,
    options?: { format?: "flac" | "wav" | "mp3" | "preview" },
    signal?: AbortSignal,
  ) => Promise<Blob | Error>;
};

export type NexusClientPort = {
  userName: string;
  open: (project: string) => Promise<NexusDocumentPort>;
  listProjects: () => Promise<ProjectSummary[]>;
  samples?: NexusSamplesPort;
  logout?: () => void;
};

export type NexusAuthResult =
  | ({ status: "authenticated" } & NexusClientPort)
  | { status: "unauthenticated"; error?: Error };

/**
 * `interactive: false` means "use an existing session if there is one, but
 * never navigate the user away" — used to finish the OAuth redirect on mount.
 */
export type NexusAuthorize = (options?: {
  interactive?: boolean;
}) => Promise<NexusAuthResult>;

export type AudiotoolControllerState = {
  status: AudiotoolStatus;
  userName: string | null;
  projects: ProjectSummary[];
  openProjectName: string | null;
  error: string | null;
};
