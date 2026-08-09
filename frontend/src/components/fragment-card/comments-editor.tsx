"use client";

import { useState, useRef } from "react";
import { MessageSquarePlus, Check, Loader2, X } from "lucide-react";
import { apiPost } from "@/lib/api";
import type { FragmentComment } from "@/types";

interface CommentsEditorProps {
  fragmentId: string;
  comments?: FragmentComment[];
  onUpdated?: () => void;
}

function shortDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function CommentsEditor({ fragmentId, comments, onUpdated }: CommentsEditorProps) {
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function startAdding() {
    setValue("");
    setAdding(true);
    setTimeout(() => textareaRef.current?.focus(), 0);
  }

  async function save() {
    const trimmed = value.trim();
    if (!trimmed) {
      setAdding(false);
      return;
    }
    setSaving(true);
    try {
      await apiPost(`/fragments/${fragmentId}/comments`, { text: trimmed });
      setAdding(false);
      onUpdated?.();
    } catch {
      // keep editing
    } finally {
      setSaving(false);
    }
  }

  async function remove(commentId: string) {
    setDeletingId(commentId);
    try {
      await apiPost(`/fragments/${fragmentId}/comments/${commentId}/delete`, {});
      onUpdated?.();
    } finally {
      setDeletingId(null);
    }
  }

  const list = comments ?? [];

  return (
    <div className="space-y-1.5">
      {list.map((c) => (
        <div key={c.id} className="flex items-start gap-2 group/comment">
          <span className="text-[10px] text-slate flex-shrink-0 mt-0.5 tabular-nums">
            {shortDate(c.created_at)}
          </span>
          <p className="text-xs text-gravel leading-relaxed flex-1 min-w-0">{c.text}</p>
          <button
            onClick={() => remove(c.id)}
            disabled={deletingId === c.id}
            className="opacity-0 group-hover/comment:opacity-100 p-0.5 rounded-full hover:bg-powder transition-all cursor-pointer flex-shrink-0"
            aria-label="Delete comment"
          >
            {deletingId === c.id
              ? <Loader2 size={10} className="animate-spin text-slate" />
              : <X size={10} className="text-slate" />}
          </button>
        </div>
      ))}

      {adding ? (
        <div className="space-y-1.5">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
              if (e.key === "Escape") setAdding(false);
            }}
            placeholder="What are you thinking right now? — ideas, direction, what this connects to..."
            className="w-full text-xs text-obsidian bg-powder rounded-lg px-3 py-2 outline-none border border-chalk focus:border-gravel transition-colors resize-none leading-relaxed"
            style={{ fieldSizing: "content" as never, minHeight: "48px" }}
          />
          <div className="flex items-center gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full bg-obsidian text-white hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50"
            >
              {saving ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />}
              Add
            </button>
            <button
              onClick={() => setAdding(false)}
              className="text-[11px] px-2.5 py-1 rounded-full text-slate hover:text-obsidian hover:bg-powder transition-all cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={startAdding}
          className="flex items-center gap-1.5 text-[11px] text-slate hover:text-gravel transition-colors cursor-pointer"
        >
          <MessageSquarePlus size={10} />
          {list.length > 0 ? "Add comment" : "Comment your thoughts"}
        </button>
      )}
    </div>
  );
}
