// Client for the /api/ranking endpoints.
//
// Only the session fingerprint and candidate *metadata* are sent — audio
// bytes stay behind the protected fragment audio route, and no Audiotool
// OAuth material is ever included.

import { apiFetch, apiPost } from "@/lib/api";
import type { Fragment } from "@/types";
import type {
  ParsedIntent,
  RankResponse,
  RecommendationEvent,
  SessionFingerprint,
} from "@/types/audiotool";

type FragmentWithFeatures = Fragment & {
  audio_features?: { duration_sec?: number; tempo_bpm?: number };
  upload?: { duration_sec?: number };
};

export type CandidatePayload = {
  fragment_id: string;
  duration_seconds: number;
  bpm: number | null;
  key: string | null;
  tags: string[];
  created_at_iso: string;
  audio_url: string;
};

/**
 * Map library fragments to rank candidates. Fragments without real audio or
 * a measured duration are excluded rather than given invented values.
 */
export function toCandidates(fragments: Fragment[]): CandidatePayload[] {
  const candidates: CandidatePayload[] = [];
  for (const fragment of fragments as FragmentWithFeatures[]) {
    if (fragment.type !== "audio" || !fragment.audio_url) continue;
    const duration =
      fragment.audio_features?.duration_sec ?? fragment.upload?.duration_sec;
    if (typeof duration !== "number" || !(duration > 0)) continue;
    candidates.push({
      fragment_id: fragment._id,
      duration_seconds: duration,
      bpm: fragment.bpm ?? fragment.audio_features?.tempo_bpm ?? null,
      key: fragment.key ?? null,
      tags: fragment.tags ?? [],
      created_at_iso: fragment.created_at,
      audio_url: `/api/fragments/${fragment._id}/audio`,
    });
  }
  return candidates;
}

export type ModelCard = {
  id: string;
} & Record<string, unknown>;

/** Registered ranking models — drives the model selector so the UI never
 * advertises a model the server didn't actually load. */
export async function fetchModelCards(): Promise<{
  default: string;
  models: ModelCard[];
}> {
  return apiFetch("/ranking/model-card");
}

/**
 * Ask the server's LLM to read a free-text intent as structured fields.
 * Null means "no usable reading" — the caller degrades to raw-text
 * matching and the user never sees an error for it.
 */
export async function parseIntent(text: string): Promise<ParsedIntent | null> {
  const result = await apiPost<{ parsed: ParsedIntent | null }>(
    "/ranking/intent",
    { text },
  );
  return result.parsed;
}

export async function requestRecommendations(
  session: SessionFingerprint,
  fragments: Fragment[],
  options?: { modelId?: string; limit?: number },
): Promise<RankResponse> {
  return apiPost<RankResponse>("/ranking/rank", {
    session,
    candidates: toCandidates(fragments),
    model_id: options?.modelId ?? "rules-v1",
    limit: options?.limit ?? 3,
  });
}

export type FeedbackPayload = {
  request_id: string;
  project_id: string;
  fragment_id: string;
  event: RecommendationEvent;
  rank_position: number;
  model_id: string;
};

async function sendFeedback(payload: FeedbackPayload): Promise<void> {
  await apiPost("/ranking/feedback", payload);
}

// Feedback must never block creating: failed events queue locally and are
// retried in the background, in order. The queue is bounded (oldest events
// drop first), retries back off up to five minutes, and an event the server
// rejects outright (4xx other than 429) or that belongs to a signed-out
// session is dropped instead of blocking everything behind it.
const MAX_QUEUED_FEEDBACK = 200;
const RETRY_BASE_MS = 5_000;
const RETRY_MAX_MS = 5 * 60_000;
const feedbackQueue: FeedbackPayload[] = [];
let flushing = false;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let retryDelayMs = RETRY_BASE_MS;

function isPermanentFeedbackError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  if (message.startsWith("Not authenticated")) return true;
  const status = /^API (\d{3})/.exec(message);
  if (!status) return false;
  const code = Number(status[1]);
  return code >= 400 && code < 500 && code !== 429;
}

export function sendFeedbackQueued(payload: FeedbackPayload): void {
  if (feedbackQueue.length >= MAX_QUEUED_FEEDBACK) feedbackQueue.shift();
  feedbackQueue.push(payload);
  void flushFeedbackQueue();
}

async function flushFeedbackQueue(): Promise<void> {
  if (flushing) return;
  flushing = true;
  try {
    while (feedbackQueue.length > 0) {
      try {
        await sendFeedback(feedbackQueue[0]);
        feedbackQueue.shift();
        retryDelayMs = RETRY_BASE_MS;
      } catch (error) {
        if (isPermanentFeedbackError(error)) {
          feedbackQueue.shift();
          continue;
        }
        if (retryTimer === null) {
          retryTimer = setTimeout(() => {
            retryTimer = null;
            void flushFeedbackQueue();
          }, retryDelayMs);
          retryDelayMs = Math.min(retryDelayMs * 2, RETRY_MAX_MS);
        }
        return;
      }
    }
  } finally {
    flushing = false;
  }
}
