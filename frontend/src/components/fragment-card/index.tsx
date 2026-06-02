"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import {
  Loader2, FileText, X, Lightbulb, RefreshCw, GitMerge,
} from "lucide-react";
import { motion } from "motion/react";
import { apiPost } from "@/lib/api";
import type { Fragment } from "@/types";

import { AudioPlayer } from "./audio-player";
import { TextContent } from "./text-content";
import { TagEditor } from "./tag-editor";

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
  const [reanalyzing, setReanalyzing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  const isStuckProcessing = fragment.status === "processing" && fragment.tags && fragment.tags.length > 0;
  const isProcessing = reanalyzing || (fragment.status === "processing" && !isStuckProcessing);
  const isError = fragment.status === "error" || fragment.status === "timeout";
  const isAudio = fragment.type === "audio";
  const displayTitle = fragment.title || "Audio fragment";

  async function handleDelete() {
    setDeleting(true);
    try {
      await apiPost(`/fragments/${fragment._id}/delete`, {});
      onDeleted?.();
    } catch {
      setDeleting(false);
    }
  }

  async function handleReanalyze() {
    setReanalyzing(true);
    try {
      await apiPost(`/fragments/${fragment._id}/reanalyze`, {});
      setTimeout(() => onUpdated?.(), 5000);
    } catch (e) {
      console.error("Reanalyze failed:", e);
    } finally {
      setReanalyzing(false);
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

  if (deleting) return null;

  return (
    <motion.div
      whileHover={{ y: -3, boxShadow: "rgba(0,0,0,0.08) 0px 8px 24px 0px, rgba(160,181,235,0.1) 0px 4px 16px 0px" }}
      whileTap={{ scale: 0.99 }}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      className={`group relative backdrop-blur-sm rounded-[24px] p-5 space-y-3 shadow-hairline ${
        isProcessing ? "opacity-60" : ""
      }`}
      style={{
        background: isAudio
          ? "linear-gradient(135deg, rgba(255,255,255,0.85), rgba(160,181,235,0.08), rgba(207,218,245,0.04))"
          : "linear-gradient(135deg, rgba(255,255,255,0.85), rgba(226,193,97,0.07), rgba(255,200,160,0.03))",
      }}
    >
      {/* Action buttons */}
      <div className="absolute top-3 right-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
        <button
          onClick={handleReanalyze}
          disabled={reanalyzing}
          className="p-1.5 rounded-full hover:bg-powder transition-colors cursor-pointer btn-press disabled:opacity-40"
          aria-label="Reanalyze fragment"
        >
          <RefreshCw size={13} className={`text-slate ${reanalyzing ? "animate-spin" : ""}`} />
        </button>
        <button
          onClick={handleDelete}
          className="p-1.5 rounded-full hover:bg-powder transition-colors cursor-pointer btn-press"
          aria-label="Delete fragment"
        >
          <X size={13} className="text-slate" />
        </button>
      </div>

      {/* Status */}
      {isProcessing && (
        <div className="flex items-center gap-2 text-xs text-gravel">
          <Loader2 size={12} className="animate-spin" />
          <span>Processing...</span>
        </div>
      )}
      {isError && (
        <div className="text-xs text-red-500">Processing failed</div>
      )}

      {/* Content */}
      {isAudio ? (
        <AudioPlayer
          fragmentId={fragment._id}
          displayTitle={displayTitle}
          fragmentKey={fragment.key}
          bpm={fragment.bpm}
          isProcessing={isProcessing}
          editing={editing}
          editTitle={editTitle}
          onEditTitleChange={setEditTitle}
          onStartEditing={startEditing}
          onSaveTitle={saveTitle}
          onCancelEditing={() => setEditing(false)}
          inputRef={inputRef}
        />
      ) : fragment.text ? (
        <TextContent fragment={fragment} onUpdated={onUpdated} />
      ) : (
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-slate" />
          <span className="text-sm text-gravel">Text fragment</span>
        </div>
      )}

      {/* Tags */}
      <TagEditor fragment={fragment} onUpdated={onUpdated} />

      {/* AI suggestion */}
      {fragment.suggestion && (
        <div
          className="flex items-start gap-2.5 rounded-xl px-3.5 py-3"
          style={{
            background: "linear-gradient(135deg, rgba(160,181,235,0.08), rgba(226,193,97,0.05))",
          }}
        >
          <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
            style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.3), rgba(226,193,97,0.2))" }}
          >
            <Lightbulb size={10} className="text-gravel" />
          </div>
          <p className="text-xs text-gravel leading-relaxed">{fragment.suggestion}</p>
        </div>
      )}

      {/* Agent connection */}
      {fragment.project_id && fragment.connection_reason && (
        <div
          className="rounded-xl px-3.5 py-3 space-y-2"
          style={{
            background: "linear-gradient(135deg, rgba(160,181,235,0.12), rgba(176,212,190,0.08))",
            border: "1px solid rgba(160,181,235,0.18)",
          }}
        >
          <div className="flex items-center gap-1.5">
            <GitMerge size={11} className="text-[#5a6f99] flex-shrink-0" />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[#5a6f99]">
              Memory Agent linked this
            </span>
          </div>
          <p className="text-xs text-gravel leading-relaxed">{fragment.connection_reason}</p>
          {fragment.connection_types && fragment.connection_types.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {fragment.connection_types.map((ct) => (
                <span
                  key={ct}
                  className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#a0b5eb]/15 text-[#5a6f99]"
                >
                  {ct.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="text-xs text-slate flex items-center gap-1.5">
        {fragment.project_id && fragment.project_title && (
          <Link
            href={`/projects/${fragment.project_id}`}
            className="text-obsidian hover:text-gravel transition-colors"
          >
            &rarr; {fragment.project_title}
          </Link>
        )}
        {fragment.project_title && <span className="text-chalk">&middot;</span>}
        <span>{timeAgo(fragment.created_at)}</span>
      </div>
    </motion.div>
  );
}
