interface HourlyHeatmapProps {
  distribution: Record<string, number>;
}

export function HourlyHeatmap({ distribution }: HourlyHeatmapProps) {
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const max = Math.max(...Object.values(distribution), 1);

  return (
    <div className="space-y-2">
      <div className="flex gap-[2px]">
        {hours.map((h) => {
          const val = distribution[String(h)] ?? 0;
          const intensity = val / max;
          return (
            <div
              key={h}
              className="flex-1 h-6 rounded-sm"
              style={{
                backgroundColor:
                  intensity > 0
                    ? `rgba(129, 140, 248, ${0.15 + intensity * 0.7})`
                    : "rgba(39, 39, 42, 0.5)",
              }}
              title={`${h}:00 — ${val} fragments`}
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-zinc-600">
        <span>0</span>
        <span>6</span>
        <span>12</span>
        <span>18</span>
        <span>24</span>
      </div>
    </div>
  );
}
