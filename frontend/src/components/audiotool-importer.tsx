"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Cable, ChevronDown, FolderOpen, Loader2, Check } from "lucide-react";
import { useAudiotool } from "@/hooks/use-audiotool";
import { listImportableSampleNames } from "@/lib/audiotool/import-project";
import { mixSamplesToWav } from "@/lib/audiotool/mix-samples";
import { getIdToken } from "@/lib/firebase";
import { linkAudiotoolInsert } from "@/lib/api";

interface AudiotoolImporterProps {
  onImported: () => void;
}

export function AudiotoolImporter({ onImported }: AudiotoolImporterProps) {
  const audiotool = useAudiotool();
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [importedProjects, setImportedProjects] = useState<Set<string>>(
    () => new Set(),
  );
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll for connection after opening auth in new tab.
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleConnect = useCallback(() => {
    // Open Audiotool page in a new tab instead of redirecting away.
    window.open("/audiotool", "_blank");
    setStatus("Connect in the new tab, then come back here.");
    // Poll until connected (restore picks up the Nexus session).
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      if (
        audiotool.status === "connected" ||
        audiotool.status === "project-open"
      ) {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setStatus(null);
      }
    }, 1000);
  }, [audiotool.status]);

  const handleSelectAndOpen = useCallback(
    async (projectName: string) => {
      setSelectedProject(projectName);
      setStatus(null);
      try {
        await audiotool.openProject(projectName);
      } catch {
        setStatus("Could not open project.");
      }
    },
    [audiotool],
  );

  const handleImport = useCallback(async () => {
    if (!selectedProject || importing) return;
    const doc = audiotool.document();
    const samples = audiotool.samples();
    if (!doc || !samples) return;

    const display =
      audiotool.projects.find((p) => p.name === selectedProject)
        ?.displayName ?? selectedProject;
    setImporting(true);
    setStatus("Downloading samples...");
    try {
      const sampleNames = listImportableSampleNames(doc);
      if (sampleNames.length === 0) {
        setStatus("No audio found in this project.");
        setImporting(false);
        return;
      }

      // Download all samples.
      const blobs: Blob[] = [];
      for (const name of sampleNames) {
        const blob = await samples.download(name, { format: "wav" });
        if (!(blob instanceof Error)) {
          const wavBlob =
            blob.type === "audio/wav"
              ? blob
              : new Blob([blob], { type: "audio/wav" });
          blobs.push(wavBlob);
        }
      }
      if (blobs.length === 0) {
        setStatus("Could not download any samples.");
        setImporting(false);
        return;
      }

      // Mix all samples into one audio file.
      setStatus("Mixing audio...");
      const mixed = await mixSamplesToWav(blobs);

      // Upload as a single fragment named after the project.
      setStatus("Saving to library...");
      const formData = new FormData();
      formData.append("file", mixed, `${display}.wav`);
      formData.append(
        "text",
        `Imported from Audiotool project "${display}".`,
      );
      const token = await getIdToken();
      if (!token) throw new Error("Not signed in");
      const response = await fetch("/api/ingest", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (response.ok) {
        const data = (await response.json()) as { fragment_id: string };
        // Create a Pocket Producer project mirroring this Audiotool project.
        await linkAudiotoolInsert({
          audiotool_project_id: selectedProject,
          display_name: display,
          fragment_id: data.fragment_id,
        }).catch(() => {});
        setImportedProjects((prev) => new Set(prev).add(selectedProject));
        setStatus(`Imported "${display}"`);
        onImported();
      } else {
        setStatus("Upload failed.");
      }
    } catch {
      setStatus("Import failed.");
    } finally {
      setImporting(false);
    }
  }, [audiotool, selectedProject, importing, onImported]);

  const notConnected =
    audiotool.status === "idle" ||
    audiotool.status === "authorizing" ||
    audiotool.status === "error";

  // Not connected: button opens /audiotool in new tab.
  if (notConnected) {
    return (
      <div>
        <button
          type="button"
          onClick={handleConnect}
          className="flex w-full items-center justify-center gap-2.5 py-5 px-4 rounded-[20px] border border-dashed border-chalk hover:border-slate/50 cursor-pointer transition-all duration-300"
          style={{ background: "rgba(255,255,255,0.3)" }}
        >
          <div className="w-8 h-8 rounded-full bg-powder flex items-center justify-center">
            <Cable size={14} className="text-slate" />
          </div>
          <span className="text-sm text-gravel">Import from Audiotool</span>
        </button>
        {status && (
          <p className="text-[11px] text-gravel mt-2 text-center">{status}</p>
        )}
      </div>
    );
  }

  // Connected: project picker + import button.
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
            disabled={importing}
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

      <div className="px-4 pb-3">
        <button
          type="button"
          onClick={() => void handleImport()}
          disabled={!isProjectOpen || importing || alreadyImported}
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
              {status ?? "Importing..."}
            </>
          ) : alreadyImported ? (
            <>
              <Check size={14} />
              Imported
            </>
          ) : (
            <>
              <FolderOpen size={14} />
              Import project audio
            </>
          )}
        </button>
      </div>

      {!importing && status && (
        <div className="px-4 pb-3">
          <p className="text-[11px] text-gravel leading-snug">{status}</p>
        </div>
      )}
    </div>
  );
}
