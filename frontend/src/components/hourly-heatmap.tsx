"use client";

import { useEffect, useRef } from "react";

interface HourlyHeatmapProps {
  distribution: Record<string, number>;
}

/**
 * Radial clock heatmap — 24-hour ring where each segment's
 * radius and color intensity reflect fragment count.
 */
export function HourlyHeatmap({ distribution }: HourlyHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const max = Math.max(...Object.values(distribution), 1);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const size = 200;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const innerR = 34;
    const maxBarR = 60;
    const gapAngle = 0.012; // small gap between segments
    let progress = 0;
    let rafId = 0;
    const duration = 50;

    function heatColor(intensity: number): string {
      const r = Math.round(160 + intensity * 95);
      const g = Math.round(181 - intensity * 60);
      const b = Math.round(235 - intensity * 140);
      return `rgb(${r},${g},${b})`;
    }

    function draw() {
      progress = Math.min(progress + 1, duration);
      const t = easeOutCubic(progress / duration);
      ctx!.clearRect(0, 0, size, size);

      // Background ring
      ctx!.beginPath();
      ctx!.arc(cx, cy, innerR - 2, 0, Math.PI * 2);
      ctx!.fillStyle = "rgba(245,243,241,0.5)";
      ctx!.fill();

      // Hour segments
      const segAngle = (Math.PI * 2) / 24;
      for (let i = 0; i < 24; i++) {
        const val = distribution[String(i)] ?? 0;
        const intensity = val / max;
        const startAngle = i * segAngle - Math.PI / 2 + gapAngle;
        const endAngle = (i + 1) * segAngle - Math.PI / 2 - gapAngle;
        const barR = innerR + (intensity * maxBarR * t);

        // Segment
        ctx!.beginPath();
        ctx!.arc(cx, cy, barR, startAngle, endAngle);
        ctx!.arc(cx, cy, innerR, endAngle, startAngle, true);
        ctx!.closePath();

        const segGrad = ctx!.createRadialGradient(cx, cy, innerR, cx, cy, barR);
        const color = heatColor(intensity);
        segGrad.addColorStop(0, intensity > 0 ? `${color}` : "rgba(229,229,229,0.3)");
        segGrad.addColorStop(1, intensity > 0 ? `${color}` : "rgba(229,229,229,0.15)");
        ctx!.fillStyle = segGrad;
        ctx!.globalAlpha = intensity > 0 ? 0.3 + intensity * 0.7 : 0.15;
        ctx!.fill();
        ctx!.globalAlpha = 1;

        // Glow for high-intensity
        if (intensity > 0.6) {
          ctx!.shadowColor = color;
          ctx!.shadowBlur = 8 * intensity;
          ctx!.beginPath();
          ctx!.arc(cx, cy, barR, startAngle, endAngle);
          ctx!.arc(cx, cy, innerR, endAngle, startAngle, true);
          ctx!.closePath();
          ctx!.fillStyle = `${color}`;
          ctx!.globalAlpha = 0.15;
          ctx!.fill();
          ctx!.globalAlpha = 1;
          ctx!.shadowColor = "transparent";
          ctx!.shadowBlur = 0;
        }
      }

      // Center label
      const totalFrags = Object.values(distribution).reduce((s, v) => s + v, 0);
      ctx!.font = "18px var(--font-cormorant, Georgia)";
      ctx!.fillStyle = "#000000";
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
      ctx!.fillText(String(totalFrags), cx, cy - 4);
      ctx!.font = "8px var(--font-ibm-plex-mono, monospace)";
      ctx!.fillStyle = "#a59f97";
      ctx!.fillText("total", cx, cy + 9);

      if (progress < duration) {
        rafId = requestAnimationFrame(draw);
      }
    }

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
  }, [distribution, max]);

  // Also keep a simple bar below for detail on hover
  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <canvas ref={canvasRef} className="max-w-full" />
      </div>
      {/* Mini linear bar below for fine detail */}
      <div className="flex gap-[2px]">
        {hours.map((h) => {
          const val = distribution[String(h)] ?? 0;
          const intensity = val / max;
          const r = Math.round(160 + intensity * 95);
          const g = Math.round(181 - intensity * 60);
          const b = Math.round(235 - intensity * 140);
          return (
            <div
              key={h}
              className="flex-1 h-2 rounded-full transition-colors animate-cell-rise"
              style={{
                backgroundColor: intensity > 0
                  ? `rgba(${r},${g},${b},${0.2 + intensity * 0.6})`
                  : "#f5f3f1",
                animationDelay: `${h * 25}ms`,
              }}
              title={`${h}:00 — ${val} fragments`}
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-slate px-0.5">
        <span>0:00</span>
        <span>6:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>23:00</span>
      </div>
    </div>
  );
}

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}
