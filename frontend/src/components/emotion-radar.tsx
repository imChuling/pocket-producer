"use client";

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

interface EmotionRadarProps {
  emotions: Record<string, number>;
}

export function EmotionRadar({ emotions }: EmotionRadarProps) {
  const entries = Object.entries(emotions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 7);
  const max = Math.max(...entries.map(([, v]) => v), 1);
  const data = entries.map(([name, value]) => ({
    name,
    value: (value / max) * 100,
  }));

  if (data.length < 3) return null;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
        <PolarGrid stroke="#27272A" strokeWidth={0.5} />
        <PolarAngleAxis
          dataKey="name"
          tick={{
            fontSize: 11,
            fontFamily: "var(--font-ibm-plex-mono)",
            fill: "#A1A1AA",
          }}
        />
        <Radar
          dataKey="value"
          stroke="rgba(129,140,248,0.5)"
          strokeWidth={1.5}
          fill="rgba(129,140,248,0.12)"
          dot={{ fill: "#818CF8", r: 3, strokeWidth: 0 }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
