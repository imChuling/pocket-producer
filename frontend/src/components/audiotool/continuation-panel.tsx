"use client";

import { useMemo, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { CandidateCard } from "@/components/audiotool/candidate-card";
import { SessionSummary } from "@/components/audiotool/session-summary";
import type { Fragment } from "@/types";
import type {
  ParsedIntent,
  RankResponse,
  RecommendationEvent,
  SessionFingerprint,
} from "@/types/audiotool";

export type PanelFeedback = {
  request_id: string;
  project_id: string;
  fragment_id: string;
  event: RecommendationEvent;
  rank_position: number;
  model_id: string;
};

type PanelStatus = "idle" | "loading" | "ready" | "error";

type Intensity = "nudge" | "suggest" | "explore";

const INTENSITY_CONFIG: Record<Intensity, { limit: number; label: string }> = {
  nudge: { limit: 1, label: "Nudge" },
  suggest: { limit: 3, label: "Suggest" },
  explore: { limit: 6, label: "Explore" },
};

const GRID_COLS: Record<Intensity, string> = {
  nudge: "md:grid-cols-1 max-w-sm",
  suggest: "md:grid-cols-3",
  explore: "md:grid-cols-3",
};

// Friendly labels for known model ids; unknown ids render as-is.
const MODEL_LABELS: Record<string, string> = {
  "rules-v1": "Rules",
  "fusion-5sig-v1": "Fusion",
  "recency-v1": "Recency",
  "text-only-v1": "Text",
  "audio-cosine-v1": "Audio",
  "mean-session-v1": "Session",
  "linear-v1": "Linear",
  "deepsets-v1": "DeepSets",
  "pocketrank-context-v1": "PocketRank",
};

export function ContinuationPanel({
  fingerprint,
  fragments,
  availableModels,
  requestRecommendations,
  onIntentChange,
  parsedIntent,
  onParsedIntentChange,
  onPreview,
  onInsert,
  onFeedback,
}: {
  fingerprint: SessionFingerprint;
  fragments: Fragment[];
  /** Model ids actually registered on the server (/ranking/model-card).
   * Absent or empty means only the guaranteed rules fallback is offered. */
  availableModels?: string[];
  requestRecommendations: (
    limit: number,
    modelId: string,
  ) => Promise<RankResponse>;
  onIntentChange: (intent: string) => void;
  /** User-approved LLM reading of the intent; rendered as removable chips. */
  parsedIntent?: ParsedIntent | null;
  onParsedIntentChange?: (parsed: ParsedIntent | null) => void;
  onPreview: (fragment: Fragment) => Promise<void> | void;
  onInsert: (fragment: Fragment) => Promise<void>;
  onFeedback: (feedback: PanelFeedback) => void;
}) {
  const [status, setStatus] = useState<PanelStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<RankResponse | null>(null);
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [intensity, setIntensity] = useState<Intensity>("suggest");
  // null = the user has not chosen; follow the server-side preference order.
  const [modelId, setModelId] = useState<string | null>(null);

  const modelOptions =
    availableModels && availableModels.length > 0
      ? availableModels
      : ["rules-v1"];
  // Default: the transparent rules baseline. The held-out evaluation
  // showed no stable fusion advantage over simpler rankers, so fusion
  // stays selectable but does not rank by default (Gate C decision).
  const defaultModel = "rules-v1";
  // If the server's model list no longer contains the selection (e.g. a
  // checkpoint was unloaded), requests go out as the guaranteed fallback.
  const selectedModel =
    modelId && modelOptions.includes(modelId) ? modelId : defaultModel;

  const fragmentsById = useMemo(() => {
    const map = new Map<string, Fragment>();
    for (const fragment of fragments) map.set(fragment._id, fragment);
    return map;
  }, [fragments]);

  async function suggest() {
    if (status === "loading") return;
    setStatus("loading");
    setError(null);
    try {
      const result = await requestRecommendations(
        INTENSITY_CONFIG[intensity].limit,
        selectedModel,
      );
      setResponse(result);
      setSkipped(new Set());
      setStatus("ready");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setStatus("error");
    }
  }

  function feedbackFor(
    fragmentId: string,
    event: RecommendationEvent,
  ): PanelFeedback | null {
    if (!response) return null;
    const position = response.candidates.findIndex(
      (candidate) => candidate.fragment_id === fragmentId,
    );
    if (position === -1) return null;
    return {
      request_id: response.request_id,
      project_id: fingerprint.project_id,
      fragment_id: fragmentId,
      event,
      rank_position: position + 1,
      model_id: response.model_id,
    };
  }

  function emit(fragmentId: string, event: RecommendationEvent) {
    const feedback = feedbackFor(fragmentId, event);
    if (feedback) onFeedback(feedback);
  }

  const visibleCandidates =
    response?.candidates.filter(
      (candidate) =>
        !skipped.has(candidate.fragment_id) &&
        fragmentsById.has(candidate.fragment_id),
    ) ?? [];

  const { limit, label } = INTENSITY_CONFIG[intensity];

  if (fragments.length === 0) {
    return (
      <div className="space-y-4">
        <SessionSummary
          fingerprint={fingerprint}
          onIntentChange={onIntentChange}
          parsedIntent={parsedIntent}
          onParsedIntentChange={onParsedIntentChange}
        />
        <p className="rounded-xl border border-chalk bg-powder p-6 text-center text-slate">
          No fragments in your library yet. Capture a few ideas first — then
          Pocket Producer can suggest what fits this session.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <SessionSummary
        fingerprint={fingerprint}
        onIntentChange={onIntentChange}
        parsedIntent={parsedIntent}
        onParsedIntentChange={onParsedIntentChange}
      />
      <div className="flex flex-wrap items-center gap-3">
        <div
          className="inline-flex rounded-lg border border-chalk"
          role="radiogroup"
          aria-label="Intervention intensity"
        >
          {(["nudge", "suggest", "explore"] as const).map((level) => (
            <button
              key={level}
              type="button"
              role="radio"
              aria-checked={intensity === level}
              onClick={() => setIntensity(level)}
              className={`px-3 py-1.5 text-sm first:rounded-l-lg last:rounded-r-lg ${
                intensity === level
                  ? "bg-obsidian text-white"
                  : "text-gravel hover:bg-powder"
              }`}
            >
              {INTENSITY_CONFIG[level].label}
            </button>
          ))}
        </div>
        <select
          value={selectedModel}
          onChange={(e) => setModelId(e.target.value)}
          className="rounded-lg border border-chalk bg-surface px-3 py-1.5 text-sm text-gravel"
          aria-label="Ranking model"
        >
          {modelOptions.map((id) => (
            <option key={id} value={id}>
              {MODEL_LABELS[id] ?? id}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => void suggest()}
          disabled={status === "loading"}
          className="inline-flex items-center gap-2 rounded-lg bg-obsidian px-4 py-2 text-sm font-medium text-white hover:bg-gravel disabled:opacity-60"
        >
          {status === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {response ? `${label} ${limit} again` : `${label} ${limit}`}
        </button>
        {response &&
          (response.fallback_used ? (
            <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs text-amber-800">
              Fallback to {response.model_id}
            </span>
          ) : (
            <span className="rounded-full border border-chalk bg-powder px-2.5 py-1 text-xs text-slate">
              Served by {response.model_id}
            </span>
          ))}
      </div>
      {status === "error" && (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          <p>Couldn&apos;t get suggestions: {error}</p>
          <button
            type="button"
            onClick={() => void suggest()}
            className="mt-2 rounded-lg border border-red-300 px-3 py-1.5 text-red-700 hover:bg-red-100"
          >
            Try again
          </button>
        </div>
      )}
      {status === "ready" && visibleCandidates.length === 0 && (
        <p className="text-sm text-slate">
          All suggestions were skipped. Ask again for a fresh set.
        </p>
      )}
      <div className={`grid gap-3 ${GRID_COLS[intensity]}`}>
        {visibleCandidates.map((candidate) => {
          const fragment = fragmentsById.get(candidate.fragment_id);
          if (!fragment) return null;
          return (
            <CandidateCard
              key={candidate.fragment_id}
              fragment={fragment}
              ranked={candidate}
              onPreview={async () => {
                emit(candidate.fragment_id, "preview");
                await onPreview(fragment);
              }}
              onInsert={async () => {
                await onInsert(fragment);
                emit(candidate.fragment_id, "insert");
              }}
              onSkip={() => {
                emit(candidate.fragment_id, "reject");
                setSkipped(
                  (previous) => new Set([...previous, candidate.fragment_id]),
                );
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
