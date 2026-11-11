"use client";

import { useState, useEffect } from "react";
import { Sparkles } from "lucide-react";
import { EmotionRadar } from "@/components/emotion-radar";
import { StyleBubbles } from "@/components/style-bubbles";
import { ThemeBar } from "@/components/theme-bar";
import { HourlyHeatmap } from "@/components/hourly-heatmap";
import type { DNAData } from "@/types";

const API_BASE = "/api";

function CreativePersonalityDemo({ dna }: { dna: DNAData }) {
  const emotionEntries = Object.entries(dna.emotions ?? {}).sort((a, b) => b[1] - a[1]);
  const topEmotion = emotionEntries[0]?.[0] ?? "---";
  const themeEntries = Object.entries(dna.themes ?? {}).sort((a, b) => b[1] - a[1]);
  const topTheme = themeEntries[0]?.[0] ?? "---";

  const archetype = (() => {
    const e = topEmotion.toLowerCase();
    if (["melancholy", "sad", "nostalgic", "longing"].some((w) => e.includes(w))) return "The Poet";
    if (["energetic", "excited", "powerful", "intense"].some((w) => e.includes(w))) return "The Firestarter";
    if (["calm", "peaceful", "serene", "dreamy"].some((w) => e.includes(w))) return "The Dreamer";
    if (["happy", "joyful", "playful", "uplifting"].some((w) => e.includes(w))) return "The Optimist";
    if (["dark", "aggressive", "angry", "tense"].some((w) => e.includes(w))) return "The Rebel";
    return "The Explorer";
  })();

  const top3 = emotionEntries.slice(0, 3);
  const emotionMax = top3[0]?.[1] ?? 1;

  return (
    <div className="relative rounded-[24px] overflow-hidden animate-card-enter" style={{ animationDelay: "50ms" }}>
      <div
        className="absolute inset-0 rounded-[24px] bg-gradient-animate"
        style={{
          background: "linear-gradient(135deg, rgba(160,181,235,0.3), rgba(255,148,115,0.2), rgba(226,193,97,0.2), rgba(160,181,235,0.3))",
          backgroundSize: "300% 300%",
        }}
      />
      <div className="relative m-[1px] rounded-[23px] bg-white/80 backdrop-blur-sm p-6 space-y-5">
        <div className="flex items-start gap-4">
          <div
            className="w-14 h-14 rounded-[18px] flex items-center justify-center flex-shrink-0"
            style={{ background: "linear-gradient(135deg, #a0b5eb, #ffa773)" }}
          >
            <Sparkles size={22} className="text-white" />
          </div>
          <div className="flex-1">
            <p className="font-heading text-2xl font-light text-obsidian tracking-tight">{archetype}</p>
            <p className="text-xs text-slate mt-1">
              Based on {dna.total_fragments} fragments
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs text-gravel" style={{ background: "rgba(160,181,235,0.12)" }}>
            Top emotion: <span className="font-medium text-obsidian">{topEmotion}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs text-gravel" style={{ background: "rgba(226,193,97,0.12)" }}>
            Top theme: <span className="font-medium text-obsidian">{topTheme}</span>
          </div>
        </div>
        {top3.length > 0 && (
          <div className="space-y-2">
            {top3.map(([name, count]) => (
              <div key={name} className="flex items-center gap-3">
                <span className="text-[11px] text-gravel w-24 truncate">{name}</span>
                <div className="flex-1 h-1.5 rounded-full bg-chalk overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(count / emotionMax) * 100}%`,
                      background: "linear-gradient(90deg, #a0b5eb, #e2c161)",
                    }}
                  />
                </div>
                <span className="text-[10px] text-slate w-6 text-right">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatsRowDemo({ dna }: { dna: DNAData }) {
  const stats = [
    { label: "Fragments", value: dna.total_fragments },
    { label: "Projects", value: dna.total_projects },
    { label: "Emotions", value: Object.keys(dna.emotions ?? {}).length },
    { label: "Themes", value: Object.keys(dna.themes ?? {}).length },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 animate-card-enter" style={{ animationDelay: "100ms" }}>
      {stats.map((s) => (
        <div key={s.label} className="bg-white/50 backdrop-blur-sm rounded-[18px] p-4 shadow-hairline text-center">
          <p className="font-heading text-2xl font-light text-obsidian">{s.value}</p>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate mt-1">{s.label}</p>
        </div>
      ))}
    </div>
  );
}

export default function DemoDNAPage() {
  const [dna, setDna] = useState<DNAData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/demo/dna`)
      .then((r) => r.json())
      .then((data) => {
        if (data && data.emotions) {
          setDna(data as DNAData);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 rounded-full border-2 border-chalk border-t-gravel animate-spin" />
      </div>
    );
  }

  if (!dna) {
    return (
      <div className="relative min-h-[calc(100vh-56px-44px)]">
        <div className="ambient-mesh" />
        <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-12 space-y-4 animate-page-enter">
          <h1 className="font-heading text-3xl font-light tracking-tight shimmer-heading">
            Creative DNA
          </h1>
          <div className="flex flex-col items-center py-16 space-y-6">
            <div
              className="w-32 h-32 morph-blob opacity-50"
              style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.4), rgba(255,148,115,0.2), rgba(226,193,97,0.2))" }}
            />
            <p className="text-sm text-gravel text-center">
              Not enough data yet.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const emotions = dna.emotions ?? {};
  const themes = dna.themes ?? {};
  const hours = dna.hourly_distribution ?? {};
  const styles = dna.top_styles ?? [];

  return (
    <div className="relative min-h-[calc(100vh-56px-44px)]">
      <div className="ambient-mesh" />

      <div className="fixed top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-0">
        <div
          className="w-[450px] h-[450px] morph-blob opacity-12"
          style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.6), rgba(255,148,115,0.35), rgba(226,193,97,0.25))" }}
        />
      </div>

      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 space-y-6 animate-page-enter">
        <div className="space-y-1">
          <h1 className="font-heading text-3xl font-light tracking-tight shimmer-heading">
            Creative DNA
          </h1>
          <p className="text-xs text-slate font-mono">
            Demo account overview
          </p>
        </div>

        {/* Hero row */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3">
            <CreativePersonalityDemo dna={dna} />
          </div>
          <div className="lg:col-span-2 flex flex-col gap-4">
            <StatsRowDemo dna={dna} />
            {dna.peak_hours && dna.peak_hours !== "N/A" && (
              <div className="animate-card-enter bg-white/50 backdrop-blur-sm rounded-[18px] p-4 shadow-hairline" style={{ animationDelay: "150ms" }}>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate mb-2">Peak Hours</p>
                <p className="font-heading text-lg text-obsidian">{dna.peak_hours}</p>
              </div>
            )}
          </div>
        </div>

        {/* Bento grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-8">
          {/* Emotion Radar */}
          {Object.keys(emotions).length >= 3 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "200ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Emotional Palette
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-3 shadow-hairline h-full flex items-center justify-center">
                <EmotionRadar emotions={emotions} />
              </div>
            </section>
          )}

          {/* Style Bubbles */}
          {styles.length > 0 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "250ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Sound Palette
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-3 shadow-hairline h-full">
                <StyleBubbles styles={styles} />
              </div>
            </section>
          )}

          {/* Themes */}
          {Object.keys(themes).length > 0 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "300ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Top Themes
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] px-6 py-3 shadow-hairline h-full flex items-center">
                <div className="w-full">
                  <ThemeBar themes={themes} />
                </div>
              </div>
            </section>
          )}

          {/* Creative Rhythm */}
          {Object.keys(hours).length > 0 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "350ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Creative Rhythm
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-6 shadow-hairline h-full">
                <HourlyHeatmap distribution={hours} />
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
