import type { ScoreBreakdown } from "@/types";

const dimensions = [
  { key: "richness" as const, label: "RICHNESS", max: 30, gradient: "from-[#a0b5eb] to-[#6366f1]" },
  { key: "structure_completeness" as const, label: "STRUCTURE", max: 30, gradient: "from-[#ffa773] to-[#e06030]" },
  { key: "emotional_coherence" as const, label: "COHERENCE", max: 20, gradient: "from-[#e2c161] to-[#d4940a]" },
  { key: "freshness" as const, label: "FRESHNESS", max: 20, gradient: "from-[#a7fccd] to-[#34d399]" },
];

export function RescueScore({ breakdown }: { breakdown: ScoreBreakdown }) {
  return (
    <div className="space-y-3.5">
      {dimensions.map(({ key, label, max, gradient }, i) => {
        const value = breakdown[key] ?? 0;
        const pct = (value / max) * 100;
        return (
          <div
            key={key}
            className="flex items-center gap-3 animate-card-enter"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate w-24 shrink-0">
              {label}
            </span>
            <div className="flex-1 h-[4px] bg-powder rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${gradient} animate-bar-fill`}
                style={{ width: `${pct}%`, animationDelay: `${200 + i * 100}ms` }}
              />
            </div>
            <span className="font-mono text-[13px] text-gravel w-12 text-right animate-count-up" style={{ animationDelay: `${400 + i * 80}ms` }}>
              {value}/{max}
            </span>
          </div>
        );
      })}
    </div>
  );
}
