"use client";

// Fixture page for rendering the paper's UI figure (Figure 2).
// Dev-only: research/annotate_ui_figure.py documents the capture pipeline.

import { notFound } from "next/navigation";

import { useEffect } from "react";

import { ContinuationPanel } from "@/components/audiotool/continuation-panel";
import type { Fragment } from "@/types";
import type { RankResponse, SessionFingerprint } from "@/types/audiotool";

const FINGERPRINT: SessionFingerprint = {
  project_id: "demo-project",
  bpm: 128,
  key: null,
  playhead_seconds: 34.5,
  track_count: 4,
  active_track_types: ["audio", "note", "pattern"],
  recent_entity_ids: [],
  text_intent: "dark bass, slower bridge",
};

const FRAGMENTS: Fragment[] = [
  {
    _id: "f1",
    user_id: "demo",
    type: "audio",
    title: "Rooftop pad idea (voice memo)",
    tags: ["pad", "ambient"],
    emotions: [],
    themes: [],
    created_at: "2026-08-01T00:00:00Z",
  },
  {
    _id: "f2",
    user_id: "demo",
    type: "audio",
    title: "Late-night perc jam",
    tags: ["house", "loop", "percussion"],
    emotions: [],
    themes: [],
    created_at: "2026-08-01T00:00:00Z",
  },
  {
    _id: "f3",
    user_id: "demo",
    type: "audio",
    title: "Tape hiss texture, Jul 14",
    tags: ["pad", "texture"],
    emotions: [],
    themes: [],
    created_at: "2026-08-01T00:00:00Z",
  },
];

const RESPONSE: RankResponse = {
  request_id: "req-demo",
  model_id: "fusion-5sig-v1",
  fallback_used: false,
  candidates: [
    {
      fragment_id: "f1",
      score: 0.91,
      evidence: [
        {
          code: "timbral_match",
          label: "Sounds close to your session regions",
          contribution: 0.4,
        },
        { code: "tempo_match", label: "Tempo fits the session", contribution: 0.3 },
      ],
    },
    {
      fragment_id: "f2",
      score: 0.84,
      evidence: [
        {
          code: "timbral_match",
          label: "Sounds close to your session regions",
          contribution: 0.35,
        },
        {
          code: "tag_overlap",
          label: "Shares tags with recent fragments",
          contribution: 0.2,
        },
      ],
    },
    {
      fragment_id: "f3",
      score: 0.78,
      evidence: [
        {
          code: "timbral_match",
          label: "Sounds close to your session regions",
          contribution: 0.3,
        },
        {
          code: "tag_overlap",
          label: "Shares tags with recent fragments",
          contribution: 0.15,
        },
        { code: "tempo_match", label: "Tempo fits the session", contribution: 0.1 },
      ],
    },
  ],
};

export default function FigurePage() {
  if (process.env.NODE_ENV === "production") notFound();
  useEffect(() => {
    // Auto-drive the panel so a headless screenshot needs no interaction:
    // pick the fusion model, request suggestions, strip the dev badge.
    const select = document.querySelector<HTMLSelectElement>(
      'select[aria-label="Ranking model"]',
    );
    if (select) {
      const setter = Object.getOwnPropertyDescriptor(
        HTMLSelectElement.prototype,
        "value",
      )?.set;
      setter?.call(select, "fusion-5sig-v1");
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    const buttons = Array.from(document.querySelectorAll("button"));
    buttons.find((b) => b.textContent?.includes("Suggest 3"))?.click();
    const hideBadge = () =>
      document
        .querySelectorAll("nextjs-portal, [data-next-badge-root]")
        .forEach((e) => e.remove());
    hideBadge();
    const t = setInterval(hideBadge, 200);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="mx-auto w-[1150px] max-w-none p-6" data-figure-root>
      <ContinuationPanel
        fingerprint={FINGERPRINT}
        fragments={FRAGMENTS}
        availableModels={["rules-v1", "fusion-5sig-v1"]}
        requestRecommendations={async () => RESPONSE}
        onIntentChange={() => {}}
        onPreview={() => {}}
        onInsert={async () => {}}
        onFeedback={() => {}}
      />
    </main>
  );
}
