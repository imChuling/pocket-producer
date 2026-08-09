"use client";

import { useEffect, useRef } from "react";

interface StyleBubblesProps {
  styles: { _id: string; count: number }[];
}

const HUE_LIST = [210, 25, 45, 220, 200, 30, 160, 280];
const NUM_MODES = 5; // harmonic modes 2..6
const SEGMENTS = 40;

interface Mode {
  amp: number;
  vel: number;
  phase: number;
}

interface Bubble {
  x: number;
  y: number;
  r: number;
  vx: number;
  vy: number;
  label: string;
  hue: number;
  modes: Mode[];
}

export function StyleBubbles({ styles }: StyleBubblesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || styles.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = 95;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const maxCount = Math.max(...styles.map((s) => s.count), 1);
    const minR = 14;
    const maxR = Math.min(28, w / 16);

    function makeModes(): Mode[] {
      return Array.from({ length: NUM_MODES }, () => ({
        amp: 0, vel: 0, phase: 0,
      }));
    }

    const bubbles: Bubble[] = styles.slice(0, 12).map((s, i, arr) => {
      const rankRatio = 1 - i / Math.max(arr.length - 1, 1);
      const countRatio = s.count / maxCount;
      const sizeRatio = countRatio * 0.6 + rankRatio * 0.4;
      const r = minR + (sizeRatio ** 0.5) * (maxR - minR);
      return {
        x: r + Math.random() * (w - r * 2),
        y: r + Math.random() * (h - r * 2),
        r,
        vx: (Math.random() - 0.5) * 1.4 + (Math.random() > 0.5 ? 0.4 : -0.4),
        vy: (Math.random() - 0.5) * 1.4 + (Math.random() > 0.5 ? 0.4 : -0.4),
        label: s._id,
        hue: HUE_LIST[i % HUE_LIST.length],
        modes: makeModes(),
      };
    });

    let rafId = 0;

    function excite(b: Bubble, angle: number, strength: number) {
      for (let m = 0; m < NUM_MODES; m++) {
        const contribution = strength * (m === 0 ? 1 : 0.6 / m);
        b.modes[m].vel += contribution;
        b.modes[m].phase = angle;
      }
    }

    function getRadius(b: Bubble, angle: number): number {
      let r = b.r;
      for (let m = 0; m < NUM_MODES; m++) {
        const modeN = m + 2;
        const mode = b.modes[m];
        r += mode.amp * b.r * Math.cos(modeN * (angle - mode.phase));
      }
      return Math.max(r * 0.65, r);
    }

    function getPoints(b: Bubble): [number, number][] {
      const pts: [number, number][] = [];
      for (let s = 0; s < SEGMENTS; s++) {
        const angle = (s / SEGMENTS) * Math.PI * 2;
        const r = getRadius(b, angle);
        pts.push([b.x + Math.cos(angle) * r, b.y + Math.sin(angle) * r]);
      }
      return pts;
    }

    function drawSmoothShape(pts: [number, number][]) {
      const n = pts.length;
      ctx!.moveTo(
        (pts[n - 1][0] + pts[0][0]) / 2,
        (pts[n - 1][1] + pts[0][1]) / 2,
      );
      for (let i = 0; i < n; i++) {
        const next = (i + 1) % n;
        const mx = (pts[i][0] + pts[next][0]) / 2;
        const my = (pts[i][1] + pts[next][1]) / 2;
        ctx!.quadraticCurveTo(pts[i][0], pts[i][1], mx, my);
      }
    }

    function drawBubble(b: Bubble) {
      const { x, y, r, hue } = b;
      const pts = getPoints(b);

      const bg = ctx!.createRadialGradient(
        x - r * 0.3, y - r * 0.35, r * 0.05,
        x, y, r,
      );
      bg.addColorStop(0, `hsla(${hue}, 60%, 90%, 0.65)`);
      bg.addColorStop(0.5, `hsla(${hue}, 50%, 80%, 0.35)`);
      bg.addColorStop(1, `hsla(${hue}, 45%, 72%, 0.18)`);
      ctx!.beginPath();
      drawSmoothShape(pts);
      ctx!.closePath();
      ctx!.fillStyle = bg;
      ctx!.fill();

      ctx!.beginPath();
      drawSmoothShape(pts);
      ctx!.closePath();
      ctx!.strokeStyle = `hsla(${hue}, 40%, 78%, 0.45)`;
      ctx!.lineWidth = 0.7;
      ctx!.stroke();

      const shine = ctx!.createRadialGradient(
        x - r * 0.28, y - r * 0.3, r * 0.02,
        x - r * 0.12, y - r * 0.12, r * 0.5,
      );
      shine.addColorStop(0, "rgba(255,255,255,0.75)");
      shine.addColorStop(1, "rgba(255,255,255,0)");
      ctx!.beginPath();
      ctx!.arc(x - r * 0.2, y - r * 0.22, r * 0.42, 0, Math.PI * 2);
      ctx!.fillStyle = shine;
      ctx!.fill();

      if (r > 12) {
        const fontSize = Math.max(7, Math.min(9, r * 0.3));
        ctx!.font = `${fontSize}px var(--font-ibm-plex-mono, monospace)`;
        ctx!.fillStyle = `hsla(${hue}, 30%, 35%, 0.8)`;
        ctx!.textAlign = "center";
        ctx!.textBaseline = "middle";
        const maxWidth = r * 1.6;
        const measured = ctx!.measureText(b.label).width;
        if (measured <= maxWidth) {
          ctx!.fillText(b.label, x, y);
        } else {
          const words = b.label.split(/[\s-]+/);
          if (words.length >= 2) {
            const mid = Math.ceil(words.length / 2);
            const line1 = words.slice(0, mid).join(" ");
            const line2 = words.slice(mid).join(" ");
            ctx!.fillText(line1, x, y - fontSize * 0.55);
            ctx!.fillText(line2, x, y + fontSize * 0.55);
          } else {
            ctx!.fillText(b.label, x, y);
          }
        }
      }
    }

    function step() {
      ctx!.clearRect(0, 0, w, h);

      for (const b of bubbles) {
        b.x += b.vx;
        b.y += b.vy;

        const margin = b.r + 2;
        if (b.x < margin) {
          b.x = margin; b.vx = Math.abs(b.vx) * 0.9;
          excite(b, Math.PI, 0.015);
        }
        if (b.x > w - margin) {
          b.x = w - margin; b.vx = -Math.abs(b.vx) * 0.9;
          excite(b, 0, 0.015);
        }
        if (b.y < margin) {
          b.y = margin; b.vy = Math.abs(b.vy) * 0.9;
          excite(b, -Math.PI / 2, 0.015);
        }
        if (b.y > h - margin) {
          b.y = h - margin; b.vy = -Math.abs(b.vy) * 0.9;
          excite(b, Math.PI / 2, 0.015);
        }
      }

      for (let i = 0; i < bubbles.length; i++) {
        for (let j = i + 1; j < bubbles.length; j++) {
          const a = bubbles[i];
          const b = bubbles[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const minDist = a.r + b.r;
          if (dist < minDist && dist > 0) {
            const nx = dx / dist;
            const ny = dy / dist;
            const overlap = minDist - dist;
            a.x -= nx * overlap * 0.5;
            a.y -= ny * overlap * 0.5;
            b.x += nx * overlap * 0.5;
            b.y += ny * overlap * 0.5;

            const dvx = a.vx - b.vx;
            const dvy = a.vy - b.vy;
            const dot = dvx * nx + dvy * ny;
            if (dot > 0) {
              a.vx -= dot * nx * 0.85;
              a.vy -= dot * ny * 0.85;
              b.vx += dot * nx * 0.85;
              b.vy += dot * ny * 0.85;
            }

            const hitAngle = Math.atan2(ny, nx);
            const imp = Math.min(0.025, overlap / minDist * 0.08 + 0.008);
            excite(a, hitAngle, imp);
            excite(b, hitAngle + Math.PI, imp);
          }
        }
      }

      for (const b of bubbles) {
        for (let m = 0; m < NUM_MODES; m++) {
          const modeN = m + 2;
          const stiffness = 0.015 * modeN;
          const damping = 0.97 - m * 0.008;
          const mode = b.modes[m];
          mode.vel -= mode.amp * stiffness;
          mode.vel *= damping;
          mode.amp += mode.vel;
          mode.amp = Math.max(-0.03, Math.min(0.03, mode.amp));
        }

        const speed = Math.sqrt(b.vx * b.vx + b.vy * b.vy);
        if (speed < 0.3 && speed > 0) {
          b.vx = (b.vx / speed) * 0.3;
          b.vy = (b.vy / speed) * 0.3;
        }
      }

      for (const b of bubbles) {
        drawBubble(b);
      }

      rafId = requestAnimationFrame(step);
    }

    rafId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafId);
  }, [styles]);

  if (styles.length === 0) return null;

  return (
    <div ref={containerRef}>
      <canvas ref={canvasRef} className="w-full" />
    </div>
  );
}
