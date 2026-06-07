"use client";

import { useState, useRef } from "react";
import { StickyNote, Check, Loader2 } from "lucide-react";
import { apiPost } from "@/lib/api";

interface NotesEditorProps {
  fragmentId: string;
  notes?: string;
  onUpdated?: () => void;
}

export function NotesEditor({ fragmentId, notes, onUpdated }: NotesEditorProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function startEditing() {
    setValue(notes || "");
    setEditing(true);
    setTimeout(() => textareaRef.current?.focus(), 0);
  }

  async function save() {
    setSaving(true);
    try {
      await apiPost(`/fragments/${fragmentId}/notes`, { notes: value.trim() });
      setEditing(false);
      onUpdated?.();
    } catch {
      // keep editing
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="space-y-1.5">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
            if (e.key === "Escape") setEditing(false);
          }}
          placeholder="Add context for the AI — what inspired this, how it connects to other ideas..."
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
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="text-[11px] px-2.5 py-1 rounded-full text-slate hover:text-obsidian hover:bg-powder transition-all cursor-pointer"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (notes) {
    return (
      <button
        onClick={startEditing}
        className="w-full text-left flex items-start gap-2 group/notes cursor-pointer"
      >
        <StickyNote size={11} className="text-slate mt-0.5 flex-shrink-0" />
        <p className="text-xs text-slate leading-relaxed group-hover/notes:text-gravel transition-colors">
          {notes}
        </p>
      </button>
    );
  }

  return (
    <button
      onClick={startEditing}
      className="flex items-center gap-1.5 text-[11px] text-slate hover:text-gravel transition-colors cursor-pointer opacity-0 group-hover:opacity-100"
    >
      <StickyNote size={10} />
      Add note
    </button>
  );
}
