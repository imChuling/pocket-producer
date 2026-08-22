"use client";

import { useCallback, useState } from "react";
import { Cable, ChevronDown, FolderOpen, Loader2, Check } from "lucide-react";
import { useAudiotool } from "@/hooks/use-audiotool";
import { importProjectAsFragments } from "@/lib/audiotool/import-project";
import { getIdToken } from "@/lib/firebase";

interface AudiotoolImporterProps {
  onImported: () => void;
}

export function AudiotoolImporter({ onImported }: AudiotoolImporterProps) {
  const audiotool = useAudiotool();
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [importing, setImporting] = useState<{
    done: number;
    total: number;
  } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [importedProjects, setImportedProjects] = useState<Set<string>>(
    () => new Set(),
  );

  const handleImport = useCallback(async () => {
    if (!selectedProject || importing) return;
    const doc = audiotool.document();
    const samples = audiotool.samples();
    if (!doc || !samples) return;

    const display =
      audiotool.projects.find((p) => p.name === selectedProject)
        ?.displayName ?? selectedProject;
    setImporting({ done: 0, total: 0 });
    setMessage(null);
    try {
      const result = await importProjectAsFragments(doc, samples, {
        projectDisplayName: display,
        getAuthToken: async () => {
          const token = await getIdToken();
          if (!token) throw new Error("Not signed in");
          return token;
        },
        onProgress: (done, total) => setImporting({ done, total }),
      });
      if (result.totalSamples === 0) {
        setMessage("No importable samples found.");
      } else {
        setImportedProjects((prev) => new Set(prev).add(selectedProject));
        setMessage(
          `Imported ${result.imported} of ${result.totalSamples} sample${result.totalSamples > 1 ? "s" : ""}` +
            (result.failed > 0 ? ` (${result.failed} failed)` : ""),
        );
        onImported();
      }
    } catch {
      setMessage("Import failed.");
    } finally {
      setImporting(null);
    }
  }, [audiotool, selectedProject, importing, onImported]);

  const handleSelectAndOpen = useCallback(
    async (projectName: string) => {
      setSelectedProject(projectName);
      setMessage(null);
      try {
        await audiotool.openProject(projectName);
      } catch {
        setMessage("Could not open project.");
      }
    },
    [audiotool],
  );

  // Not connected: show connect button
  if (
    audiotool.status === "idle" ||
    audiotool.status === "authorizing" ||
    audiotool.status === "error"
  ) {
    return (
      <button
        type="button"
        onClick={() => void audiotool.connect()}
        disabled={audiotool.status === "authorizing"}
        className="flex w-full items-center justify-center gap-2.5 py-5 px-4 rounded-[20px] border border-dashed border-chalk hover:border-slate/50 cursor-pointer transition-all duration-300"
        style={{ background: "rgba(255,255,255,0.3)" }}
      >
        <div className="w-8 h-8 rounded-full bg-powder flex items-center justify-center">
          {audiotool.status === "authorizing" ? (
            <Loader2 size={14} className="text-slate animate-spin" />
          ) : (
            <Cable size={14} className="text-slate" />
          )}
        </div>
        <span className="text-sm text-gravel">
          {audiotool.status === "authorizing"
            ? "Connecting..."
            : "Import from Audiotool"}
        </span>
      </button>
    );
  }

  // Connected: show project picker + import button
  const isProjectOpen = audiotool.status === "project-open" && selectedProject;
  const alreadyImported =
    selectedProject !== null && importedProjects.has(selectedProject);

  return (
    <div
      className="rounded-[20px] border border-chalk overflow-hidden transition-all duration-300"
      style={{ background: "rgba(255,255,255,0.5)" }}
    >
      <div className="px-4 py-3 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-full bg-powder flex items-center justify-center flex-shrink-0">
          <Cable size={14} className="text-slate" />
        </div>
        <div className="flex-1 min-w-0 relative">
          <select
            value={selectedProject ?? ""}
            onChange={(e) => {
              if (e.target.value) {
                void handleSelectAndOpen(e.target.value);
              }
            }}
            disabled={importing !== null}
            className="w-full appearance-none bg-transparent text-sm text-gravel outline-none cursor-pointer pr-5 truncate"
          >
            <option value="">Select a project...</option>
            {audiotool.projects.map((p) => (
              <option key={p.name} value={p.name}>
                {p.displayName}
              </option>
            ))}
          </select>
          <ChevronDown
            size={12}
            className="absolute right-0 top-1/2 -translate-y-1/2 text-slate pointer-events-none"
          />
        </div>
      </div>

      {isProjectOpen && (
        <div className="px-4 pb-3">
          <button
            type="button"
            onClick={() => void handleImport()}
            disabled={importing !== null || alreadyImported}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-sm transition-all duration-200 disabled:opacity-50"
            style={{
              background: alreadyImported
                ? "rgba(160,181,235,0.1)"
                : "rgba(160,181,235,0.15)",
              color: "var(--gravel, #777169)",
            }}
          >
            {importing ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                {importing.total > 0
                  ? `Importing ${importing.done}/${importing.total}...`
                  : "Importing..."}
              </>
            ) : alreadyImported ? (
              <>
                <Check size={14} />
                Imported
              </>
            ) : (
              <>
                <FolderOpen size={14} />
                Import samples to library
              </>
            )}
          </button>
        </div>
      )}

      {message && (
        <div className="px-4 pb-3">
          <p className="text-[11px] text-gravel leading-snug">{message}</p>
        </div>
      )}
    </div>
  );
}
