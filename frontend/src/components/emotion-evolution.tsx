"use client";

import { useEffect, useRef } from "react";

interface EmotionEvolutionProps {
  timeline: { week: string; emotions: Record<string, number> }[];
}

const PALETTE = [
  "#6b85c2", "#8fa3d0", "#a0b5eb", "#e2c161",
  "#ffa773", "#d4855a", "#b8c8e8",
];

export function EmotionEvolution({ timeline }: EmotionEvolutionProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || timeline.length < 2) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = 200;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const allEmotions = new Map<string, number>();
    for (const entry of timeline) {
      for (const [em, count] of Object.entries(entry.emotions)) {
        allEmotions.set(em, (allEmotions.get(em) ?? 0) + count);
      }
    }
    const topEmotions = [...allEmotions.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([name]) => name);

    const padL = 8;
    const padR = 8;
    const padT = 12;
    const padB = 28;
    const chartW = w - padL - padR;
    const chartH = h - padT - padB;
    const n = timeline.length;

    const totals = timeline.map((entry) =>
      topEmotions.reduce((s, em) => s + (entry.emotions[em] ?? 0), 0)
    );
    const maxTotal = Math.max(...totals, 1);

    let progress = 0;
    let rafId = 0;
    const duration = 50;

    function easeOut(t: number) {
      return 1 - Math.pow(1 - t, 3);
    }

    function draw() {
      progress = Math.min(progress + 1, duration);
      const t = easeOut(progress / duration);
      ctx!.clearRect(0, 0, w, h);

      // Draw stacked areas bottom-up
      for (let ei = topEmotions.length - 1; ei >= 0; ei--) {
        const em = topEmotions[ei];

        // Compute cumulative stacks at each x
        const yBottoms: number[] = [];
        const yTops: number[] = [];
        for (let xi = 0; xi < n; xi++) {
          let below = 0;
          for (let j = 0; j < ei; j++) {
            below += timeline[xi].emotions[topEmotions[j]] ?? 0;
          }
          const val = timeline[xi].emotions[em] ?? 0;
          const bNorm = (below / maxTotal) * chartH * t;
          const tNorm = ((below + val) / maxTotal) * chartH * t;
          yBottoms.push(padT + chartH - bNorm);
          yTops.push(padT + chartH - tNorm);
        }

        const color = PALETTE[ei % PALETTE.length];

        ctx!.beginPath();
        // Top edge (left to right)
        for (let xi = 0; xi < n; xi++) {
          const x = padL + (xi / (n - 1)) * chartW;
          if (xi === 0) ctx!.moveTo(x, yTops[xi]);
          else ctx!.lineTo(x, yTops[xi]);
        }
        // Bottom edge (right to left)
        for (let xi = n - 1; xi >= 0; xi--) {
          const x = padL + (xi / (n - 1)) * chartW;
          ctx!.lineTo(x, yBottoms[xi]);
        }
        ctx!.closePath();

        const grad = ctx!.createLinearGradient(0, padT, 0, padT + chartH);
        grad.addColorStop(0, color + "55");
        grad.addColorStop(1, color + "18");
        ctx!.fillStyle = grad;
        ctx!.fill();

        // Top stroke
        ctx!.beginPath();
        for (let xi = 0; xi < n; xi++) {
          const x = padL + (xi / (n - 1)) * chartW;
          if (xi === 0) ctx!.moveTo(x, yTops[xi]);
          else ctx!.lineTo(x, yTops[xi]);
        }
        ctx!.strokeStyle = color + "88";
        ctx!.lineWidth = 1.5;
        ctx!.stroke();
      }

      // Week labels — only show when enough data points
      if (n >= 4) {
        ctx!.font = "10px var(--font-ibm-plex-mono, monospace)";
        ctx!.fillStyle = "#a59f97";
        ctx!.textAlign = "center";
        const step = Math.max(1, Math.floor(n / 5));
        for (let xi = 0; xi < n; xi += step) {
          const x = padL + (xi / (n - 1)) * chartW;
          const label = timeline[xi].week.replace(/^\d{4}-W/, "Wk");
          ctx!.fillText(label, x, h - 6);
        }
        if (n - 1 > 0) {
          const lastX = padL + chartW;
          const lastLabel = timeline[n - 1].week.replace(/^\d{4}-W/, "Wk");
          ctx!.fillText(lastLabel, lastX, h - 6);
        }
      }

      if (progress < duration) {
        rafId = requestAnimationFrame(draw);
      }
    }

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
  }, [timeline]);

  if (timeline.length < 2) return null;

  const allEmotions = new Map<string, number>();
  for (const entry of timeline) {
    for (const [em, count] of Object.entries(entry.emotions)) {
      allEmotions.set(em, (allEmotions.get(em) ?? 0) + count);
    }
  }
  const legend = [...allEmotions.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div ref={containerRef} className="space-y-3">
      <canvas ref={canvasRef} className="w-full" />
      <div className="flex flex-wrap gap-3 justify-center">
        {legend.map(([name], i) => (
          <span key={name} className="flex items-center gap-1.5 text-[10px] text-gravel font-mono">
            <span
              className="w-2.5 h-2.5 rounded-sm"
              style={{ background: PALETTE[i % PALETTE.length] }}
            />
            {name}
          </span>
        ))}
      </div>
    </div>
  );
}
