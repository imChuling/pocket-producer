"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Flame, Clock, Music2, Sparkles, Layers } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { apiFetch } from "@/lib/api";
import { EmotionRadar } from "@/components/emotion-radar";
import { ThemeBar } from "@/components/theme-bar";
import { HourlyHeatmap } from "@/components/hourly-heatmap";
import type { DNAData } from "@/types";

/* ═══════════════════════════════════════════════════════════════
   Creative Personality — hero card with animated gradient border
   ═══════════════════════════════════════════════════════════════ */
function CreativePersonality({ dna }: { dna: DNAData }) {
  const emotionEntries = Object.entries(dna.emotions ?? {}).sort((a, b) => b[1] - a[1]);
  const topEmotion = emotionEntries[0]?.[0] ?? "—";
  const themeEntries = Object.entries(dna.themes ?? {}).sort((a, b) => b[1] - a[1]);
  const topTheme = themeEntries[0]?.[0] ?? "—";

  const archetype = (() => {
    const e = topEmotion.toLowerCase();
    if (["melancholy", "sad", "nostalgic", "longing"].some(w => e.includes(w))) return "The Poet";
    if (["energetic", "excited", "powerful", "intense"].some(w => e.includes(w))) return "The Firestarter";
    if (["calm", "peaceful", "serene", "dreamy"].some(w => e.includes(w))) return "The Dreamer";
    if (["happy", "joyful", "playful", "uplifting"].some(w => e.includes(w))) return "The Optimist";
    if (["dark", "aggressive", "angry", "tense"].some(w => e.includes(w))) return "The Rebel";
    return "The Explorer";
  })();

  // Top 3 emotions as mini visual
  const top3 = emotionEntries.slice(0, 3);
  const emotionMax = top3[0]?.[1] ?? 1;

  return (
    <div className="relative rounded-[24px] overflow-hidden animate-card-enter" style={{ animationDelay: "50ms" }}>
      {/* Animated gradient border */}
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
            style={{
              background: "linear-gradient(135deg, #a0b5eb, #ffa773)",
            }}
          >
            <Sparkles size={22} className="text-white" />
          </div>
          <div className="flex-1">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-slate mb-0.5">
              Creative Archetype
            </p>
            <p className="font-heading text-3xl font-light text-obsidian tracking-tight leading-tight">
              {archetype}
            </p>
          </div>
        </div>
        <p className="text-sm text-gravel leading-relaxed">
          Your music gravitates toward <span className="font-medium text-obsidian">{topEmotion}</span> emotions
          with recurring <span className="font-medium text-obsidian">{topTheme}</span> themes.
          {dna.peak_hours && dna.peak_hours !== "N/A" && (
            <> You create most during <span className="font-medium text-obsidian">{dna.peak_hours}</span>.</>
          )}
        </p>
        {/* Mini emotion bars */}
        <div className="space-y-2 pt-1">
          {top3.map(([name, value], i) => {
            const pct = (value / emotionMax) * 100;
            const colors = [
              ["#a0b5eb", "#6366f1"],
              ["#ffa773", "#e06030"],
              ["#e2c161", "#d4940a"],
            ];
            const [from, to] = colors[i % colors.length];
            return (
              <div key={name} className="flex items-center gap-2.5">
                <span className="text-[11px] text-slate w-20 truncate font-mono">{name}</span>
                <div className="flex-1 h-[4px] bg-powder/60 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full animate-bar-fill"
                    style={{
                      width: `${pct}%`,
                      background: `linear-gradient(90deg, ${from}, ${to})`,
                      animationDelay: `${300 + i * 120}ms`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   Emotion color mapping — semantic hue by mood
   ═══════════════════════════════════════════ */

// Map each emotion keyword to a position on a warm↔cool spectrum (0 = coldest blue, 1 = warmest amber).
// Similar emotions sit close together so their colors are naturally related.
const EMOTION_HUE: Record<string, number> = {
  // Cold / melancholic — deep blues
  sadness: 0.0, melancholy: 0.05, longing: 0.1, bittersweet: 0.13,
  // Cool / reflective — mid blues
  nostalgia: 0.18, peacefulness: 0.22, tenderness: 0.26, dreamy: 0.30,
  transcendence: 0.34, wonder: 0.38,
  // Neutral / warm — transitional
  hopeful: 0.45, joyful_activation: 0.52,
  // Warm / energetic — oranges & golds
  energetic: 0.62, power: 0.70, defiance: 0.78,
  tension: 0.85,
};

function emotionColor(name: string): string {
  const key = name.toLowerCase().replace(/\s+/g, "_");
  // Exact match or partial match
  let hue = EMOTION_HUE[key];
  if (hue === undefined) {
    for (const [k, v] of Object.entries(EMOTION_HUE)) {
      if (key.includes(k) || k.includes(key)) { hue = v; break; }
    }
  }
  if (hue === undefined) hue = 0.5; // neutral fallback

  // Interpolate: cold blue (#6b85c2) ↔ warm amber (#d4a05a)
  const r = Math.round(107 + hue * 105);  // 107 → 212
  const g = Math.round(133 + hue * 27);   // 133 → 160
  const b = Math.round(194 - hue * 104);  // 194 → 90
  return `rgb(${r},${g},${b})`;
}

/* ═══════════════════════════════════════════
   Emotion Flow — Canvas flowing particle field
   ═══════════════════════════════════════════ */
function EmotionFlow({ emotions }: { emotions: Record<string, number> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = 100;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const entries = Object.entries(emotions).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const total = entries.reduce((s, [, v]) => s + v, 0) || 1;

    const particles: {
      x: number; y: number; vx: number; size: number;
      color: string; phase: number; laneY: number;
    }[] = [];

    entries.forEach(([name, value], laneIdx) => {
      const count = Math.max(4, Math.round((value / total) * 30));
      const laneY = ((laneIdx + 0.5) / entries.length) * h;
      const color = emotionColor(name);
      for (let j = 0; j < count; j++) {
        particles.push({
          x: Math.random() * w,
          y: laneY + (Math.random() - 0.5) * 24,
          vx: 0.2 + Math.random() * 0.4,
          size: 1.5 + Math.random() * 2,
          color,
          phase: Math.random() * Math.PI * 2,
          laneY,
        });
      }
    });

    let frame = 0;
    let rafId = 0;

    function draw() {
      ctx!.clearRect(0, 0, w, h);

      // Subtle lane lines
      entries.forEach((_, i) => {
        const laneY = ((i + 0.5) / entries.length) * h;
        ctx!.beginPath();
        ctx!.moveTo(0, laneY);
        ctx!.lineTo(w, laneY);
        ctx!.strokeStyle = "rgba(0,0,0,0.02)";
        ctx!.lineWidth = 0.5;
        ctx!.stroke();
      });

      particles.forEach((p) => {
        if (!prefersReducedMotion) {
          p.x += p.vx;
          p.y = p.laneY + Math.sin(frame * 0.01 + p.phase) * 12;
        }
        if (p.x > w + 10) p.x = -10;

        // Particle glow
        const glow = ctx!.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 4);
        glow.addColorStop(0, p.color.replace("rgb", "rgba").replace(")", ",0.2)"));
        glow.addColorStop(1, "transparent");
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.size * 4, 0, Math.PI * 2);
        ctx!.fillStyle = glow;
        ctx!.fill();

        // Solid dot
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx!.fillStyle = p.color.replace("rgb", "rgba").replace(")", ",0.6)");
        ctx!.fill();
      });

      frame++;
      rafId = requestAnimationFrame(draw);
    }

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
  }, [emotions]);

  return (
    <div ref={containerRef} className="w-full">
      <canvas ref={canvasRef} className="rounded-2xl" />
    </div>
  );
}

/* ═══════════════════════════════════════════
   Style Cloud — bubble layout
   ═══════════════════════════════════════════ */
function StyleCloud({ styles }: { styles: { _id: string; count: number }[] }) {
  const max = Math.max(...styles.map(s => s.count), 1);
  const gradients = [
    "linear-gradient(135deg, rgba(160,181,235,0.22), rgba(123,143,204,0.12))",
    "linear-gradient(135deg, rgba(212,160,106,0.2), rgba(180,130,80,0.1))",
    "linear-gradient(135deg, rgba(196,164,78,0.2), rgba(170,140,60,0.1))",
    "linear-gradient(135deg, rgba(143,163,208,0.2), rgba(120,140,180,0.1))",
    "linear-gradient(135deg, rgba(184,200,232,0.2), rgba(150,168,200,0.1))",
    "linear-gradient(135deg, rgba(240,196,144,0.2), rgba(200,160,110,0.1))",
  ];
  return (
    <div className="flex flex-wrap gap-2.5 justify-center">
      {styles.map((s, i) => {
        const intensity = s.count / max;
        const size = 0.78 + intensity * 0.28;
        return (
          <span
            key={s._id}
            className="px-4 py-2 rounded-full animate-tag-pop font-medium border border-white/50 backdrop-blur-sm"
            style={{
              fontSize: `${size}rem`,
              animationDelay: `${i * 70}ms`,
              background: gradients[i % gradients.length],
              color: intensity > 0.5 ? "#000000" : "#777169",
              boxShadow: intensity > 0.5 ? "0 2px 12px rgba(160,181,235,0.15)" : "none",
            }}
          >
            {s._id}
          </span>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════
   Structure Donut — Canvas with animation
   ═══════════════════════════════════════════ */
function StructureDonut({ structures }: { structures: { _id: string; count: number }[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const total = structures.reduce((sum, s) => sum + s.count, 0);

  const colors = ["#a0b5eb", "#d4a06a", "#c4a44e", "#8fa3d0", "#b8c8e8", "#96a8c8"];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || structures.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const size = 160;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const outerR = 68;
    const innerR = 42;
    let progress = 0;
    let rafId = 0;
    const duration = 45;

    function draw() {
      progress = Math.min(progress + 1, duration);
      const t = easeOutCubic(progress / duration);
      ctx!.clearRect(0, 0, size, size);

      let startAngle = -Math.PI / 2;
      const gap = 0.04;

      structures.forEach((s, i) => {
        const sweep = ((s.count / total) * Math.PI * 2 - gap) * t;
        const endAngle = startAngle + sweep;
        const color = colors[i % colors.length];

        // Shadow / glow
        ctx!.shadowColor = color;
        ctx!.shadowBlur = 6;

        ctx!.beginPath();
        ctx!.arc(cx, cy, outerR, startAngle, endAngle);
        ctx!.arc(cx, cy, innerR, endAngle, startAngle, true);
        ctx!.closePath();
        ctx!.fillStyle = color;
        ctx!.globalAlpha = 0.85;
        ctx!.fill();
        ctx!.globalAlpha = 1;
        ctx!.shadowBlur = 0;

        startAngle = endAngle + gap;
      });

      // Center
      ctx!.beginPath();
      ctx!.arc(cx, cy, innerR - 2, 0, Math.PI * 2);
      ctx!.fillStyle = "rgba(255,255,255,0.85)";
      ctx!.fill();

      ctx!.font = "22px var(--font-cormorant, Georgia)";
      ctx!.fillStyle = "#000000";
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
      ctx!.fillText(String(total), cx, cy - 4);
      ctx!.font = "8px var(--font-ibm-plex-mono, monospace)";
      ctx!.fillStyle = "#a59f97";
      ctx!.fillText("parts", cx, cy + 11);

      if (progress < duration) {
        rafId = requestAnimationFrame(draw);
      }
    }

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
  }, [structures, total]);

  return (
    <div className="flex flex-col items-center gap-4">
      <canvas ref={canvasRef} className="flex-shrink-0" />
      <div className="space-y-2 w-full">
        {structures.slice(0, 5).map((seg, i) => {
          const pct = Math.round((seg.count / total) * 100);
          return (
            <div key={seg._id} className="flex items-center gap-2 animate-card-enter" style={{ animationDelay: `${i * 60}ms` }}>
              <div
                className="w-3 h-3 rounded-[4px] flex-shrink-0"
                style={{ background: colors[i % colors.length] }}
              />
              <span className="text-xs text-gravel flex-1 truncate">
                {seg._id.replace("_candidate", "").replace("_", " ")}
              </span>
              <span className="font-mono text-[11px] text-slate font-medium">
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   Stats Row
   ═══════════════════════════════════════════ */
function StatsRow({ dna }: { dna: DNAData }) {
  const emotionCount = Object.keys(dna.emotions ?? {}).length;
  const themeCount = Object.keys(dna.themes ?? {}).length;
  const stats = [
    { value: dna.total_fragments ?? 0, label: "Fragments", icon: Music2, gradient: "linear-gradient(135deg, #a0b5eb40, #6366f120)" },
    { value: dna.total_projects ?? 0, label: "Projects", icon: Layers, gradient: "linear-gradient(135deg, #ffa77340, #e0603020)" },
    { value: emotionCount, label: "Emotions", icon: Flame, gradient: "linear-gradient(135deg, #e2c16140, #d4940a20)" },
    { value: themeCount, label: "Themes", icon: Sparkles, gradient: "linear-gradient(135deg, #34d39940, #05966920)" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      {stats.map(({ value, label, icon: Icon, gradient }, i) => (
        <div
          key={label}
          className="rounded-[16px] p-3.5 text-center space-y-1 animate-card-enter"
          style={{ background: gradient, animationDelay: `${i * 60}ms` }}
        >
          <Icon size={15} className="text-gravel mx-auto" />
          <p className="font-heading text-xl font-light text-obsidian tracking-tight animate-count-up" style={{ animationDelay: `${200 + i * 80}ms` }}>
            {value}
          </p>
          <p className="font-mono text-[9px] text-slate uppercase tracking-[0.12em]">{label}</p>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════
   Peak Hours Insight
   ═══════════════════════════════════════════ */
function PeakHoursInsight({ peakHours, hours }: { peakHours: string; hours: Record<string, number> }) {
  const maxHour = Object.entries(hours).sort((a, b) => b[1] - a[1])[0];
  const totalFrags = Object.values(hours).reduce((sum, v) => sum + v, 0);
  const peakPct = maxHour ? Math.round((maxHour[1] / totalFrags) * 100) : 0;

  return (
    <div className="flex items-center gap-4 rounded-[20px] px-5 py-4" style={{ background: "linear-gradient(135deg, rgba(226,193,97,0.12), rgba(255,148,115,0.08))" }}>
      <div
        className="w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: "linear-gradient(135deg, #e2c161, #ffa773)" }}
      >
        <Clock size={17} className="text-white" />
      </div>
      <div className="flex-1">
        <p className="text-sm text-obsidian font-medium">Peak creative window</p>
        <p className="text-xs text-gravel">
          <span className="font-mono font-medium text-obsidian">{peakHours}</span> — {peakPct}% of your ideas happen here
        </p>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   Main Page
   ═══════════════════════════════════════════ */
export default function DNAPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [dna, setDna] = useState<DNAData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    apiFetch<Record<string, unknown>>("/dna")
      .then((data) => {
        if (data && data.emotions) {
          setDna(data as unknown as DNAData);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  if (authLoading || !user) return null;

  if (loading) {
    return <div className="py-8 text-sm text-slate">Loading...</div>;
  }

  if (!dna) {
    return (
      <div className="relative min-h-[calc(100vh-56px)]">
        <div className="ambient-mesh" />
        <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-12 space-y-4 animate-page-enter">
          <h1 className="font-heading text-3xl font-light tracking-tight shimmer-heading">
            Your Creative DNA
          </h1>
          <div className="flex flex-col items-center py-16 space-y-6">
            <div
              className="w-32 h-32 morph-blob opacity-50"
              style={{
                background: "linear-gradient(135deg, rgba(160,181,235,0.4), rgba(255,148,115,0.2), rgba(226,193,97,0.2))",
              }}
            />
            <p className="text-sm text-gravel text-center">
              Not enough data yet. Keep capturing fragments!
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
  const structures = dna.structure_distribution ?? [];

  return (
    <div className="relative min-h-[calc(100vh-56px)]">
      {/* Ambient background */}
      <div className="ambient-mesh" />

      {/* Decorative morph blob */}
      <div className="fixed top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-0">
        <div
          className="w-[450px] h-[450px] morph-blob opacity-12"
          style={{
            background: "linear-gradient(135deg, rgba(160,181,235,0.6), rgba(255,148,115,0.35), rgba(226,193,97,0.25))",
          }}
        />
      </div>

      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 space-y-6 animate-page-enter">
        <div className="space-y-1">
          <h1 className="font-heading text-3xl font-light tracking-tight shimmer-heading">
            Your Creative DNA
          </h1>
          <p className="text-xs text-slate font-mono">
            Last updated {dna.updated_at ? new Date(dna.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
          </p>
        </div>

        {/* Hero row — Personality + Stats side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3">
            <CreativePersonality dna={dna} />
          </div>
          <div className="lg:col-span-2 flex flex-col gap-4">
            <StatsRow dna={dna} />
            {dna.peak_hours && dna.peak_hours !== "N/A" && (
              <div className="animate-card-enter flex-1" style={{ animationDelay: "150ms" }}>
                <PeakHoursInsight peakHours={dna.peak_hours} hours={hours} />
              </div>
            )}
          </div>
        </div>

        {/* Emotion Flow — full width */}
        {Object.keys(emotions).length >= 2 && (
          <section className="space-y-3 animate-card-enter" style={{ animationDelay: "180ms" }}>
            <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
              Emotion Flow
            </span>
            <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-4 shadow-hairline overflow-hidden">
              <EmotionFlow emotions={emotions} />
              <div className="flex flex-wrap gap-2 mt-3 justify-center">
                {Object.entries(emotions).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([name]) => (
                  <span key={name} className="flex items-center gap-1.5 text-[10px] text-gravel font-mono">
                    <span className="w-2 h-2 rounded-full" style={{ background: emotionColor(name) }} />
                    {name}
                  </span>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Bento grid — 2-column layout for visualizations */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-10">
          {/* Emotion Radar */}
          {Object.keys(emotions).length >= 3 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "240ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Emotional Palette
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-6 shadow-hairline h-full">
                <EmotionRadar emotions={emotions} />
              </div>
            </section>
          )}

          {/* Themes */}
          {Object.keys(themes).length > 0 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "320ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Top Themes
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-6 shadow-hairline h-full">
                <ThemeBar themes={themes} />
              </div>
            </section>
          )}

          {/* Structure Distribution */}
          {structures.length > 0 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "400ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Structure Breakdown
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-6 shadow-hairline h-full">
                <StructureDonut structures={structures} />
              </div>
            </section>
          )}

          {/* Creative Rhythm */}
          {Object.keys(hours).length > 0 && (
            <section className="space-y-3 animate-card-enter" style={{ animationDelay: "480ms" }}>
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Creative Rhythm
              </span>
              <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-6 shadow-hairline h-full">
                <HourlyHeatmap distribution={hours} />
              </div>
            </section>
          )}
        </div>

        {/* Style Cloud — full width bottom */}
        {styles.length > 0 && (
          <section className="space-y-3 animate-card-enter" style={{ animationDelay: "560ms" }}>
            <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
              Your Sound Palette
            </span>
            <div className="bg-white/50 backdrop-blur-sm rounded-[24px] p-6 shadow-hairline">
              <StyleCloud styles={styles} />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}
