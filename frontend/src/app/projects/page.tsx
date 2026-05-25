"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Loader2, RefreshCw } from "lucide-react";
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

  if (authLoading || !user) return null;

  return (
    <div className="py-8 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-2xl font-medium text-zinc-50">
          Projects
        </h1>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors disabled:opacity-40 cursor-pointer"
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
      {scanResult && (
        <div className="text-xs text-zinc-400 text-center">{scanResult}</div>
      )}
      {loading ? (
        <div className="text-sm text-zinc-600">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <p className="text-sm text-zinc-500">No projects yet.</p>
          <p className="text-xs text-zinc-600">
            Projects are created automatically when related fragments are detected.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((p) => (
            <ProjectCard key={p._id} project={p} />
          ))}
        </div>
      )}
    </div>
  );
}
