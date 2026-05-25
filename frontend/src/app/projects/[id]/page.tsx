"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Music, PenLine } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useProjectDetail } from "@/hooks/use-projects";
import { RescueScore } from "@/components/rescue-score";

function scoreColor(score: number | null) {
  if (score === null) return "text-zinc-500";
  if (score >= 70) return "text-emerald-400";
  if (score >= 40) return "text-amber-400";
  return "text-red-400";
}

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { project, loading } = useProjectDetail(id);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  if (authLoading || !user) return null;

  if (loading) {
    return <div className="py-8 text-sm text-zinc-600">Loading...</div>;
  }

  if (!project) {
    return <div className="py-8 text-sm text-zinc-500">Project not found.</div>;
  }

  return (
    <div className="py-8 space-y-6 animate-fade-in">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="p-2 -ml-2 rounded-full hover:bg-surface-raised cursor-pointer transition-colors"
          aria-label="Back"
        >
          <ArrowLeft size={18} className="text-zinc-400" />
        </button>
        <h1 className="font-heading text-xl font-medium text-zinc-50 flex-1">
          {project.title}
        </h1>
        {project.rescue_score !== null && (
          <span
            className={`font-mono text-3xl font-light ${scoreColor(project.rescue_score)}`}
          >
            {project.rescue_score}
          </span>
        )}
      </div>

      {project.score_breakdown && (
        <RescueScore breakdown={project.score_breakdown} />
      )}

      {project.next_action && (
        <div className="bg-surface rounded-xl p-4 space-y-1">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">
            Next Action
          </span>
          <p className="text-sm text-zinc-300">{project.next_action.action}</p>
          {project.next_action.estimated_time && (
            <p className="text-xs text-zinc-500">
              ~{project.next_action.estimated_time}
            </p>
          )}
        </div>
      )}

      <div className="space-y-3">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">
          {project.fragments.length} Fragments
        </span>
        <div className="space-y-2">
          {project.fragments.map((f) => (
            <div key={f._id} className="flex gap-3 py-2">
              <div className="pt-0.5">
                {f.type === "audio" ? (
                  <Music size={14} className="text-zinc-600" />
                ) : (
                  <PenLine size={14} className="text-zinc-600" />
                )}
              </div>
              <div className="flex-1 space-y-1">
                {f.text ? (
                  <p className="text-sm text-zinc-300 italic line-clamp-2">
                    &ldquo;{f.text}&rdquo;
                  </p>
                ) : (
                  <p className="text-sm text-zinc-400">Audio fragment</p>
                )}
                <p className="text-xs text-zinc-500 font-mono">
                  {[f.key, f.bpm ? `${f.bpm} BPM` : null, ...f.emotions]
                    .filter(Boolean)
                    .join(" · ")}
                  {f.created_at &&
                    ` · ${new Date(f.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
