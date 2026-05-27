"use client";

import { useEffect, useRef } from "react";

interface ThemeBarProps {
  themes: Record<string, number>;
}

const gradients = [
  ["#a0b5eb", "#7b8fcc"],   // atmosphere blue
  ["#ffa773", "#d4855a"],   // sunset orange
  ["#e2c161", "#c4a44e"],   // amber glow
  ["#b8c8e8", "#8fa3d0"],   // soft sky
  ["#f0c490", "#d4a06a"],   // warm sand
  ["#c0cce6", "#96a8c8"],   // muted steel
];

export function ThemeBar({ themes }: ThemeBarProps) {
  const entries = Object.entries(themes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="space-y-4">
      {entries.map(([name, value], i) => {
        const pct = (value / max) * 100;
        const [from, to] = gradients[i % gradients.length];
        return (
          <ThemeBarRow
            key={name}
            name={name}
            value={value}
            pct={pct}
            from={from}
            to={to}
            delay={i * 100}
          />
        );
      })}
    </div>
  );
}

function ThemeBarRow({
  name, value, pct, from, to, delay,
}: {
  name: string; value: number; pct: number;
  from: string; to: string; delay: number;
}) {
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = barRef.current;
    if (!el) return;
    // Animate width from 0
    el.style.width = "0%";
    const timeout = setTimeout(() => {
      el.style.transition = "width 800ms cubic-bezier(0.16,1,0.3,1)";
      el.style.width = `${pct}%`;
    }, delay + 100);
    return () => clearTimeout(timeout);
  }, [pct, delay]);

  return (
    <div className="group animate-card-enter" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-obsidian font-medium">{name}</span>
        <span className="font-mono text-xs text-slate">{value}</span>
      </div>
      <div className="relative h-[6px] bg-powder rounded-full overflow-hidden">
        <div
          ref={barRef}
          className="h-full rounded-full"
          style={{
            background: `linear-gradient(90deg, ${from}, ${to})`,
            boxShadow: `0 0 8px ${from}40`,
          }}
        />
      </div>
    </div>
  );
}
