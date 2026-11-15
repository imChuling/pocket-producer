"use client";

import { useState, useEffect } from "react";
import { Layers, RefreshCw } from "lucide-react";
import { useDemoToast } from "../demo-context";
import { loadDemo } from "../demo-data";
import { ProjectCard } from "@/components/project-card";
import type { Project } from "@/types";

export default function DemoProjectsPage() {
  const showToast = useDemoToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDemo<{ projects?: Project[] }>("projects", "projects")
      .then((data) => setProjects(data.projects ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="relative min-h-[calc(100vh-56px-44px)]">
      <div className="ambient-mesh" />
      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 space-y-6 animate-page-enter">
        {/* Header row */}
        <div className="flex items-end justify-between">
          <div className="space-y-1">
            <h1 className="font-heading text-3xl font-light tracking-tight shimmer-heading">
              Projects
            </h1>
            <p className="text-xs text-slate font-mono">
              {projects.length} project{projects.length !== 1 && "s"} assembled from fragments
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => showToast()}
              className="flex items-center gap-1.5 text-xs text-gravel hover:text-obsidian transition-colors cursor-pointer btn-press"
            >
              <Layers size={13} />
              Reset
            </button>
            <button
              onClick={() => showToast()}
              className="flex items-center gap-1.5 text-xs text-gravel hover:text-obsidian transition-colors cursor-pointer btn-press"
            >
              <RefreshCw size={13} />
              Scan
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 rounded-full border-2 border-chalk border-t-gravel animate-spin" />
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20 space-y-3 animate-fade-in">
            <div
              className="mx-auto w-16 h-16 rounded-full flex items-center justify-center mb-4 morph-blob"
              style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.3), rgba(255,148,115,0.15), rgba(226,193,97,0.1))" }}
            >
              <Layers size={24} className="text-gravel" />
            </div>
            <p className="text-sm text-gravel">No projects in the demo</p>
            <p className="text-xs text-slate max-w-[300px] mx-auto leading-relaxed">
              In a real account, AI groups related fragments into projects automatically when it finds shared emotion, key, or theme.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p, i) => (
              <div
                key={p._id}
                className="animate-card-enter"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <ProjectCard project={p} basePath="/demo/projects" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
