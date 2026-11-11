"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Link2 } from "lucide-react";
import { FragmentCard } from "@/components/fragment-card";
import { useDemoToast } from "../../demo-context";
import type { Fragment } from "@/types";

interface DemoProjectDetail {
  _id: string;
  title: string;
  rescue_score: number | null;
  fragment_ids: string[];
  fragments: Fragment[];
  sections: string[];
  connection_reasons?: string[];
  connection_types?: string[];
}

function scoreColor(score: number | null) {
  if (score === null) return "text-slate";
  if (score >= 70) return "text-obsidian";
  if (score >= 40) return "text-gravel";
  return "text-slate";
}

export default function DemoProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const showToast = useDemoToast();
  const [project, setProject] = useState<DemoProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/demo/projects/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then(setProject)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 rounded-full border-2 border-chalk border-t-gravel animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="py-20 text-center text-sm text-gravel">
        Project not found.
      </div>
    );
  }

  const reasons = project.connection_reasons ?? [];
  const types = project.connection_types ?? [];

  return (
    <div className="relative min-h-[calc(100vh-56px-44px)]">
      <div className="ambient-mesh" />

      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 space-y-6 animate-page-enter">
        {/* Back + Title */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/demo/projects")}
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

        {/* Two-column layout */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left sidebar */}
          <div className="lg:w-[340px] flex-shrink-0">
            <div className="lg:sticky lg:top-[calc(56px+44px+20px)] space-y-5">
              {/* Connection info */}
              {reasons.length > 0 && (
                <div
                  className="backdrop-blur-sm rounded-[24px] p-5 space-y-3 shadow-hairline animate-card-enter"
                  style={{
                    animationDelay: "120ms",
                    background:
                      "linear-gradient(135deg, rgba(255,255,255,0.7), rgba(160,181,235,0.06))",
                  }}
                >
                  <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                    Why these connect
                  </span>
                  {types.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {types.map((t) => (
                        <span
                          key={t}
                          className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-gravel px-2 py-0.5 rounded-full bg-powder/60"
                        >
                          <Link2 size={8} />
                          {t.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="space-y-2">
                    {reasons.map((r, i) => (
                      <p key={i} className="text-xs text-gravel/80 italic">
                        {r}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {/* Sections */}
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

              {/* Demo info */}
              <div
                className="rounded-xl px-4 py-3 text-[13px] text-gravel leading-relaxed"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(160,181,235,0.1), rgba(226,193,97,0.06))",
                }}
              >
                This is a read-only demo. In a real account, each project also
                gets a rescue score and a suggested next action.
              </div>
            </div>
          </div>

          {/* Right -- Fragments list */}
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
                    readOnly
                    onReadOnlyAction={() => showToast()}
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
