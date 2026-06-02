"use client";

import { useState, useRef } from "react";
import { Loader2, Pencil, Check, History, Trash2 } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { apiFetch, apiPost } from "@/lib/api";
import type { Fragment, EditHistoryEntry } from "@/types";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `${days}d`;
}

interface TextContentProps {
  fragment: Fragment;
  onUpdated?: () => void;
}

export function TextContent({ fragment, onUpdated }: TextContentProps) {
  const [editingText, setEditingText] = useState(false);
  const [editTextValue, setEditTextValue] = useState("");
  const [savingText, setSavingText] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const [showHistory, setShowHistory] = useState(false);
  const [editHistory, setEditHistory] = useState<EditHistoryEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  function startEditingText() {
    setEditTextValue(fragment.text ?? "");
    setEditingText(true);
    setTimeout(() => {
      const ta = textareaRef.current;
      if (ta) { ta.focus(); ta.selectionStart = ta.value.length; }
    }, 0);
  }

  async function saveText() {
    const trimmed = editTextValue.trim();
    if (!trimmed || trimmed === (fragment.text ?? "")) {
      setEditingText(false);
      return;
    }
    setSavingText(true);
    try {
      await apiPost(`/fragments/${fragment._id}/edit-text`, { text: trimmed });
      setEditingText(false);
      onUpdated?.();
    } catch {
      // keep editing on failure
    } finally {
      setSavingText(false);
    }
  }

  async function toggleHistory() {
    if (showHistory) {
      setShowHistory(false);
      return;
    }
    setLoadingHistory(true);
    try {
      const full = await apiFetch<Fragment>(`/fragments/${fragment._id}`);
      setEditHistory(full.edit_history ?? []);
    } catch {
      setEditHistory([]);
    } finally {
      setLoadingHistory(false);
      setShowHistory(true);
    }
  }

  async function deleteHistoryEntry(entryId: string) {
    try {
      await apiPost(`/fragments/${fragment._id}/edit-history/${entryId}/delete`, {});
      setEditHistory((prev) => prev.filter((e) => e.id !== entryId));
    } catch { /* silent */ }
  }

  return (
    <div className="space-y-2">
      {editingText ? (
        <div className="space-y-2">
          <textarea
            ref={textareaRef}
            value={editTextValue}
            onChange={(e) => setEditTextValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) saveText();
              if (e.key === "Escape") setEditingText(false);
            }}
            className="w-full text-sm text-obsidian bg-powder rounded-lg px-3 py-2 outline-none border border-chalk focus:border-gravel transition-colors resize-none leading-relaxed"
            style={{ fieldSizing: "content" as never, minHeight: "60px" }}
          />
          <div className="flex items-center gap-2">
            <button
              onClick={saveText}
              disabled={savingText}
              className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full bg-obsidian text-white hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50"
            >
              {savingText ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />}
              Save
            </button>
            <button
              onClick={() => setEditingText(false)}
              className="text-[11px] px-2.5 py-1 rounded-full text-slate hover:text-obsidian hover:bg-powder transition-all cursor-pointer"
            >
              Cancel
            </button>
            <span className="text-[10px] text-slate ml-auto">⌘+Enter to save</span>
          </div>
        </div>
      ) : (
        <div className="group/text">
          <p className="text-sm text-gravel italic leading-relaxed line-clamp-3">
            &ldquo;{fragment.text}&rdquo;
          </p>
          <button
            onClick={startEditingText}
            className="flex items-center gap-1 mt-1.5 text-[10px] text-slate hover:text-obsidian opacity-0 group-hover/text:opacity-100 transition-all cursor-pointer"
            aria-label="Edit text"
          >
            <Pencil size={9} />
            Edit
          </button>
        </div>
      )}
      {!editingText && (fragment.user_edited_fields?.includes("text") || fragment.raw_text) && fragment.raw_text !== fragment.text && (
        <button
          onClick={toggleHistory}
          className="flex items-center gap-1 text-[10px] text-slate hover:text-obsidian transition-colors cursor-pointer"
        >
          {loadingHistory ? <Loader2 size={9} className="animate-spin" /> : <History size={9} />}
          {showHistory ? "Hide history" : "Edit history"}
        </button>
      )}
      <AnimatePresence>
        {showHistory && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="space-y-1.5 pt-1 border-t border-chalk/60">
              {editHistory.length === 0 && !fragment.raw_text && (
                <p className="text-[10px] text-slate py-2">No edit history</p>
              )}
              {editHistory.slice().reverse().map((entry) => (
                <div key={entry.id} className="group/hist flex items-start gap-2 py-1.5">
                  <p className="text-[11px] text-slate italic leading-relaxed flex-1 line-clamp-2">
                    &ldquo;{entry.text}&rdquo;
                  </p>
                  <span className="text-[9px] text-slate/60 whitespace-nowrap flex-shrink-0 mt-0.5">
                    {timeAgo(entry.edited_at)}
                  </span>
                  <button
                    onClick={() => deleteHistoryEntry(entry.id)}
                    className="p-0.5 rounded opacity-0 group-hover/hist:opacity-100 hover:bg-powder transition-all cursor-pointer flex-shrink-0 mt-0.5"
                    aria-label="Delete history entry"
                  >
                    <Trash2 size={10} className="text-slate hover:text-red-500" />
                  </button>
                </div>
              ))}
              {fragment.raw_text && fragment.raw_text !== fragment.text && (
                <div className="flex items-start gap-2 py-1.5 opacity-60">
                  <p className="text-[11px] text-slate italic leading-relaxed flex-1 line-clamp-2">
                    <span className="not-italic text-[9px] font-mono uppercase tracking-wider mr-1">Original</span>
                    &ldquo;{fragment.raw_text}&rdquo;
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
