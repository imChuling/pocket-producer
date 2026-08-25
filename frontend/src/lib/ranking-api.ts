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
// retried in the background, in order.
const feedbackQueue: FeedbackPayload[] = [];
let flushing = false;
let retryTimer: ReturnType<typeof setTimeout> | null = null;

export function sendFeedbackQueued(payload: FeedbackPayload): void {
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
      } catch {
        if (retryTimer === null) {
          retryTimer = setTimeout(() => {
            retryTimer = null;
            void flushFeedbackQueue();
          }, 5000);
        }
        return;
      }
    }
  } finally {
    flushing = false;
  }
}
