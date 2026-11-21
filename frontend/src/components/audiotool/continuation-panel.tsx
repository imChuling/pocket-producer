"use client";

import { useMemo, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { CandidateCard } from "@/components/audiotool/candidate-card";
import { SessionSummary } from "@/components/audiotool/session-summary";
import { toCandidates, type FeedbackPayload } from "@/lib/ranking-api";
import type { Fragment } from "@/types";
import type {
  ParsedIntent,
  RankResponse,
  RecommendationEvent,
  SessionFingerprint,
} from "@/types/audiotool";

export type PanelFeedback = FeedbackPayload;

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
  "harmonic-fit-v1": "Harmonic fit",
  "beat-fit-v1": "Beat fit",
  "recency-v1": "Recency",
  "text-only-v1": "Text",
  "audio-cosine-v1": "Audio",
  "mean-session-v1": "Session",
  "role-gap-v1": "Role gap",
  "linear-v1": "Linear",
  "deepsets-v1": "DeepSets",
  "pocketrank-context-v1": "PocketRank",
};

type PanelProps = {
  libraryPage?: string | null;
  libraryReady?: boolean;
  mutationPending?: boolean;
  fingerprint: SessionFingerprint;
  intentText?: string;
  fragments: Fragment[];
  /** Model ids actually registered on the server (/ranking/model-card).
   * Absent or empty means only the guaranteed rules fallback is offered. */
  availableModels?: string[];
  requestRecommendations: (
    limit: number,
    modelId: string,
    skipped: ReadonlySet<string>,
  ) => Promise<RankResponse>;
  onIntentChange: (intent: string) => void;
  /** Why session audio may be missing; explains a fallback to rules. */
  sessionAudioNote?: string | null;
  /** User-approved LLM reading of the intent; rendered as removable chips. */
  parsedIntent?: ParsedIntent | null;
  onParsedIntentChange?: (parsed: ParsedIntent | null) => void;
  onPreview: (fragment: Fragment) => Promise<void> | void;
  onInsert: (fragment: Fragment, feedback: PanelFeedback) => Promise<string | void>;
  onFeedback: (feedback: PanelFeedback) => void;
};

export function ContinuationPanel(props: PanelProps) {
  const [intensity, setIntensity] = useState<Intensity>("suggest");
  const [modelId, setModelId] = useState<string | null>(null);
  const scope = JSON.stringify([props.fingerprint.project_id, props.fingerprint.text_intent]);
  const [history, setHistory] = useState(() => ({ scope, edit: 0, skipped: new Set<string>() }));
  if (history.scope !== scope) {
    setHistory({ scope, edit: 0, skipped: new Set() });
  }

  return (
    <div className="space-y-4">
      <SessionSummary
        fingerprint={props.fingerprint}
        intentText={props.intentText ?? props.fingerprint.text_intent}
        onIntentChange={props.onIntentChange}
        parsedIntent={props.parsedIntent}
        onParsedIntentChange={props.onParsedIntentChange}
        onEditInterpretation={() => setHistory({ scope, edit: history.edit + 1, skipped: new Set() })}
      />
      {props.libraryReady !== false && (
        <Suggestions
          key={JSON.stringify([scope, history.edit, props.libraryPage])}
          {...props}
          skipped={history.skipped}
          setSkipped={(skipped) => setHistory({ ...history, skipped })}
          intensity={intensity}
          setIntensity={setIntensity}
          modelId={modelId}
          setModelId={setModelId}
        />
      )}
    </div>
  );
}

function Suggestions({
  fingerprint, fragments, availableModels, requestRecommendations, sessionAudioNote,
  onPreview, onInsert, onFeedback, mutationPending, intensity, setIntensity, modelId, setModelId,
  skipped, setSkipped,
}: PanelProps & {
  skipped: ReadonlySet<string>;
  setSkipped: (ids: Set<string>) => void;
  intensity: Intensity;
  setIntensity: (level: Intensity) => void;
  modelId: string | null;
  setModelId: (id: string) => void;
}) {
  const [status, setStatus] = useState<PanelStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<RankResponse | null>(null);

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
  const playable = useMemo(() => toCandidates(fragments), [fragments]);

  async function suggest(excluded = skipped) {
    if (status === "loading") return;
    setStatus("loading");
    setError(null);
    try {
      const result = await requestRecommendations(
        INTENSITY_CONFIG[intensity].limit,
        selectedModel,
        excluded,
      );
      setResponse(result);
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
  const allSkipped = playable.length > 0 && playable.every(candidate => skipped.has(candidate.fragment_id));

  if (fragments.length === 0) {
    return (
      <p className="rounded-xl border border-chalk bg-powder p-6 text-center text-slate">
        No fragments in your library yet. Capture a few ideas first, then
        Pocket Producer can suggest what fits this session.
      </p>
    );
  }
  if (playable.length === 0) {
    return <p className="text-sm text-slate">No playable sketches on this page.</p>;
  }

  return (
    <div className="space-y-4">
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
          disabled={status === "loading" || allSkipped}
          className="inline-flex items-center gap-2 rounded-lg bg-obsidian px-4 py-2 text-sm font-medium text-white hover:bg-gravel disabled:opacity-60"
        >
          {status === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {response ? `${label} ${limit} again` : `${label} ${limit}`}
        </button>
        {skipped.size > 0 && (
          <button
            type="button"
            disabled={status === "loading"}
            onClick={() => {
              const reset = new Set<string>();
              setSkipped(reset);
              void suggest(reset);
            }}
            className="text-sm text-slate underline underline-offset-2 hover:text-gravel disabled:opacity-60"
          >
            Include skipped sketches
          </button>
        )}
        {response &&
          (response.fallback_used ? (
            <span
              title={sessionAudioNote ?? undefined}
              className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs text-amber-800"
            >
              Fallback to {response.model_id}
            </span>
          ) : (
            <span className="rounded-full border border-chalk bg-powder px-2.5 py-1 text-xs text-slate">
              Served by {response.model_id}
            </span>
          ))}
      </div>
      {response?.fallback_used && sessionAudioNote && (
        <p className="text-xs text-amber-800">{sessionAudioNote}</p>
      )}
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
      {(allSkipped || (status === "ready" && visibleCandidates.length === 0)) && (
        <p role="status" className="text-sm text-slate">
          {allSkipped
            ? "You’ve skipped every playable sketch on this page."
            : response?.candidates.length
              ? "Ask again for more suggestions."
              : "No suggestions available on this page."}
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
              insertDisabled={mutationPending}
              onPreview={async () => {
                emit(candidate.fragment_id, "preview");
                await onPreview(fragment);
              }}
              onInsert={async () => {
                const feedback = feedbackFor(candidate.fragment_id, "insert");
                if (!feedback) return;
                // The choice is logged even if the upload or SDK write fails.
                onFeedback({ ...feedback, event: "accept" });
                const insertionId = await onInsert(fragment, feedback);
                onFeedback(insertionId ? { ...feedback, insertion_id: insertionId } : feedback);
              }}
              onSkip={() => {
                emit(candidate.fragment_id, "reject");
                setSkipped(new Set([...skipped, candidate.fragment_id]));
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
