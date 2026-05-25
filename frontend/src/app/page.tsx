"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Send, Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useFragments } from "@/hooks/use-fragments";
import { apiPost } from "@/lib/api";
import { AudioRecorder } from "@/components/audio-recorder";
import { FileDropzone } from "@/components/file-dropzone";
import { FragmentCard } from "@/components/fragment-card";

export default function CapturePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { fragments, loading, refresh } = useFragments();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const handleRecorded = useCallback(
    async (blob: Blob) => {
      setSubmitting(true);
      setStatus("Processing audio...");
      try {
        const form = new FormData();
        const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
        form.append("file", blob, `recording.${ext}`);
        await apiPost("/ingest", form);
        setStatus("Saved!");
        refresh();
      } catch (e) {
        setStatus(e instanceof Error ? e.message : "Processing failed");
      } finally {
        setSubmitting(false);
        setTimeout(() => setStatus(null), 3000);
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
        setStatus("Saved!");
        refresh();
      } catch (e) {
        setStatus(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setSubmitting(false);
        setTimeout(() => setStatus(null), 3000);
      }
    },
    [refresh],
  );

  if (authLoading || !user) return null;

  async function submitText() {
    if (!text.trim() || submitting) return;
    setSubmitting(true);
    setStatus("Processing...");
    try {
      const form = new FormData();
      form.append("text", text.trim());
      await apiPost("/ingest", form);
      setText("");
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
    <div className="py-8 space-y-8 animate-fade-in">
      <div className="flex flex-col items-center pt-8 pb-4">
        <AudioRecorder onRecorded={handleRecorded} />
      </div>

      {status && (
        <div className="flex items-center justify-center gap-2 text-sm text-zinc-400">
          {submitting && <Loader2 size={14} className="animate-spin" />}
          {status}
        </div>
      )}

      <div className="flex items-center gap-2 bg-surface rounded-xl px-4 py-3">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitText()}
          placeholder="Type your idea..."
          className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 outline-none"
          disabled={submitting}
        />
        <button
          onClick={submitText}
          disabled={!text.trim() || submitting}
          className="p-2 rounded-full hover:bg-surface-raised cursor-pointer transition-colors disabled:opacity-30"
          aria-label="Send"
        >
          <Send size={16} className="text-zinc-400" />
        </button>
      </div>

      <FileDropzone onFile={handleFile} />

      {!loading && fragments.length > 0 && (
        <div className="space-y-3">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">
            Fragments
          </span>
          <div className="space-y-2">
            {fragments.map((f) => (
              <FragmentCard key={f._id} fragment={f} onDeleted={refresh} onUpdated={refresh} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
