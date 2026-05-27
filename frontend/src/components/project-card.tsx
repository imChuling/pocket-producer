import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { Project } from "@/types";

function scoreBarStyle(score: number | null): React.CSSProperties {
  if (score === null) return {};
  if (score >= 70) return { background: "linear-gradient(90deg, #a0b5eb, #ffa773)" };
  if (score >= 40) return { background: "linear-gradient(90deg, #8fa3d0, #a0b5eb)" };
  return { background: "#a59f97" };
}

export function ProjectCard({ project }: { project: Project }) {
  const score = project.rescue_score;
  const pct = score !== null ? score : 0;
  const fragmentCount = (project.fragment_ids ?? []).length;

  return (
    <Link href={`/projects/${project._id}`} className="block cursor-pointer group">
      <div
        className="backdrop-blur-sm rounded-[24px] p-5 space-y-4 shadow-hairline card-3d gradient-border h-full flex flex-col"
        style={{
          background: "linear-gradient(135deg, rgba(255,255,255,0.8), rgba(160,181,235,0.04), rgba(255,255,255,0.7))",
        }}
      >
        {/* Title + score */}
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-heading text-lg font-light text-obsidian tracking-tight leading-snug">
            {project.title}
          </h3>
          {score !== null && (
            <span className="font-mono text-2xl font-light text-obsidian animate-count-up flex-shrink-0">
              {score}
            </span>
          )}
        </div>

        {/* Score bar */}
        <div className="h-[3px] rounded-full bg-powder overflow-hidden">
          <div
            className="h-full rounded-full animate-bar-fill"
            style={{ width: `${pct}%`, ...scoreBarStyle(score) }}
          />
        </div>

        {/* Meta */}
        <div className="flex-1 space-y-2">
          <div className="text-xs text-gravel">
            <span>{fragmentCount} fragment{fragmentCount !== 1 && "s"}</span>
            {(project.sections ?? []).length > 0 && (
              <span> · {project.sections.join(" + ")}</span>
            )}
          </div>
          {project.next_action && (
            <p className="text-xs text-slate line-clamp-2">{project.next_action.action}</p>
          )}
        </div>

        {/* Footer hint */}
        <div className="flex items-center justify-end pt-1">
          <span className="text-[11px] text-slate flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            Open <ArrowRight size={11} />
          </span>
        </div>
      </div>
    </Link>
  );
}
