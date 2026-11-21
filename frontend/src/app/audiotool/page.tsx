"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
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
import { importProjectAsFragments, listImportableSampleNames } from "@/lib/audiotool/import-project";
import {
  describeSessionAudio,
  extractSessionAudio,
  needsSessionAudio,
  type SessionAudioCache,
} from "@/lib/audiotool/session-audio";
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
import type { NexusDocumentPort, ParsedIntent } from "@/types/audiotool";

export default function AudiotoolPage() {
  const { user, loading: authLoading } = useAuth();
  const audiotool = useAudiotool();
  const [importHistory] = useState(() => new Map<string, Set<string>>());
  const scope = JSON.stringify([user?.uid, audiotool.openProjectName]);
  const router = useRouter();
  const [openingProject, setOpeningProject] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>();

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
      ) : (
        <OpenSession
          key={scope}
          audiotool={audiotool}
          availableModels={availableModels}
          importHistory={importHistory}
          scope={scope}
        />
      )}
    </main>
  );
}

function OpenSession({
  audiotool, availableModels, importHistory, scope,
}: {
  audiotool: ReturnType<typeof useAudiotool>;
  availableModels?: string[];
  importHistory: Map<string, Set<string>>;
  scope: string;
}) {
  const [cursors, setCursors] = useState<string[]>([]);
  const before = cursors.at(-1) ?? null;
  const { fragments, refresh, loading, error: libraryError, nextCursor } = useFragments(before);
  const [intent, setIntent] = useState("");
  // LLM reading of the intent, already reviewed (chips) by the user.
  const [parsedIntent, setParsedIntent] = useState<ParsedIntent | null>(null);
  const [lastInsert, setLastInsert] = useState<{
    receipt: InsertReceipt;
    document: NexusDocumentPort;
    feedback: PanelFeedback;
    mirrorLink: Promise<unknown>;
    title: string;
  } | null>(null);
  const mutationInFlight = useRef(false);
  const [mutation, setMutation] = useState<"insert" | "undo" | null>(null);
  const [undoError, setUndoError] = useState<string | null>(null);
  const [importing, setImporting] = useState<{ done: number; total: number } | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [importComplete, setImportComplete] = useState(() => {
    const completed = importHistory.get(scope);
    const doc = audiotool.document();
    if (!doc || !completed) return false;
    const names = listImportableSampleNames(doc);
    return names.length > 0 && names.every((name) => completed.has(name));
  });
  // Tag sets of fragments inserted this session, in insert order.
  // Kept as a list (not a flat set) so undoing an insert also retracts
  // its tags from the fusion ranker's context.
  const [insertedTagSets, setInsertedTagSets] = useState<string[][]>([]);
  // Why audio-based rankers may have fallen back, shown next to the model chip.
  const [sessionAudioNote, setSessionAudioNote] = useState<string | null>(null);
  const sessionTags = useMemo(
    () => [...new Set(insertedTagSets.flat())],
    [insertedTagSets],
  );
  const preview = useRef<{
    controller: AbortController;
    audio?: HTMLAudioElement;
    url?: string;
  } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  // Session vectors keyed by the regions' sample set, so asking again for
  // an unchanged session does not re-download and re-encode its audio.
  const sessionAudioCacheRef = useRef<SessionAudioCache>(new Map());

  const releasePreview = useCallback(() => {
    const current = preview.current;
    if (!current) return;
    preview.current = null;
    current.controller.abort();
    if (current.audio) {
      current.audio.onended = null;
      current.audio.onerror = null;
      current.audio.pause();
    }
    if (current.url) URL.revokeObjectURL(current.url);
  }, []);

  useEffect(() => () => {
    releasePreview();
    setPreviewError(null);
  }, [before, releasePreview]);

  const activeImport = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      activeImport.current?.abort();
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
    releasePreview();
    setPreviewError(null);
    const controller = new AbortController();
    const { signal } = controller;
    preview.current = { controller };

    function failed() {
      if (signal.aborted) return;
      releasePreview();
      setPreviewError(`Couldn’t preview “${fragment.title ?? "Untitled fragment"}”. Try again.`);
    }

    try {
      const token = await getIdToken();
      if (signal.aborted) return;
      const response = await fetch(`/api/fragments/${fragment._id}/audio`, {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      });
      if (!response.ok) throw new Error("Could not load preview audio");
      const blob = await response.blob();
      if (signal.aborted) return;
      const url = URL.createObjectURL(blob);
      preview.current.url = url;
      const audio = new Audio(url);
      preview.current.audio = audio;
      audio.onended = () => {
        if (!signal.aborted) releasePreview();
      };
      audio.onerror = failed;
      await audio.play();
    } catch {
      failed();
    }
  }, [releasePreview]);

  const insertFragment = useCallback(
    async (fragment: Fragment, feedback: PanelFeedback) => {
      if (mutationInFlight.current) throw new Error("An Audiotool edit is in progress.");
      mutationInFlight.current = true;
      setMutation("insert");
      try {
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
        if (!mountedRef.current || audiotool.document() !== doc) {
          throw new Error("The project changed before insertion.");
        }
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
        // Serialize this receipt's mirror writes, independently of timeline edits.
        const projectName = feedback.project_id;
        const display = audiotool.projects.find((p) => p.name === projectName)?.displayName ?? "";
        const mirrorLink = linkAudiotoolInsert({
          audiotool_project_id: projectName,
          display_name: display,
          fragment_id: fragment._id,
          insertion_id: receipt.regionId,
        }).catch((cause) => console.warn("[audiotool-project] link failed:", cause));
        setLastInsert({
          receipt,
          document: doc,
          feedback: { ...feedback, insertion_id: receipt.regionId },
          title: fragment.title ?? "Fragment",
          mirrorLink,
        });
        setUndoError(null);
        setInsertedTagSets((previous) => [
          ...previous,
          fragment.tags.map((t) => t.toLowerCase()),
        ]);
        return receipt.regionId;
      } finally {
        mutationInFlight.current = false;
        setMutation(null);
      }
    },
    [audiotool, fingerprint],
  );

  const handleUndo = useCallback(async () => {
    if (!lastInsert || mutationInFlight.current) return;
    const doc = audiotool.document();
    if (doc !== lastInsert.document) return;
    mutationInFlight.current = true;
    setMutation("undo");
    setUndoError(null);
    try {
      await undoInsert(
        doc as unknown as Parameters<typeof undoInsert>[0],
        lastInsert.receipt,
      );
      sendFeedbackQueued({ ...lastInsert.feedback, event: "undo" });
      void lastInsert.mirrorLink
        .then(() => unlinkAudiotoolInsert({
          audiotool_project_id: lastInsert.feedback.project_id,
          fragment_id: lastInsert.receipt.fragmentId,
          insertion_id: lastInsert.receipt.regionId,
        }))
        .catch((cause) => console.warn("[audiotool-project] unlink failed:", cause));
      setLastInsert(null);
      setInsertedTagSets((previous) => previous.slice(0, -1));
    } catch (cause) {
      setUndoError(cause instanceof Error ? cause.message : "Could not undo the insertion. Try again.");
    } finally {
      mutationInFlight.current = false;
      setMutation(null);
    }
  }, [audiotool, lastInsert]);

  const handleImportProject = useCallback(async () => {
    const doc = audiotool.document();
    const samples = audiotool.samples();
    const projectName = audiotool.openProjectName;
    if (!doc || !samples || !projectName || activeImport.current) return;
    const controller = new AbortController();
    activeImport.current = controller;
    const display =
      audiotool.projects.find((p) => p.name === projectName)?.displayName ??
      projectName;
    setImporting({ done: 0, total: 0 });
    setImportMessage(null);
    try {
      const completed = importHistory.get(scope) ?? new Set<string>();
      importHistory.set(scope, completed);
      const result = await importProjectAsFragments(doc, samples, {
        projectDisplayName: display,
        signal: controller.signal,
        alreadyImported: completed,
        onImported: (name) => completed.add(name),
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
        setImportComplete(result.failed === 0 && result.imported > 0);
        if (result.imported > 0 && mountedRef.current) {
          if (before) setCursors([]);
          else await refresh();
        }
        setImportMessage(
          `Imported ${result.imported} of ${result.totalSamples} samples` +
            (result.failed > 0 ? ` (${result.failed} failed)` : "") +
            " into your library.",
        );
      }
    } catch {
      setImportMessage("Import failed. Please try again.");
    } finally {
      activeImport.current = null;
      setImporting(null);
    }
  }, [audiotool, importHistory, scope, before, refresh]);

  async function rankSuggestions(limit: number, modelId: string, skipped: ReadonlySet<string>) {
    const fresh = getFingerprint();
    if (!fresh) throw new Error("No session to rank against");
    fresh.context_tags = sessionTags;
    fresh.parsed_intent = parsedIntent;
    const doc = audiotool.document();
    const samplesApi = audiotool.samples();
    if (!needsSessionAudio(modelId)) {
      // This ranker does not use session audio: nothing is sent.
      setSessionAudioNote(null);
    } else if (doc && samplesApi) {
      try {
        const token = await getIdToken();
        if (!token) throw new Error("not authenticated");
        const result = await extractSessionAudio(doc, samplesApi, {
          backendUrl: "/api/ranking/session-embed",
          modelId,
          authToken: token,
          cache: sessionAudioCacheRef.current,
          bpm: fresh.bpm,
        });
        if (result.embeddings.length > 0) {
          fresh.region_audio_embeddings = result.embeddings;
        }
        if (result.chroma.length > 0) {
          fresh.region_chroma_vectors = result.chroma;
        }
        if (result.sessionBeats) {
          fresh.session_beats = result.sessionBeats;
        }
        setSessionAudioNote(describeSessionAudio(result));
      } catch (cause) {
        // Session audio is best-effort; rules-v1 ranks without it,
        // but the reason must be visible, not swallowed.
        console.warn("[session-audio] extraction failed:", cause);
        setSessionAudioNote(
          `Session audio unavailable: ${cause instanceof Error ? cause.message : String(cause)}`,
        );
      }
    } else {
      setSessionAudioNote(
        "Session audio unavailable: no open document or samples API.",
      );
    }
    const remaining = fragments.filter((fragment) => !skipped.has(fragment._id));
    return requestRecommendations(fresh, remaining, { limit, modelId });
  }

  return fingerprint ? (
    <>
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-medium text-obsidian">
          Continue this session
        </h1>
        <div className="flex items-center gap-4">
          <button
            type="button"
            disabled={importing !== null || importComplete}
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
            ) : importComplete ? (
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
      {!loading && !libraryError && !before && fragments.length === 0 && importing === null && !importMessage && (
        <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
          <span className="font-medium">Your library is empty.</span>{" "}
          Click{" "}
          <button
            type="button"
            onClick={() => void handleImportProject()}
            className="font-medium underline underline-offset-2 hover:text-sky-700"
          >
            Import samples to library
          </button>{" "}
          to turn this project&apos;s sounds into rankable fragments in
          about a minute, or record and upload ideas on the{" "}
          <Link href="/capture" className="font-medium underline underline-offset-2 hover:text-sky-700">
            Capture page
          </Link>
          .
        </div>
      )}
      {lastInsert && (
        <div className="flex items-center justify-between rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <span>
            Inserted “{lastInsert.title}” at the start of the timeline;
            check your Audiotool project.
          </span>
          <button
            type="button"
            disabled={mutation !== null}
            onClick={() => void handleUndo()}
            className="rounded-lg border border-emerald-400 px-3 py-1.5 text-emerald-900 hover:bg-emerald-100 disabled:opacity-60"
          >
            {mutation === "undo" ? "Undoing…" : "Undo"}
          </button>
        </div>
      )}
      {undoError && <p role="alert" className="text-sm text-red-600">{undoError}</p>}
      {(before || nextCursor) && (
        <nav aria-label="Library pages" className="flex items-center gap-4 text-sm">
          <span>Ranking sketches on page {cursors.length + 1}</span>
          {before && (
            <button type="button" disabled={importing !== null} onClick={() => setCursors(cursors.slice(0, -1))}>
              Newer sketches
            </button>
          )}
          {nextCursor && (
            <button type="button" disabled={importing !== null} onClick={() => setCursors([...cursors, nextCursor])}>
              Older sketches
            </button>
          )}
        </nav>
      )}
      {libraryError && (
        <p role="alert">{libraryError} <button type="button" onClick={() => void refresh()}>Retry</button></p>
      )}
      {loading && <p role="status">Loading sketches…</p>}
      {previewError && <p role="alert" className="text-sm text-red-600">{previewError}</p>}
      <ContinuationPanel
        libraryPage={before}
        libraryReady={!loading && (!libraryError || fragments.length > 0)}
        mutationPending={mutation !== null}
        fingerprint={fingerprint}
        fragments={fragments}
        availableModels={availableModels}
        requestRecommendations={rankSuggestions}
        intentText={intent}
        onIntentChange={setIntent}
        sessionAudioNote={sessionAudioNote}
        parsedIntent={parsedIntent}
        onParsedIntentChange={setParsedIntent}
        onPreview={previewFragment}
        onInsert={insertFragment}
        onFeedback={sendFeedbackQueued}
      />
    </>
  ) : (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-slate" />
    </div>
  );
}
