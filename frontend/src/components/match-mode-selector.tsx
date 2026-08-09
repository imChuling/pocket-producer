"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";

type MatchMode = "strict" | "balanced" | "loose";

const MODES: { value: MatchMode; label: string; hint: string }[] = [
  { value: "strict", label: "Strict", hint: "Only group on strong same-song evidence" },
  { value: "balanced", label: "Balanced", hint: "Default matching behavior" },
  { value: "loose", label: "Loose", hint: "Surface more speculative connections" },
];

export function MatchModeSelector() {
  const [mode, setMode] = useState<MatchMode | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch<{ mode: MatchMode }>("/settings/match-mode");
        if (!cancelled) setMode(res.mode);
      } catch {
        if (!cancelled) setMode("balanced");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function select(next: MatchMode) {
    if (next === mode || saving) return;
    const prev = mode;
    setMode(next);
    setSaving(true);
    try {
      await apiPost("/settings/match-mode", { mode: next });
    } catch {
      setMode(prev);
    } finally {
      setSaving(false);
    }
  }

  if (mode === null) return null;

  return (
    <div
      className="flex items-center rounded-full p-0.5"
      style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.12), rgba(226,193,97,0.08))" }}
      role="radiogroup"
      aria-label="Match strictness"
    >
      {MODES.map((m) => (
        <button
          key={m.value}
          onClick={() => select(m.value)}
          title={m.hint}
          role="radio"
          aria-checked={mode === m.value}
          className={`font-mono text-[10px] px-2 py-0.5 rounded-full transition-all cursor-pointer ${
            mode === m.value
              ? "bg-white text-obsidian shadow-sm"
              : "text-slate hover:text-gravel"
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
