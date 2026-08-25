"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { parseIntent } from "@/lib/ranking-api";
import type { ParsedIntent, SessionFingerprint } from "@/types/audiotool";

// Shows exactly what was read from the Audiotool document. Fields the
// document didn't provide render as "not available" — the UI never pretends
// to know more than Nexus reported.
//
// The intent input carries an LLM reading underneath: once the user pauses
// typing, the server proposes structured chips (tags, roles, tempo, key).
// Every chip is removable — only what the user leaves standing is echoed
// back into the fingerprint and allowed to influence ranking.
export function SessionSummary({
  fingerprint,
  onIntentChange,
  parsedIntent,
  onParsedIntentChange,
}: {
  fingerprint: SessionFingerprint;
  onIntentChange: (intent: string) => void;
  parsedIntent?: ParsedIntent | null;
  onParsedIntentChange?: (parsed: ParsedIntent | null) => void;
}) {
  const [interpreting, setInterpreting] = useState(false);
  const lastParsedRef = useRef("");
  const text = fingerprint.text_intent;

  useEffect(() => {
    if (!onParsedIntentChange) return;
    const trimmed = text.trim();
    if (trimmed.length < 4) {
      if (lastParsedRef.current !== "") {
        lastParsedRef.current = "";
        onParsedIntentChange(null);
      }
      return;
    }
    if (trimmed.toLowerCase() === lastParsedRef.current) return;
    const timer = setTimeout(() => {
      setInterpreting(true);
      parseIntent(trimmed)
        .then((parsed) => {
          lastParsedRef.current = trimmed.toLowerCase();
          onParsedIntentChange(parsed);
        })
        .catch(() => {
          // Interpretation is an enhancement; raw text still ranks.
          onParsedIntentChange(null);
        })
        .finally(() => setInterpreting(false));
    }, 800);
    return () => clearTimeout(timer);
  }, [text, onParsedIntentChange]);

  function update(partial: Partial<ParsedIntent>) {
    if (!onParsedIntentChange || !parsedIntent) return;
    const next = { ...parsedIntent, ...partial };
    const empty =
      next.tags.length === 0 &&
      next.roles.length === 0 &&
      next.bpm === null &&
      next.key === null;
    onParsedIntentChange(empty ? null : next);
  }

  return (
    <section
      aria-label="Session summary"
      className="rounded-xl border border-chalk bg-powder p-4 space-y-3"
    >
      <h2 className="text-sm font-medium text-gravel">
        What we read from your session
      </h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <SummaryItem
          label="Tempo"
          value={
            fingerprint.bpm !== null
              ? `${Math.round(fingerprint.bpm * 10) / 10} BPM`
              : "not available"
          }
        />
        <SummaryItem
          label="Key"
          value={fingerprint.key ?? "not available"}
        />
        <SummaryItem
          label="Tracks"
          value={String(fingerprint.track_count)}
        />
        <SummaryItem
          label="Track types"
          value={
            fingerprint.active_track_types.length > 0
              ? fingerprint.active_track_types.join(", ")
              : "none yet"
          }
        />
        <SummaryItem
          label="Playhead"
          value={`${fingerprint.playhead_seconds.toFixed(1)}s`}
        />
      </dl>
      <label className="block text-sm text-gravel">
        <span className="mb-1 block">What are you going for? (optional)</span>
        <input
          type="text"
          maxLength={240}
          value={text}
          onChange={(event) => onIntentChange(event.target.value)}
          placeholder="e.g. darker, more cinematic, but not too heavy…"
          className="w-full rounded-lg border border-chalk bg-surface px-3 py-2 text-obsidian placeholder:text-slate focus:border-gravel focus:outline-none"
        />
      </label>
      {onParsedIntentChange && interpreting && (
        <p className="text-xs text-slate" aria-live="polite">
          Reading your intent…
        </p>
      )}
      {onParsedIntentChange && !interpreting && parsedIntent && (
        <div
          className="flex flex-wrap items-center gap-1.5"
          aria-label="How your intent was read"
        >
          <span className="text-xs text-slate">How I read that:</span>
          {parsedIntent.tags.map((tag) => (
            <IntentChip
              key={`tag-${tag}`}
              label={tag}
              onRemove={() =>
                update({ tags: parsedIntent.tags.filter((t) => t !== tag) })
              }
            />
          ))}
          {parsedIntent.roles.map((role) => (
            <IntentChip
              key={`role-${role}`}
              label={`needs ${role}`}
              onRemove={() =>
                update({ roles: parsedIntent.roles.filter((r) => r !== role) })
              }
            />
          ))}
          {parsedIntent.bpm !== null && (
            <IntentChip
              label={`~${Math.round(parsedIntent.bpm)} BPM`}
              onRemove={() => update({ bpm: null })}
            />
          )}
          {parsedIntent.key !== null && (
            <IntentChip
              label={parsedIntent.key}
              onRemove={() => update({ key: null })}
            />
          )}
        </div>
      )}
    </section>
  );
}

function IntentChip({
  label,
  onRemove,
}: {
  label: string;
  onRemove: () => void;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-chalk bg-surface px-2.5 py-0.5 text-xs text-gravel">
      {label}
      <button
        type="button"
        aria-label={`Remove ${label}`}
        onClick={onRemove}
        className="text-slate hover:text-obsidian"
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate">{label}</dt>
      <dd className="text-obsidian">{value}</dd>
    </div>
  );
}
