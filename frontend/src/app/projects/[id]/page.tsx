"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, SkipForward } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useProjectDetail } from "@/hooks/use-projects";
import { apiPost } from "@/lib/api";
import { RescueScore } from "@/components/rescue-score";
import { FragmentCard } from "@/components/fragment-card";
import type { NextAction } from "@/types";

function scoreColor(score: number | null) {
  if (score === null) return "text-slate";
  if (score >= 70) return "text-obsidian";
  if (score >= 40) return "text-gravel";
  return "text-slate";
}

function NextActionCard({
  projectId,
  action,
  onUpdate,
}: {
  projectId: string;
  action: NextAction;
  onUpdate: (newAction: NextAction | null, newScore?: number | null) => void;
}) {
  const [busy, setBusy] = useState<"done" | "skip" | null>(null);
  const [current, setCurrent] = useState(action);

  async function handleDone() {
    setBusy("done");
    try {
      const res = await apiPost<{
        new_action: NextAction | null;
        rescue_score: number | null;
      }>(`/projects/${projectId}/complete-action`, { note: "" });
      const next = res.new_action ?? null;
      setCurrent(next ?? { action: "All caught up!", estimated_time: "" });
      onUpdate(next, res.rescue_score);
    } catch {
      /* silent */
    } finally {
      setBusy(null);
    }
  }

  async function handleSkip() {
    setBusy("skip");
    try {
      const res = await apiPost<{ new_action: NextAction | null }>(
        `/projects/${projectId}/skip-action`,
        {}
      );
      const next = res.new_action ?? { action: "All caught up!", estimated_time: "" };
      setCurrent(next);
      onUpdate(res.new_action ?? null);
    } catch {
      /* silent */
    } finally {
      setBusy(null);
    }
  }

  return (
    <div
      className="backdrop-blur-sm rounded-[24px] p-5 space-y-3 shadow-hairline gradient-border animate-card-enter"
      style={{
        animationDelay: "160ms",
        background:
          "linear-gradient(135deg, rgba(255,255,255,0.7), rgba(226,193,97,0.04))",
      }}
    >
      <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
        Next Action
      </span>
      <p className="text-xs text-gravel/80 italic">{current.action}</p>
      {current.estimated_time && (
        <p className="text-xs text-gravel">~{current.estimated_time}</p>
      )}
      <div className="flex gap-2 pt-1">
        <button
          onClick={handleDone}
          disabled={!!busy}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-obsidian text-white text-[11px] font-medium tracking-wide hover:bg-obsidian/85 transition-colors disabled:opacity-40"
        >
          <Check size={12} />
          {busy === "done" ? "Saving..." : "Done"}
        </button>
        <button
          onClick={handleSkip}
          disabled={!!busy}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-chalk text-gravel text-[11px] font-medium tracking-wide hover:border-slate/40 transition-colors disabled:opacity-40"
        >
          <SkipForward size={12} />
          {busy === "skip" ? "Generating..." : "Skip"}
        </button>
      </div>
    </div>
  );
}

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { project, loading, refresh } = useProjectDetail(id);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  if (authLoading || !user) return null;

  if (loading) {
    return <div className="py-8 text-sm text-slate">Loading...</div>;
  }

  if (!project) {
    return <div className="py-8 text-sm text-gravel">Project not found.</div>;
  }

  return (
    <div className="relative min-h-[calc(100vh-56px)]">
      {/* Ambient background */}
      <div className="ambient-mesh" />

      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 space-y-6 animate-page-enter">
        {/* Back + Title */}
        <div className="relative">
          {project.rescue_score !== null && project.rescue_score >= 60 && (
            <div
              className="absolute -top-4 -right-4 w-24 h-24 rounded-full pointer-events-none opacity-30"
              style={{
                background: "radial-gradient(circle, rgba(160,181,235,0.5) 0%, transparent 70%)",
              }}
            />
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.back()}
              className="p-2 -ml-2 rounded-full hover:bg-powder cursor-pointer transition-colors btn-press"
              aria-label="Back"
            >
              <ArrowLeft size={18} className="text-gravel" />
            </button>
            <h1 className="font-heading text-2xl font-light text-obsidian flex-1 tracking-tight">
              {project.title}
            </h1>
            {project.rescue_score !== null && (
              <span
                className={`font-mono text-3xl font-light animate-count-up ${scoreColor(project.rescue_score)}`}
              >
                {project.rescue_score}
              </span>
            )}
          </div>
        </div>

        {/* Two-column layout */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left — Score + Next Action (sticky) */}
          <div className="lg:w-[340px] flex-shrink-0">
            <div className="lg:sticky lg:top-20 space-y-5">
              {project.score_breakdown && (
                <div
                  className="backdrop-blur-sm rounded-[24px] p-5 shadow-hairline animate-card-enter"
                  style={{ animationDelay: "80ms", background: "linear-gradient(135deg, rgba(255,255,255,0.7), rgba(160,181,235,0.05))" }}
                >
                  <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate block mb-4">
                    Rescue Score
                  </span>
                  <RescueScore breakdown={project.score_breakdown} />
                </div>
              )}

              {(project.connection_reasons ?? []).length > 0 && (
                <div
                  className="backdrop-blur-sm rounded-[24px] p-5 space-y-3 shadow-hairline animate-card-enter"
                  style={{ animationDelay: "120ms", background: "linear-gradient(135deg, rgba(255,255,255,0.7), rgba(160,181,235,0.06))" }}
                >
                  <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                    Why these connect
                  </span>
                  {(project.connection_types ?? []).length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {project.connection_types!.map((t: string) => (
                        <span key={t} className="text-[10px] font-mono uppercase tracking-wider text-gravel px-2 py-0.5 rounded-full bg-powder/60">
                          {t.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="space-y-2">
                    {project.connection_reasons!.map((r: string, i: number) => (
                      <p key={i} className="text-xs text-gravel/80 italic">{r}</p>
                    ))}
                  </div>
                </div>
              )}

              {project.next_action && (
                <NextActionCard
                  projectId={project._id}
                  action={project.next_action}
                  onUpdate={(a, score) => {
                    project.next_action = a ?? undefined;
                    if (score !== undefined) project.rescue_score = score;
                  }}
                />
              )}

              {/* Sections summary */}
              {(project.sections ?? []).length > 0 && (
                <div className="flex flex-wrap gap-1.5 animate-card-enter" style={{ animationDelay: "240ms" }}>
                  {project.sections.map((s) => (
                    <span
                      key={s}
                      className="text-[11px] font-medium px-3 py-1.5 rounded-full bg-powder text-gravel"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right — Fragments list */}
          <div className="flex-1 min-w-0">
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                  {project.fragments.length} Fragments
                </span>
                <div className="flex-1 h-px bg-gradient-to-r from-chalk to-transparent" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {project.fragments.map((f) => (
                  <FragmentCard
                    key={f._id}
                    fragment={f}
                    onDeleted={refresh}
                    onUpdated={refresh}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
