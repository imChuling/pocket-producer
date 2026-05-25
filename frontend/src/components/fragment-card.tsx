"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import { Loader2, Mic, FileText, X, Play, Pause, Pencil, Check, Lightbulb } from "lucide-react";
import { apiPost } from "@/lib/api";
import { getIdToken } from "@/lib/firebase";
import type { Fragment } from "@/types";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `${days}d`;
}

interface FragmentCardProps {
  fragment: Fragment;
  onDeleted?: () => void;
  onUpdated?: () => void;
}

export function FragmentCard({ fragment, onDeleted, onUpdated }: FragmentCardProps) {
  const [deleting, setDeleting] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playingRef = useRef(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const isProcessing = fragment.status === "processing";
  const isError = fragment.status === "error" || fragment.status === "timeout";
  const isAudio = fragment.type === "audio";
  const displayTitle = fragment.title || "Audio fragment";
  const tags = [...(fragment.emotions ?? []), ...(fragment.tags ?? [])].slice(0, 4);
  const structureLabel = fragment.structure_hint
    ?.replace("_candidate", "")
    .replace("_", " ");
  const potentialColor =
    fragment.potential === "high"
      ? "text-emerald-400 bg-emerald-400/10"
      : fragment.potential === "low"
        ? "text-zinc-500 bg-zinc-700/50"
        : "";

  async function handleDelete() {
    setDeleting(true);
    try {
      await apiPost(`/fragments/${fragment._id}/delete`, {});
      onDeleted?.();
    } catch {
      setDeleting(false);
    }
  }

  function startEditing() {
    setEditTitle(displayTitle);
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  async function saveTitle() {
    const trimmed = editTitle.trim();
    if (!trimmed || trimmed === displayTitle) {
      setEditing(false);
      return;
    }
    const form = new FormData();
    form.append("title", trimmed);
    await apiPost(`/fragments/${fragment._id}/title`, form);
    setEditing(false);
    onUpdated?.();
  }

  const togglePlay = useCallback(async () => {
    if (audioRef.current) {
      if (playingRef.current) {
        audioRef.current.pause();
        playingRef.current = false;
        setPlaying(false);
      } else {
        audioRef.current.play();
        playingRef.current = true;
        setPlaying(true);
      }
      return;
    }

    setLoadingAudio(true);
    try {
      const token = await getIdToken();
      const res = await fetch(`/api/fragments/${fragment._id}/audio`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load audio");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const audio = new Audio(url);
      audio.onended = () => {
        playingRef.current = false;
        setPlaying(false);
      };
      audio.onerror = () => {
        playingRef.current = false;
        setPlaying(false);
      };
      audioRef.current = audio;
      await audio.play();
      playingRef.current = true;
      setPlaying(true);
    } catch {
      /* silent */
    } finally {
      setLoadingAudio(false);
    }
  }, [fragment._id]);

  if (deleting) return null;

  return (
    <div
      className={`group relative bg-surface rounded-xl p-4 space-y-3 ${isProcessing ? "opacity-70" : ""}`}
    >
      {/* Delete button */}
      <button
        onClick={handleDelete}
        className="absolute top-3 right-3 p-1 rounded-full opacity-0 group-hover:opacity-100 hover:bg-zinc-700/50 transition-all cursor-pointer"
        aria-label="Delete fragment"
      >
        <X size={14} className="text-zinc-500" />
      </button>

      {/* Status indicator */}
      {isProcessing && (
        <div className="flex items-center gap-2 text-xs text-amber-400/80">
          <Loader2 size={12} className="animate-spin" />
          <span>Processing...</span>
        </div>
      )}
      {isError && (
        <div className="text-xs text-red-400/80">Processing failed</div>
      )}

      {/* Content */}
      {isAudio ? (
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            disabled={isProcessing || loadingAudio}
            className="flex-shrink-0 w-9 h-9 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center hover:bg-zinc-700 transition-colors cursor-pointer disabled:opacity-40"
            aria-label={playing ? "Pause" : "Play"}
          >
            {loadingAudio ? (
              <Loader2 size={14} className="text-zinc-300 animate-spin" />
            ) : playing ? (
              <Pause size={14} className="text-zinc-300" />
            ) : (
              <Play size={14} className="text-zinc-300 ml-0.5" />
            )}
          </button>
          <div className="flex flex-col gap-0.5 min-w-0 flex-1">
            {editing ? (
              <div className="flex items-center gap-1.5">
                <input
                  ref={inputRef}
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveTitle();
                    if (e.key === "Escape") setEditing(false);
                  }}
                  onBlur={saveTitle}
                  className="text-sm text-zinc-300 bg-zinc-800 rounded px-2 py-0.5 outline-none border border-zinc-600 focus:border-zinc-400 w-full"
                  autoFocus
                />
              </div>
            ) : (
              <div className="flex items-center gap-1.5 group/title">
                <span className="text-sm text-zinc-400 truncate">
                  {displayTitle}
                </span>
                <button
                  onClick={startEditing}
                  className="p-0.5 rounded opacity-0 group-hover/title:opacity-100 hover:bg-zinc-700/50 transition-all cursor-pointer"
                  aria-label="Edit title"
                >
                  <Pencil size={11} className="text-zinc-500" />
                </button>
              </div>
            )}
            {(fragment.key || fragment.bpm) && (
              <span className="font-mono text-xs text-zinc-500">
                {fragment.key ?? ""}
                {fragment.key && fragment.bpm ? " · " : ""}
                {fragment.bpm ? `${fragment.bpm} BPM` : ""}
              </span>
            )}
          </div>
        </div>
      ) : fragment.text ? (
        <p className="text-sm text-zinc-300 italic leading-relaxed line-clamp-3">
          &ldquo;{fragment.text}&rdquo;
        </p>
      ) : (
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-zinc-500" />
          <span className="text-sm text-zinc-400">Text fragment</span>
        </div>
      )}

      {(tags.length > 0 || structureLabel || fragment.potential) && (
        <div className="flex flex-wrap gap-1.5">
          {structureLabel && (
            <span className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-violet-500/15 text-violet-400">
              {structureLabel}
            </span>
          )}
          {fragment.potential && fragment.potential !== "medium" && (
            <span className={`text-[11px] font-medium px-2.5 py-1 rounded-full ${potentialColor}`}>
              {fragment.potential}
            </span>
          )}
          {tags.map((tag) => (
            <span
              key={tag}
              className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-zinc-800 text-zinc-400"
            >
              {tag}
            </span>
          ))}
          {(fragment.style ?? []).map((s) => (
            <span
              key={s}
              className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400"
            >
              {s}
            </span>
          ))}
        </div>
      )}

      {/* AI suggestion */}
      {fragment.suggestion && (
        <div className="flex items-start gap-2 bg-zinc-800/50 rounded-lg px-3 py-2">
          <Lightbulb size={13} className="text-amber-400/70 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-zinc-400 leading-relaxed">{fragment.suggestion}</p>
        </div>
      )}

      <div className="text-xs text-zinc-500 flex items-center gap-1">
        {fragment.project_id && fragment.project_title && (
          <Link
            href={`/projects/${fragment.project_id}`}
            className="text-violet-400/80 hover:text-violet-300 transition-colors"
          >
            &rarr; {fragment.project_title}
          </Link>
        )}
        {fragment.project_title && <span>&middot;</span>}
        <span>{timeAgo(fragment.created_at)}</span>
      </div>
    </div>
  );
}
