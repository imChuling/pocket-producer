"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Play } from "lucide-react";

// Blind pairwise annotation: no model information is shown or known here.

export type PairFragment = {
  fragment_id: string;
  title: string | null;
  audio_url: string | null;
};

export type PairTask = {
  pair_id: string;
  context_project_id: string | null;
  context: PairFragment[];
  left: PairFragment;
  right: PairFragment;
};

export type NextPairResponse =
  | { done: false; remaining: number; pair: PairTask }
  | { done: true; remaining: 0 };

export type PairLabelPayload = {
  choice: "left" | "right" | "neither";
  reason_codes: string[];
  confidence: number;
};

export const REASON_CODES = [
  ["tempo_fit", "Tempo fit"],
  ["key_fit", "Key fit"],
  ["supports_next_step", "Supports next step"],
  ["fills_missing_role", "Fills missing role"],
  ["rhythmic_fit", "Rhythmic fit"],
  ["mood_fit", "Mood fit"],
  ["novelty_welcome", "Welcome novelty"],
  ["too_similar", "Too similar"],
  ["wrong_energy", "Wrong energy"],
] as const;

export function AnnotatePanel({
  fetchNext,
  submitLabel,
  onPreview,
}: {
  fetchNext: () => Promise<NextPairResponse>;
  submitLabel: (pairId: string, label: PairLabelPayload) => Promise<void>;
  onPreview: (fragment: PairFragment) => Promise<void> | void;
}) {
  const [task, setTask] = useState<NextPairResponse | null>(null);
  const [choice, setChoice] = useState<PairLabelPayload["choice"] | null>(null);
  const [reasons, setReasons] = useState<Set<string>>(new Set());
  const [confidence, setConfidence] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await fetchNext();
      setChoice(null);
      setReasons(new Set());
      setConfidence(3);
      setError(null);
      setTask(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, [fetchNext]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (error) {
    return (
      <p role="alert" className="text-sm text-red-600">
        {error}
      </p>
    );
  }
  if (task === null) {
    return <Loader2 className="h-6 w-6 animate-spin text-slate" />;
  }
  if (task.done) {
    return (
      <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-8 text-center text-emerald-900">
        <CheckCircle2 className="mx-auto mb-2 h-8 w-8" />
        All pairs labeled — thank you. Run the export script to collect them.
      </div>
    );
  }

  const { pair, remaining } = task;

  async function submit() {
    if (choice === null || busy || task === null || task.done) return;
    setBusy(true);
    try {
      await submitLabel(task.pair.pair_id, {
        choice,
        reason_codes: [...reasons],
        confidence,
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  function toggleReason(code: string) {
    setReasons((previous) => {
      const next = new Set(previous);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate">{remaining} pairs left</p>

      <section className="rounded-xl border border-chalk bg-powder p-4">
        <h2 className="mb-2 text-sm font-medium text-gravel">
          Session context — imagine you are continuing this project
        </h2>
        <ul className="space-y-1">
          {pair.context.map((fragment) => (
            <li
              key={fragment.fragment_id}
              className="flex items-center gap-2 text-sm text-gravel"
            >
              <button
                type="button"
                aria-label={`Preview ${fragment.title ?? "context fragment"}`}
                onClick={() => void onPreview(fragment)}
                className="rounded-md border border-chalk p-1 hover:bg-powder"
              >
                <Play className="h-3 w-3" />
              </button>
              {fragment.title ?? "Untitled"}
            </li>
          ))}
        </ul>
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        {(
          [
            ["left", "A", pair.left],
            ["right", "B", pair.right],
          ] as const
        ).map(([side, letter, fragment]) => (
          <section
            key={side}
            className={`rounded-xl border p-4 space-y-3 ${
              choice === side
                ? "border-gravel bg-powder"
                : "border-chalk bg-powder"
            }`}
          >
            <header className="flex items-center justify-between">
              <h3 className="text-obsidian">{fragment.title ?? "Untitled"}</h3>
              <span className="text-xs text-slate">Candidate {letter}</span>
            </header>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void onPreview(fragment)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-chalk px-3 py-1.5 text-sm text-gravel hover:bg-powder"
              >
                <Play className="h-3.5 w-3.5" /> Preview
              </button>
              <button
                type="button"
                onClick={() => setChoice(side)}
                className="rounded-lg bg-obsidian px-3 py-1.5 text-sm font-medium text-white hover:bg-gravel"
              >
                Choose {letter}
              </button>
            </div>
          </section>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setChoice("neither")}
        className={`rounded-lg border px-3 py-1.5 text-sm ${
          choice === "neither"
            ? "border-gravel text-obsidian"
            : "border-chalk text-slate hover:text-gravel"
        }`}
      >
        Neither works here
      </button>

      <section>
        <p className="mb-2 text-sm text-slate">Why? (optional)</p>
        <div className="flex flex-wrap gap-2">
          {REASON_CODES.map(([code, label]) => (
            <button
              key={code}
              type="button"
              onClick={() => toggleReason(code)}
              className={`rounded-full border px-3 py-1 text-xs ${
                reasons.has(code)
                  ? "border-gravel bg-powder text-obsidian"
                  : "border-chalk text-slate hover:text-gravel"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <section className="flex items-center gap-3">
        <label htmlFor="confidence" className="text-sm text-slate">
          Confidence
        </label>
        <input
          id="confidence"
          type="range"
          min={1}
          max={5}
          value={confidence}
          onChange={(event) => setConfidence(Number(event.target.value))}
        />
        <span className="text-sm text-gravel">{confidence}/5</span>
      </section>

      <button
        type="button"
        disabled={choice === null || busy}
        onClick={() => void submit()}
        className="inline-flex items-center gap-2 rounded-lg bg-obsidian px-5 py-2 text-sm font-medium text-white hover:bg-gravel disabled:opacity-50"
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        Submit
      </button>
    </div>
  );
}
