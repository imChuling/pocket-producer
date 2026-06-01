"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useProjectDetail } from "@/hooks/use-projects";
import { RescueScore } from "@/components/rescue-score";
import { FragmentCard } from "@/components/fragment-card";

function scoreColor(score: number | null) {
  if (score === null) return "text-slate";
  if (score >= 70) return "text-obsidian";
  if (score >= 40) return "text-gravel";
  return "text-slate";
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
                <div
                  className="backdrop-blur-sm rounded-[24px] p-5 space-y-2 shadow-hairline gradient-border animate-card-enter"
                  style={{ animationDelay: "160ms", background: "linear-gradient(135deg, rgba(255,255,255,0.7), rgba(226,193,97,0.04))" }}
                >
                  <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                    Next Action
                  </span>
                  <p className="text-xs text-gravel/80 italic">{project.next_action.action}</p>
                  {project.next_action.estimated_time && (
                    <p className="text-xs text-gravel">
                      ~{project.next_action.estimated_time}
                    </p>
                  )}
                </div>
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
