import type { ScoreBreakdown } from "@/types";

const dimensions = [
  { key: "richness" as const, label: "RICHNESS", max: 30 },
  { key: "structure" as const, label: "STRUCTURE", max: 30 },
  { key: "coherence" as const, label: "COHERENCE", max: 20 },
  { key: "freshness" as const, label: "FRESHNESS", max: 20 },
];

export function RescueScore({ breakdown }: { breakdown: ScoreBreakdown }) {
  return (
    <div className="space-y-3">
      {dimensions.map(({ key, label, max }) => {
        const value = breakdown[key] ?? 0;
        const pct = (value / max) * 100;
        return (
          <div key={key} className="flex items-center gap-3">
            <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500 w-24 shrink-0">
              {label}
            </span>
            <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-zinc-300 rounded-full transition-all duration-700 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="font-mono text-[13px] text-zinc-400 w-12 text-right">
              {value}/{max}
            </span>
          </div>
        );
      })}
    </div>
  );
}
