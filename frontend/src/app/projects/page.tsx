"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Loader2, RefreshCw, Layers } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useProjects } from "@/hooks/use-projects";
import { apiPost } from "@/lib/api";
import { ProjectCard } from "@/components/project-card";

export default function ProjectsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { projects, loading, refresh } = useProjects();
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const handleScan = useCallback(async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const res = await apiPost<{ message: string; processed: number }>(
        "/reprocess-projects",
        {},
      );
      setScanResult(res.message);
      if (res.processed > 0) refresh();
    } catch {
      setScanResult("Scan failed");
    } finally {
      setScanning(false);
      setTimeout(() => setScanResult(null), 4000);
    }
  }, [refresh]);

  const handleReset = useCallback(async () => {
    setResetting(true);
    setScanResult(null);
    try {
      const res = await apiPost<{ deleted_projects: number }>("/reset-projects", {});
      setScanResult(`Reset ${res.deleted_projects} projects. Use Scan to re-group.`);
      refresh();
    } catch {
      setScanResult("Reset failed");
    } finally {
      setResetting(false);
      setTimeout(() => setScanResult(null), 6000);
    }
  }, [refresh]);

  if (authLoading || !user) return null;

  return (
    <div className="relative min-h-[calc(100vh-56px)]">
      {/* Ambient background */}
      <div className="ambient-mesh" />

      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 space-y-6 animate-page-enter">
        {/* Header row */}
        <div className="flex items-end justify-between">
          <div className="space-y-1">
            <h1 className="font-heading text-3xl font-light tracking-tight shimmer-heading">
              Projects
            </h1>
            <p className="text-xs text-slate font-mono">
              {projects.length} project{projects.length !== 1 && "s"} assembled from your fragments
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleReset}
              disabled={resetting || scanning}
              className="flex items-center gap-1.5 text-xs text-gravel hover:text-red-500 transition-colors disabled:opacity-40 cursor-pointer btn-press"
              title="Reset all projects and re-group from scratch"
            >
              {resetting ? <Loader2 size={13} className="animate-spin" /> : <Layers size={13} />}
              Reset
            </button>
            <button
              onClick={handleScan}
              disabled={scanning || resetting}
              className="flex items-center gap-1.5 text-xs text-gravel hover:text-obsidian transition-colors disabled:opacity-40 cursor-pointer btn-press"
              title="Scan fragments for project connections"
            >
              {scanning ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <RefreshCw size={13} />
              )}
              Scan
            </button>
          </div>
        </div>

        {scanResult && (
          <div className="text-xs text-gravel text-center animate-fade-in">{scanResult}</div>
        )}

        {loading ? (
          <div className="text-sm text-slate">Loading...</div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20 space-y-3 animate-fade-in">
            <div className="mx-auto w-16 h-16 rounded-full flex items-center justify-center mb-4 morph-blob" style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.3), rgba(255,148,115,0.15), rgba(226,193,97,0.1))" }}>
              <Layers size={24} className="text-gravel" />
            </div>
            <p className="text-sm text-gravel">No projects yet.</p>
            <p className="text-xs text-slate">
              Projects are created automatically when related fragments are detected.
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
                <ProjectCard project={p} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
