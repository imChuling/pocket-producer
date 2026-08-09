"use client";

import type { SessionFingerprint } from "@/types/audiotool";

// Shows exactly what was read from the Audiotool document. Fields the
// document didn't provide render as "not available" — the UI never pretends
// to know more than Nexus reported.
export function SessionSummary({
  fingerprint,
  onIntentChange,
}: {
  fingerprint: SessionFingerprint;
  onIntentChange: (intent: string) => void;
}) {
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
          value={fingerprint.text_intent}
          onChange={(event) => onIntentChange(event.target.value)}
          placeholder="e.g. dark bass, slower bridge…"
          className="w-full rounded-lg border border-chalk bg-surface px-3 py-2 text-obsidian placeholder:text-slate focus:border-gravel focus:outline-none"
        />
      </label>
    </section>
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
