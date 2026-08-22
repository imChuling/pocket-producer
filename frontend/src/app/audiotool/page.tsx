"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderOpen, Loader2, Unplug } from "lucide-react";

import { ConnectionPanel } from "@/components/audiotool/connection-panel";
import {
  ContinuationPanel,
  type PanelFeedback,
} from "@/components/audiotool/continuation-panel";
import { useAudiotool } from "@/hooks/use-audiotool";
import { useAuth } from "@/hooks/use-auth";
import { useFragments } from "@/hooks/use-fragments";
import {
  insertFragment as nexusInsertFragment,
  undoInsert,
  type InsertReceipt,
} from "@/lib/audiotool/insert-fragment";
import { importProjectAsFragments } from "@/lib/audiotool/import-project";
import { extractSessionAudio } from "@/lib/audiotool/session-audio";
import { fingerprintFromDocument } from "@/lib/audiotool/session-fingerprint";
import { linkAudiotoolInsert, unlinkAudiotoolInsert } from "@/lib/api";
import { getIdToken } from "@/lib/firebase";
import {
  fetchModelCards,
  requestRecommendations,
  sendFeedbackQueued,
  toCandidates,
} from "@/lib/ranking-api";
import type { Fragment } from "@/types";

export default function AudiotoolPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const audiotool = useAudiotool();
  const { fragments } = useFragments();
  const [intent, setIntent] = useState("");
  const [openingProject, setOpeningProject] = useState<string | null>(null);
  const [lastInsert, setLastInsert] = useState<{
    receipt: InsertReceipt;
    feedback: PanelFeedback | null;
    title: string;
  } | null>(null);
  const [undoing, setUndoing] = useState(false);
  const [importing, setImporting] = useState<{ done: number; total: number } | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  // Projects already imported this session, so the button can't double-ingest.
  const [importedProjects, setImportedProjects] = useState<Set<string>>(
    () => new Set(),
  );
  const [availableModels, setAvailableModels] = useState<string[]>();
  // Tag sets of fragments inserted this session, in insert order.
  // Kept as a list (not a flat set) so undoing an insert also retracts
  // its tags from the fusion ranker's context.
  const [insertedTagSets, setInsertedTagSets] = useState<string[][]>([]);
  const sessionTags = useMemo(
    () => [...new Set(insertedTagSets.flat())],
    [insertedTagSets],
  );
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    fetchModelCards()
      .then((cards) => {
        if (!cancelled) setAvailableModels(cards.models.map((m) => m.id));
      })
      .catch(() => {
        // Selector falls back to the guaranteed rules-v1 entry.
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  function getFingerprint(): ReturnType<typeof fingerprintFromDocument> | null {
    const doc = audiotool.document();
    if (!doc?.queryEntities || audiotool.openProjectName === null) return null;
    return fingerprintFromDocument(
      { queryEntities: doc.queryEntities },
      {
        projectId: audiotool.openProjectName,
        textIntent: intent,
      },
    );
  }

  const fingerprint = getFingerprint();

  const previewFragment = useCallback(async (fragment: Fragment) => {
    const token = await getIdToken();
    const response = await fetch(`/api/fragments/${fragment._id}/audio`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Could not load preview audio");
    const url = URL.createObjectURL(await response.blob());
    audioRef.current?.pause();
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => URL.revokeObjectURL(url);
    await audio.play();
  }, []);

  const insertFragment = useCallback(
    async (fragment: Fragment) => {
      const doc = audiotool.document();
      const samples = audiotool.samples();
      if (!doc || !samples) {
        throw new Error("No open Audiotool project to insert into");
      }
      const candidate = toCandidates([fragment])[0];
      if (!candidate) {
        throw new Error("This fragment has no playable audio to insert");
      }
      const token = await getIdToken();
      const response = await fetch(`/api/fragments/${fragment._id}/audio`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Could not load the fragment's audio");
      const audioBlob = await response.blob();
      const receipt = await nexusInsertFragment(
        {
          samples,
          document: doc as unknown as Parameters<
            typeof nexusInsertFragment
          >[0]["document"],
        },
        {
          fragmentId: fragment._id,
          title: fragment.title ?? "Pocket Producer fragment",
          durationSeconds: candidate.duration_seconds,
          bpm: candidate.bpm,
        },
        {
          audioBlob,
          playheadSeconds: fingerprint?.playhead_seconds ?? 0,
          projectBpm: fingerprint?.bpm ?? null,
        },
      );
      setLastInsert({
        receipt,
        feedback: null,
        title: fragment.title ?? "Fragment",
      });
      setInsertedTagSets((previous) => [
        ...previous,
        fragment.tags.map((t) => t.toLowerCase()),
      ]);
      // Mirror the insertion into the Projects view so the Audiotool
      // session shows up alongside capture-pipeline projects. Best-effort:
      // a failure must not break the insert the musician just made.
      const projectName = audiotool.openProjectName;
      if (projectName) {
        const display =
          audiotool.projects.find((p) => p.name === projectName)
            ?.displayName ?? "";
        linkAudiotoolInsert({
          audiotool_project_id: projectName,
          display_name: display,
          fragment_id: fragment._id,
        }).catch((cause) => {
          console.warn("[audiotool-project] link failed:", cause);
        });
      }
    },
    [audiotool, fingerprint],
  );

  const handleFeedback = useCallback((feedback: PanelFeedback) => {
    sendFeedbackQueued(feedback);
    if (feedback.event === "insert") {
      setLastInsert((previous) =>
        previous && previous.feedback === null
          ? { ...previous, feedback }
          : previous,
      );
    }
  }, []);

  const handleUndo = useCallback(async () => {
    if (!lastInsert || undoing) return;
    const doc = audiotool.document();
    if (!doc) return;
    setUndoing(true);
    try {
      await undoInsert(
        doc as unknown as Parameters<typeof undoInsert>[0],
        lastInsert.receipt,
      );
      if (lastInsert.feedback) {
        sendFeedbackQueued({ ...lastInsert.feedback, event: "undo" });
      }
      // The undone insert must also leave the Projects view (best-effort).
      if (audiotool.openProjectName) {
        unlinkAudiotoolInsert({
          audiotool_project_id: audiotool.openProjectName,
          fragment_id: lastInsert.receipt.fragmentId,
        }).catch((cause) => {
          console.warn("[audiotool-project] unlink failed:", cause);
        });
      }
      setLastInsert(null);
      // The undone insert's tags must leave the ranking context too.
      setInsertedTagSets((previous) => previous.slice(0, -1));
    } finally {
      setUndoing(false);
    }
  }, [audiotool, lastInsert, undoing]);

  const handleImportProject = useCallback(async () => {
    const doc = audiotool.document();
    const samples = audiotool.samples();
    const projectName = audiotool.openProjectName;
    if (!doc || !samples || !projectName || importing) return;
    const display =
      audiotool.projects.find((p) => p.name === projectName)?.displayName ??
      projectName;
    setImporting({ done: 0, total: 0 });
    setImportMessage(null);
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
        setImportMessage("No importable samples found in this project.");
      } else {
        setImportedProjects((previous) => new Set(previous).add(projectName));
        setImportMessage(
          `Imported ${result.imported} of ${result.totalSamples} samples` +
            (result.failed > 0 ? ` (${result.failed} failed)` : "") +
            " into your library.",
        );
      }
    } catch {
      setImportMessage("Import failed — please try again.");
    } finally {
      setImporting(null);
    }
  }, [audiotool, importing]);

  if (authLoading || !user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate" />
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 space-y-6">
      {audiotool.status === "idle" || audiotool.status === "authorizing" ? (
        <ConnectionPanel
          status={audiotool.status}
          error={audiotool.error}
          onConnect={() => void audiotool.connect()}
        />
      ) : audiotool.status === "error" ? (
        <ConnectionPanel
          status={audiotool.status}
          error={audiotool.error}
          onConnect={() => void audiotool.connect()}
        />
      ) : audiotool.status === "connected" ? (
        <section className="mx-auto max-w-md space-y-4">
          <header className="flex items-center justify-between">
            <h1 className="text-lg font-medium text-obsidian">
              Open a project
            </h1>
            {audiotool.userName && (
              <span className="text-sm text-slate">
                {audiotool.userName}
              </span>
            )}
          </header>
          {audiotool.projects.length === 0 ? (
            <p className="rounded-xl border border-chalk bg-powder p-6 text-center text-sm text-slate">
              No Audiotool projects found for this account yet. Create one in
              Audiotool, then reconnect.
            </p>
          ) : (
            <ul className="space-y-2">
              {audiotool.projects.map((project) => (
                <li key={project.name}>
                  <button
                    type="button"
                    disabled={openingProject !== null}
                    onClick={() => {
                      setOpeningProject(project.name);
                      void audiotool
                        .openProject(project.name)
                        .catch(() => {})
                        .finally(() => setOpeningProject(null));
                    }}
                    className="flex w-full items-center gap-3 rounded-xl border border-chalk bg-surface px-4 py-3 text-left text-gravel hover:bg-powder disabled:opacity-60"
                  >
                    {openingProject === project.name ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FolderOpen className="h-4 w-4 text-slate" />
                    )}
                    {project.displayName}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {audiotool.error && (
            <p role="alert" className="text-sm text-red-600">
              {audiotool.error}
            </p>
          )}
        </section>
      ) : fingerprint ? (
        <>
          <header className="flex items-center justify-between">
            <h1 className="text-lg font-medium text-obsidian">
              Continue this session
            </h1>
            <div className="flex items-center gap-4">
              <button
                type="button"
                disabled={
                  importing !== null ||
                  (audiotool.openProjectName !== null &&
                    importedProjects.has(audiotool.openProjectName))
                }
                onClick={() => void handleImportProject()}
                className="inline-flex items-center gap-1.5 text-sm text-slate hover:text-gravel disabled:opacity-50"
              >
                {importing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {importing.total > 0
                      ? `Importing ${importing.done}/${importing.total}…`
                      : "Importing…"}
                  </>
                ) : audiotool.openProjectName !== null &&
                  importedProjects.has(audiotool.openProjectName) ? (
                  "Samples imported ✓"
                ) : (
                  "Import samples to library"
                )}
              </button>
              <button
                type="button"
                onClick={() => void audiotool.closeProject()}
                className="inline-flex items-center gap-1.5 text-sm text-slate hover:text-gravel"
              >
                <Unplug className="h-4 w-4" /> Close project
              </button>
            </div>
          </header>
          {importMessage && (
            <p className="rounded-xl border border-chalk bg-powder px-4 py-2.5 text-sm text-gravel">
              {importMessage}
            </p>
          )}
          {lastInsert && (
            <div className="flex items-center justify-between rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              <span>
                Inserted “{lastInsert.title}” at{" "}
                {lastInsert.receipt.insertedAtSeconds.toFixed(1)}s — check your
                Audiotool timeline.
              </span>
              <button
                type="button"
                disabled={undoing}
                onClick={() => void handleUndo()}
                className="rounded-lg border border-emerald-400 px-3 py-1.5 text-emerald-900 hover:bg-emerald-100 disabled:opacity-60"
              >
                {undoing ? "Undoing…" : "Undo"}
              </button>
            </div>
          )}
          <ContinuationPanel
            fingerprint={fingerprint}
            fragments={fragments}
            availableModels={availableModels}
            requestRecommendations={async (limit: number, modelId: string) => {
              const fresh = getFingerprint();
              if (!fresh) throw new Error("No session to rank against");
              fresh.context_tags = sessionTags;
              const doc = audiotool.document();
              const samplesApi = audiotool.samples();
              if (doc && samplesApi) {
                try {
                  const token = await getIdToken();
                  if (!token) throw new Error("not authenticated");
                  const result = await extractSessionAudio(doc, samplesApi, {
                    backendUrl: "/api/ranking/session-embed",
                    authToken: token,
                  });
                  if (result.embeddings.length > 0) {
                    fresh.region_audio_embeddings = result.embeddings;
                  } else {
                    console.info(
                      "[session-audio] no embeddings: " +
                        `samples=${result.sampleCount} failed=${result.failedCount}`,
                    );
                  }
                } catch (cause) {
                  // Session audio is best-effort; rules-v1 ranks without it —
                  // but the reason must be visible, not swallowed.
                  console.warn("[session-audio] extraction failed:", cause);
                }
              } else {
                console.info(
                  `[session-audio] unavailable: doc=${!!doc} samples=${!!samplesApi}`,
                );
              }
              return requestRecommendations(fresh, fragments, { limit, modelId });
            }}
            onIntentChange={setIntent}
            onPreview={previewFragment}
            onInsert={insertFragment}
            onFeedback={handleFeedback}
          />
        </>
      ) : (
        <main className="flex min-h-[40vh] items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-slate" />
        </main>
      )}
    </main>
  );
}
