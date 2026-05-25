interface ThemeBarProps {
  themes: Record<string, number>;
}

const barColors = [
  "bg-indigo-400",
  "bg-emerald-400",
  "bg-amber-400",
  "bg-red-400",
  "bg-blue-400",
];

export function ThemeBar({ themes }: ThemeBarProps) {
  const entries = Object.entries(themes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="space-y-2.5">
      {entries.map(([name, value], i) => {
        const pct = (value / max) * 100;
        return (
          <div key={name} className="flex items-center gap-3">
            <span className="text-sm text-zinc-400 w-28 truncate">{name}</span>
            <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${barColors[i % barColors.length]}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="font-mono text-xs text-zinc-500 w-8 text-right">
              {value}
            </span>
          </div>
        );
      })}
    </div>
  );
}
