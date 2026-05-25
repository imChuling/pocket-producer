import Link from "next/link";
import type { Project } from "@/types";

function scoreColor(score: number | null) {
  if (score === null) return "bg-zinc-700";
  if (score >= 70) return "bg-gradient-to-r from-emerald-500 to-emerald-400";
  if (score >= 40) return "bg-gradient-to-r from-amber-500 to-amber-400";
  return "bg-gradient-to-r from-red-500 to-red-400";
}

export function ProjectCard({ project }: { project: Project }) {
  const score = project.rescue_score;
  const pct = score !== null ? score : 0;

  return (
    <Link href={`/projects/${project._id}`} className="block cursor-pointer">
      <div className="bg-surface rounded-xl p-4 space-y-3 hover:bg-surface-raised transition-colors">
        <div className="flex items-baseline justify-between">
          <h3 className="font-heading text-base font-medium text-zinc-50">
            {project.title}
          </h3>
          {score !== null && (
            <span className="font-mono text-2xl font-light text-zinc-300">
              {score}
            </span>
          )}
        </div>
        <div className="h-1 rounded-full bg-zinc-800 overflow-hidden">
          <div
            className={`h-full rounded-full ${scoreColor(score)}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="text-xs text-zinc-500 space-x-1">
          <span>{(project.fragment_ids ?? []).length} fragments</span>
          {(project.sections ?? []).length > 0 && (
            <span>· {project.sections.join(" + ")}</span>
          )}
        </div>
        {project.next_action && (
          <p className="text-xs text-zinc-400">{project.next_action.action}</p>
        )}
      </div>
    </Link>
  );
}
