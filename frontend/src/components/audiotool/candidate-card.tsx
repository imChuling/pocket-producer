"use client";

import { useState } from "react";
import { Loader2, Play, Plus, X } from "lucide-react";

import type { Fragment } from "@/types";
import type { RankEvidence, RankedCandidate } from "@/types/audiotool";

const EVIDENCE_STYLE: Record<string, string> = {
  tempo_match: "bg-[#e8dfd3]/60 text-[#7a6b56]",
  key_match: "bg-[#e8dfd3]/60 text-[#7a6b56]",
  track_gap: "bg-[#c8e6d0]/60 text-[#3d7a4f]",
  role_gap_fill: "bg-[#c8e6d0]/60 text-[#3d7a4f]",
  harmonic_fit: "bg-[#d8cee8]/60 text-[#6b5a8a]",
  intent_match: "bg-[#c8daf0]/60 text-[#4a6a8a]",
  novelty: "bg-[#f0e4c8]/60 text-[#8a7a3e]",
  recency: "bg-[#f0e4c8]/60 text-[#8a7a3e]",
  model_signal: "bg-obsidian/5 text-slate",
  timbral_match: "bg-[#f0d8cc]/60 text-[#8a5a42]",
  tag_overlap: "bg-[#cce4e8]/60 text-[#3e6e78]",
};

function evidenceClass(code: RankEvidence["code"]): string {
  return EVIDENCE_STYLE[code] ?? EVIDENCE_STYLE.model_signal!;
}

export function CandidateCard({
  fragment,
  ranked,
  onPreview,
  onInsert,
  onSkip,
}: {
  fragment: Fragment;
  ranked: RankedCandidate;
  onPreview: () => Promise<void> | void;
  onInsert: () => Promise<void> | void;
  onSkip: () => void;
}) {
  const [inserting, setInserting] = useState(false);
  const [insertError, setInsertError] = useState<string | null>(null);
  const evidence = ranked.evidence.slice(0, 3);

  async function handleInsert() {
    if (inserting) return;
    setInserting(true);
    setInsertError(null);
    try {
      await onInsert();
    } catch (cause) {
      setInsertError(
        cause instanceof Error ? cause.message : "Insert failed — try again",
      );
    } finally {
      setInserting(false);
    }
  }

  return (
    <article className="rounded-xl border border-chalk bg-powder p-4 space-y-3">
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="truncate text-obsidian">
          {fragment.title ?? "Untitled fragment"}
        </h3>
      </header>
      {evidence.length > 0 && (
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide text-slate">
            Why this now
          </p>
          <div className="flex flex-wrap gap-1.5">
            {evidence.map((item, index) => (
              <span
                key={`${item.code}-${index}`}
                className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium leading-tight ${evidenceClass(item.code)}`}
              >
                {item.label}
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void onPreview()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-chalk px-3 py-1.5 text-sm text-gravel hover:bg-powder"
        >
          <Play className="h-3.5 w-3.5" /> Preview
        </button>
        <button
          type="button"
          disabled={inserting}
          onClick={() => void handleInsert()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-obsidian px-3 py-1.5 text-sm font-medium text-white hover:bg-gravel disabled:opacity-60"
        >
          {inserting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plus className="h-3.5 w-3.5" />
          )}
          Insert into Audiotool
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-slate hover:text-gravel"
        >
          <X className="h-3.5 w-3.5" /> Skip
        </button>
      </div>
      {insertError && (
        <p role="alert" className="text-sm text-red-600">
          {insertError}
        </p>
      )}
    </article>
  );
}
