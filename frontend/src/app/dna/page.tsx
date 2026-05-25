"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { apiFetch } from "@/lib/api";
import { EmotionRadar } from "@/components/emotion-radar";
import { ThemeBar } from "@/components/theme-bar";
import { HourlyHeatmap } from "@/components/hourly-heatmap";
import type { DNAData } from "@/types";

export default function DNAPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [dna, setDna] = useState<DNAData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    apiFetch<Record<string, unknown>>("/dna")
      .then((data) => {
        if (data && data.emotions) {
          setDna(data as unknown as DNAData);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  if (authLoading || !user) return null;

  if (loading) {
    return <div className="py-8 text-sm text-zinc-600">Loading...</div>;
  }

  if (!dna) {
    return (
      <div className="py-8 space-y-4 animate-fade-in">
        <h1 className="font-heading text-2xl font-light text-zinc-50">
          Your Creative DNA
        </h1>
        <p className="text-sm text-zinc-500">
          Not enough data yet. Keep capturing fragments!
        </p>
      </div>
    );
  }

  const emotions = dna.emotions ?? {};
  const themes = dna.themes ?? {};
  const hours = dna.hourly_distribution ?? {};

  return (
    <div className="py-8 space-y-10 animate-fade-in">
      <h1 className="font-heading text-2xl font-light text-zinc-50">
        Your Creative DNA
      </h1>

      {Object.keys(emotions).length >= 3 && (
        <section className="space-y-4">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">
            Emotional Palette
          </span>
          <EmotionRadar emotions={emotions} />
        </section>
      )}

      {Object.keys(themes).length > 0 && (
        <section className="space-y-4">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">
            Top Themes
          </span>
          <ThemeBar themes={themes} />
        </section>
      )}

      {Object.keys(hours).length > 0 && (
        <section className="space-y-4">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">
            Peak Hours
          </span>
          <HourlyHeatmap distribution={hours} />
        </section>
      )}

      <div className="text-xs text-zinc-600 font-mono text-center pt-4">
        {dna.total_fragments ?? 0} fragments · {dna.total_projects ?? 0} projects
      </div>
    </div>
  );
}
