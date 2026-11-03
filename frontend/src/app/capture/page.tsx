"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Send, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useAuth } from "@/hooks/use-auth";
import { useFragments } from "@/hooks/use-fragments";
import { apiPost } from "@/lib/api";
import { AudioRecorder } from "@/components/audio-recorder";
import { FileDropzone } from "@/components/file-dropzone";
import { AudiotoolImporter } from "@/components/audiotool-importer";
import { FragmentCard } from "@/components/fragment-card";
import { MatchModeSelector } from "@/components/match-mode-selector";
import { GuidedTour } from "@/components/guided-tour";

// Capture is the library-building flow: record, type, drop audio, or import
// from Audiotool. The session flow at /audiotool ranks what is captured here.
export default function CapturePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);
  if (authLoading || !user) return null;
  return <CaptureDashboard />;
}

function CaptureDashboard() {
  const { user } = useAuth();
  const { fragments, loading, refresh } = useFragments();
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  // Recomputed in an effect (not during render) because the age check
  // reads the clock; re-runs whenever the fragment list changes.
  const [stuckCount, setStuckCount] = useState(0);
  useEffect(() => {
    const compute = () =>
      setStuckCount(
        fragments.filter((f) => {
          if (f.status !== "processing") return false;
          if (f.tags && f.tags.length > 0) return true;
          const age = Date.now() - new Date(f.created_at).getTime();
          return age > 2 * 60 * 1000;
        }).length,
      );
    const timer = setTimeout(compute, 0);
    const interval = setInterval(compute, 30_000);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [fragments]);

  const handleFixStuck = useCallback(async () => {
    try {
      await apiPost("/fix-stuck", {});
      refresh();
    } catch {}
  }, [refresh]);

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 6) return "Late night session";
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  })();

  const firstName = user?.displayName?.split(" ")[0] ?? "";

  const handleRecorded = useCallback(
    async (blob: Blob) => {
      setSubmitting(true);
      setStatus("Processing audio...");
      try {
        const form = new FormData();
        const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
        form.append("file", blob, `recording.${ext}`);
        await apiPost("/ingest", form);
        setStatus("Saved — AI analysis takes ~30–60s");
        refresh();
      } catch (e) {
        setStatus(e instanceof Error ? e.message : "Processing failed");
      } finally {
        setSubmitting(false);
        setTimeout(() => setStatus(null), 5000);
      }
    },
    [refresh],
  );

  const handleFile = useCallback(
    async (file: File) => {
      setSubmitting(true);
      setStatus("Uploading...");
      try {
        const form = new FormData();
        form.append("file", file);
        await apiPost("/ingest", form);
        setStatus("Saved — AI analysis takes ~30–60s");
        refresh();
      } catch (e) {
        setStatus(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setSubmitting(false);
        setTimeout(() => setStatus(null), 5000);
      }
    },
    [refresh],
  );

  async function submitText() {
    if (!text.trim() || submitting) return;
    setSubmitting(true);
    setStatus("Processing...");
    try {
      const form = new FormData();
      form.append("text", text.trim());
      await apiPost("/ingest", form);
      setText("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "20px";
        textareaRef.current.style.overflowY = "hidden";
      }
      setStatus("Saved!");
      refresh();
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
      setTimeout(() => setStatus(null), 3000);
    }
  }

  return (
    <div className="relative min-h-[calc(100vh-56px)]">
      <div className="ambient-mesh" />
      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 animate-page-enter">
        <div className="flex flex-col lg:flex-row gap-8 lg:gap-10">
          <div className="lg:w-[340px] flex-shrink-0">
            <div className="lg:sticky lg:top-20 space-y-6" data-tour="capture">
              <div className="space-y-1">
                <p className="font-mono text-[10px] font-medium uppercase tracking-[0.3em] text-slate">
                  {greeting}{firstName ? `, ${firstName}` : ""}
                </p>
                <h1 className="font-heading text-3xl font-light text-obsidian tracking-tight leading-[1.08]">
                  Capture a moment
                </h1>
              </div>
              <div className="flex flex-col items-center py-4">
                <div className="relative">
                  <div
                    className="absolute inset-0 -m-10 rounded-full opacity-40 pointer-events-none"
                    style={{
                      background: "radial-gradient(circle, rgba(160,181,235,0.18) 0%, rgba(226,193,97,0.06) 50%, transparent 70%)",
                      filter: "blur(24px)",
                    }}
                  />
                  <AudioRecorder onRecorded={handleRecorded} />
                </div>
              </div>
              <AnimatePresence>
                {status && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, filter: "blur(4px)" }}
                    animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                    exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
                    transition={{ type: "spring", stiffness: 200, damping: 20 }}
                    className="flex items-center justify-center gap-2 text-sm text-gravel"
                  >
                    {submitting && <Loader2 size={14} className="animate-spin" />}
                    {status}
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="flex items-center gap-2 bg-white rounded-2xl px-5 py-3 shadow-hairline gradient-border">
                <textarea
                  ref={textareaRef}
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    const el = e.target;
                    el.style.height = "0";
                    el.style.height = `${el.scrollHeight}px`;
                    el.style.overflowY = el.scrollHeight > 200 ? "auto" : "hidden";
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      submitText();
                    }
                  }}
                  placeholder="Type a lyric, idea, or note..."
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-obsidian placeholder:text-slate outline-none resize-none leading-5 max-h-[200px]"
                  style={{ height: "20px", overflowY: "hidden" }}
                  disabled={submitting}
                />
                <button
                  onClick={submitText}
                  disabled={!text.trim() || submitting}
                  className="p-2 rounded-full hover:bg-powder cursor-pointer transition-colors disabled:opacity-30 btn-press flex-shrink-0"
                  aria-label="Send"
                >
                  <Send size={16} className="text-gravel" />
                </button>
              </div>
              <FileDropzone onFile={handleFile} />
              <AudiotoolImporter onImported={refresh} />
            </div>
          </div>
          <div className="flex-1 min-w-0" data-tour="fragments">
            {!loading && fragments.length > 0 && (
              <div className="space-y-5 pb-12">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                    Your fragments
                  </span>
                  <div className="flex-1 h-px bg-gradient-to-r from-chalk to-transparent" />
                  <MatchModeSelector />
                  <span
                    className="font-mono text-[11px] text-gravel px-2.5 py-0.5 rounded-full"
                    style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.15), rgba(226,193,97,0.1))" }}
                  >
                    {fragments.length}
                  </span>
                </div>
                {stuckCount > 0 && (
                  <button
                    onClick={handleFixStuck}
                    className="text-xs text-gravel hover:text-obsidian transition-colors"
                  >
                    {stuckCount} fragment{stuckCount > 1 ? "s" : ""} stuck processing —{" "}
                    <span className="underline">fix now</span>
                  </button>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
                  <AnimatePresence mode="popLayout">
                    {fragments.map((f, i) => (
                      <motion.div
                        key={f._id}
                        layout
                        initial={{ opacity: 0, y: 24, scale: 0.96, filter: "blur(4px)" }}
                        animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
                        exit={{ opacity: 0, scale: 0.94, filter: "blur(4px)" }}
                        transition={{ type: "spring", stiffness: 200, damping: 22, delay: i * 0.05 }}
                      >
                        <FragmentCard fragment={f} onDeleted={refresh} onUpdated={refresh} />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            )}
            {!loading && fragments.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 space-y-8 animate-fade-in">
                <div
                  className="w-20 h-20 rounded-full opacity-50 morph-blob"
                  style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.4), rgba(226,193,97,0.2))" }}
                />
                <div className="space-y-2 text-center">
                  <p className="text-sm text-gravel">Record, type, upload, or import your first musical idea</p>
                  <p className="text-xs text-slate max-w-[300px] mx-auto leading-relaxed">
                    Each idea becomes a fragment — AI analyzes its emotion, key, tempo, and themes, then groups related fragments into projects automatically.
                  </p>
                </div>
                <div className="flex flex-col gap-3 w-full max-w-[280px]">
                  {[
                    { step: "1", label: "Capture", detail: "Record, type, drop audio, or import from Audiotool" },
                    { step: "2", label: "Analyze", detail: "AI profiles your idea (audio ~30–60s)" },
                    { step: "3", label: "Connect", detail: "Related fragments form projects" },
                  ].map((s) => (
                    <div key={s.step} className="flex items-start gap-3">
                      <span
                        className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-mono font-medium text-gravel"
                        style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.2), rgba(226,193,97,0.1))" }}
                      >
                        {s.step}
                      </span>
                      <div>
                        <p className="text-xs font-medium text-obsidian">{s.label}</p>
                        <p className="text-[11px] text-slate leading-snug">{s.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      <GuidedTour context="dashboard" autoStart />
    </div>
  );
}
