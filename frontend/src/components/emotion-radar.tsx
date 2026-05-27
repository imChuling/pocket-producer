"use client";

import { useEffect, useRef } from "react";

interface EmotionRadarProps {
  emotions: Record<string, number>;
}

/**
 * Custom Canvas-drawn radar / flower chart with gradient fills,
 * animated draw-in, and glowing dots.
 */
export function EmotionRadar({ emotions }: EmotionRadarProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const entries = Object.entries(emotions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 7);
  const max = Math.max(...entries.map(([, v]) => v), 1);
  const data = entries.map(([name, value]) => ({
    name,
    value: (value / max) * 100,
  }));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length < 3) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = 320;
    const h = 320;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const cx = w / 2;
    const cy = h / 2;
    const maxR = 120;
    const rings = 4;
    const n = data.length;
    let progress = 0;
    let rafId = 0;
    const duration = 60; // frames

    function draw() {
      progress = Math.min(progress + 1, duration);
      const t = easeOutCubic(progress / duration);
      ctx!.clearRect(0, 0, w, h);

      // — Grid rings —
      for (let r = 1; r <= rings; r++) {
        const radius = (r / rings) * maxR;
        ctx!.beginPath();
        ctx!.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx!.strokeStyle = `rgba(0,0,0,${0.04})`;
        ctx!.lineWidth = 0.5;
        ctx!.stroke();
      }

      // — Axis lines + labels —
      for (let i = 0; i < n; i++) {
        const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
        const ex = cx + Math.cos(angle) * maxR;
        const ey = cy + Math.sin(angle) * maxR;
        ctx!.beginPath();
        ctx!.moveTo(cx, cy);
        ctx!.lineTo(ex, ey);
        ctx!.strokeStyle = "rgba(0,0,0,0.04)";
        ctx!.lineWidth = 0.5;
        ctx!.stroke();

        // Label
        const labelR = maxR + 18;
        const lx = cx + Math.cos(angle) * labelR;
        const ly = cy + Math.sin(angle) * labelR;
        ctx!.font = "11px var(--font-ibm-plex-mono, monospace)";
        ctx!.fillStyle = "#777169";
        ctx!.textAlign = "center";
        ctx!.textBaseline = "middle";
        ctx!.fillText(data[i].name, lx, ly);
      }

      // — Filled shape with gradient —
      const points: [number, number][] = [];
      for (let i = 0; i < n; i++) {
        const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
        const r = (data[i].value / 100) * maxR * t;
        points.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]);
      }

      // Gradient fill
      const grad = ctx!.createRadialGradient(cx, cy, 0, cx, cy, maxR);
      grad.addColorStop(0, "rgba(160,181,235,0.25)");
      grad.addColorStop(0.5, "rgba(255,148,115,0.12)");
      grad.addColorStop(1, "rgba(226,193,97,0.06)");

      ctx!.beginPath();
      ctx!.moveTo(points[0][0], points[0][1]);
      // Smooth curves between points
      for (let i = 0; i < n; i++) {
        const curr = points[i];
        const next = points[(i + 1) % n];
        const cpx = (curr[0] + next[0]) / 2;
        const cpy = (curr[1] + next[1]) / 2;
        ctx!.quadraticCurveTo(curr[0], curr[1], cpx, cpy);
      }
      ctx!.closePath();
      ctx!.fillStyle = grad;
      ctx!.fill();

      // Stroke outline
      ctx!.beginPath();
      ctx!.moveTo(points[0][0], points[0][1]);
      for (let i = 0; i < n; i++) {
        const curr = points[i];
        const next = points[(i + 1) % n];
        const cpx = (curr[0] + next[0]) / 2;
        const cpy = (curr[1] + next[1]) / 2;
        ctx!.quadraticCurveTo(curr[0], curr[1], cpx, cpy);
      }
      ctx!.closePath();
      const strokeGrad = ctx!.createLinearGradient(cx - maxR, cy - maxR, cx + maxR, cy + maxR);
      strokeGrad.addColorStop(0, "rgba(160,181,235,0.7)");
      strokeGrad.addColorStop(0.5, "rgba(255,148,115,0.5)");
      strokeGrad.addColorStop(1, "rgba(226,193,97,0.6)");
      ctx!.strokeStyle = strokeGrad;
      ctx!.lineWidth = 2;
      ctx!.stroke();

      // — Dots with glow —
      for (let i = 0; i < n; i++) {
        const [px, py] = points[i];
        // Glow
        const dotGlow = ctx!.createRadialGradient(px, py, 0, px, py, 12);
        const dotT = i / n;
        const glowR = Math.round(160 + dotT * 95);
        const glowG = Math.round(181 - dotT * 40);
        const glowB = Math.round(235 - dotT * 120);
        dotGlow.addColorStop(0, `rgba(${glowR},${glowG},${glowB},0.3)`);
        dotGlow.addColorStop(1, "transparent");
        ctx!.beginPath();
        ctx!.arc(px, py, 12, 0, Math.PI * 2);
        ctx!.fillStyle = dotGlow;
        ctx!.fill();
        // Solid dot
        ctx!.beginPath();
        ctx!.arc(px, py, 3.5, 0, Math.PI * 2);
        ctx!.fillStyle = `rgb(${glowR},${glowG},${glowB})`;
        ctx!.fill();
        ctx!.strokeStyle = "white";
        ctx!.lineWidth = 1.5;
        ctx!.stroke();
      }

      if (progress < duration) {
        rafId = requestAnimationFrame(draw);
      }
    }

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
  }, [data]);

  if (data.length < 3) return null;

  return (
    <div className="flex justify-center">
      <canvas ref={canvasRef} className="max-w-full" />
    </div>
  );
}

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}
