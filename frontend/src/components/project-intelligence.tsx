"use client";

import { useMemo } from "react";
import { Music, Gauge, Tag, Fingerprint } from "lucide-react";
import type { Fragment } from "@/types";

interface Props {
  fragments: Fragment[];
  connectionReasons?: string[];
  connectionTypes?: string[];
}

function modeName(key: string): string {
  const lower = key.toLowerCase().trim();
  if (lower.includes("minor") || lower.includes("min")) return "minor";
  if (lower.includes("major") || lower.includes("maj")) return "major";
  return "";
}

function keyRoot(key: string): string {
  return key.replace(/\s*(major|minor|maj|min)\s*/gi, "").trim();
}

export function ProjectIntelligence({ fragments, connectionReasons, connectionTypes }: Props) {
  const analysis = useMemo(() => {
    const audioFragments = fragments.filter((f) => f.type === "audio");
    const keys = audioFragments.map((f) => f.key).filter(Boolean) as string[];
    const bpms = audioFragments.map((f) => f.bpm).filter((b): b is number => b != null && b > 0);
    const allTags = audioFragments.flatMap((f) => f.tags || []);
    const tagCounts: Record<string, number> = {};
    for (const t of allTags) {
      tagCounts[t] = (tagCounts[t] || 0) + 1;
    }
    const topTags = Object.entries(tagCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([tag]) => tag);

    const keyGroups: Record<string, number> = {};
    for (const k of keys) {
      const root = keyRoot(k);
      const mode = modeName(k);
      const label = mode ? `${root} ${mode}` : root;
      keyGroups[label] = (keyGroups[label] || 0) + 1;
    }
    const dominantKey = Object.entries(keyGroups).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

    const bpmMin = bpms.length > 0 ? Math.min(...bpms) : null;
    const bpmMax = bpms.length > 0 ? Math.max(...bpms) : null;
    const sorted = [...bpms].sort((a, b) => a - b);
    const bpmMedian = sorted.length > 0 ? sorted[Math.floor(sorted.length / 2)] : null;
    const bpmSpread = bpmMin != null && bpmMax != null ? bpmMax - bpmMin : 0;
    const tempoCoherence = bpmSpread <= 5 ? "locked" : bpmSpread <= 15 ? "close" : "varied";

    const emotions = audioFragments.flatMap((f) => f.emotions || []);
    const emotionCounts: Record<string, number> = {};
    for (const e of emotions) {
      emotionCounts[e] = (emotionCounts[e] || 0) + 1;
    }
    const topEmotion = Object.entries(emotionCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

    const structures = audioFragments
      .map((f) => f.structure_hint)
      .filter(Boolean) as string[];
    const structureCounts: Record<string, number> = {};
    for (const s of structures) {
      structureCounts[s] = (structureCounts[s] || 0) + 1;
    }
    const topStructures = Object.entries(structureCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([s]) => s);

    return {
      audioCount: audioFragments.length,
      totalCount: fragments.length,
      dominantKey,
      keyCount: keys.length,
      bpmMedian,
      bpmMin,
      bpmMax,
      tempoCoherence,
      topTags,
      topEmotion,
      topStructures,
    };
  }, [fragments]);

  if (analysis.totalCount < 2) return null;

  const signals: { icon: typeof Music; label: string; value: string; sub?: string }[] = [];

  if (analysis.dominantKey) {
    signals.push({
      icon: Music,
      label: "Key center",
      value: analysis.dominantKey,
      sub: analysis.keyCount > 1 ? `${analysis.keyCount} fragments with key` : undefined,
    });
  }

  if (analysis.bpmMedian != null) {
    const tempoLabel =
      analysis.tempoCoherence === "locked"
        ? `${Math.round(analysis.bpmMedian)} BPM`
        : analysis.tempoCoherence === "close"
        ? `~${Math.round(analysis.bpmMedian)} BPM`
        : `${Math.round(analysis.bpmMin!)}--${Math.round(analysis.bpmMax!)} BPM`;
    signals.push({
      icon: Gauge,
      label: "Tempo",
      value: tempoLabel,
      sub: analysis.tempoCoherence === "locked" ? "tempo-locked" : undefined,
    });
  }

  if (analysis.topTags.length > 0) {
    signals.push({
      icon: Tag,
      label: "Shared traits",
      value: analysis.topTags.slice(0, 3).join(", "),
      sub: analysis.topTags.length > 3 ? `+${analysis.topTags.length - 3} more` : undefined,
    });
  }

  if (analysis.topEmotion) {
    signals.push({
      icon: Fingerprint,
      label: "Dominant feel",
      value: analysis.topEmotion,
    });
  }

  if (signals.length === 0) return null;

  return (
    <div
      className="rounded-[24px] p-5 space-y-4 shadow-hairline animate-card-enter"
      style={{
        background:
          "linear-gradient(135deg, rgba(255,255,255,0.85), rgba(160,181,235,0.06), rgba(226,193,97,0.04))",
      }}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
          Pipeline Analysis
        </span>
        <span className="text-[10px] text-slate/60 font-mono">
          {analysis.audioCount} audio fragment{analysis.audioCount !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {signals.map(({ icon: Icon, label, value, sub }, i) => (
          <div
            key={label}
            className="flex items-start gap-2.5 animate-card-enter"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{
                background:
                  "linear-gradient(135deg, rgba(160,181,235,0.15), rgba(226,193,97,0.1))",
              }}
            >
              <Icon size={13} className="text-gravel" />
            </div>
            <div className="min-w-0">
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate block">
                {label}
              </span>
              <span className="text-sm text-obsidian font-medium block truncate">
                {value}
              </span>
              {sub && (
                <span className="text-[10px] text-slate">{sub}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {analysis.topStructures.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {analysis.topStructures.map((s) => (
            <span
              key={s}
              className="text-[10px] font-mono uppercase tracking-wider text-gravel px-2 py-0.5 rounded-full bg-powder/60"
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
