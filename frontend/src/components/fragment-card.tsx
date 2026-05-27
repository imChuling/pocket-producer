"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import {
  Loader2, Mic, FileText, X, Play, Pause, Pencil, Check,
  Lightbulb, Plus, UserPen, History, Trash2,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { apiFetch, apiPost } from "@/lib/api";
import { getIdToken } from "@/lib/firebase";
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

const POTENTIAL_OPTIONS: Fragment["potential"][] = ["high", "medium", "low"];
const STRUCTURE_OPTIONS = [
  "verse_candidate", "chorus_candidate", "hook_candidate",
  "bridge_candidate", "intro_candidate", "outro_candidate",
  "interlude_candidate", "loop_candidate", "drop_candidate",
  "buildup_candidate", "breakdown_candidate", "ad_lib_candidate",
  "near_complete_demo",
];

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
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [dragging, setDragging] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playingRef = useRef(false);
  const progressBarRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Editable tag state
  const [localTags, setLocalTags] = useState<string[]>(fragment.tags ?? []);
  const [localEmotions, setLocalEmotions] = useState<string[]>(fragment.emotions ?? []);
  const [localStyle, setLocalStyle] = useState<string[]>(fragment.style ?? []);
  const [localPotential, setLocalPotential] = useState(fragment.potential);
  const [localStructure, setLocalStructure] = useState(fragment.structure_hint);
  const [editedFields, setEditedFields] = useState<string[]>(fragment.user_edited_fields ?? []);
  const [addingTag, setAddingTag] = useState(false);
  const [newTagValue, setNewTagValue] = useState("");
  const [saving, setSaving] = useState(false);
  const newTagRef = useRef<HTMLInputElement | null>(null);

  // Text editing state
  const [editingText, setEditingText] = useState(false);
  const [editTextValue, setEditTextValue] = useState("");
  const [savingText, setSavingText] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Edit history state
  const [showHistory, setShowHistory] = useState(false);
  const [editHistory, setEditHistory] = useState<EditHistoryEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const isProcessing = fragment.status === "processing";
  const isError = fragment.status === "error" || fragment.status === "timeout";
  const isAudio = fragment.type === "audio";
  const displayTitle = fragment.title || "Audio fragment";

  const allTags = [...localEmotions, ...localTags].slice(0, 6);
  const structureLabel = localStructure
    ?.replace("_candidate", "")
    .replace("_", " ");
  const potentialColor =
    localPotential === "high"
      ? "text-obsidian bg-obsidian/5"
      : localPotential === "low"
        ? "text-slate bg-powder"
        : "text-gravel bg-powder/60";

  // Check if a specific field was user-edited
  const isEdited = (field: string) => editedFields.includes(field);

  // Save a field change to backend
  async function saveField(field: string, value: unknown) {
    setSaving(true);
    try {
      const res = await apiPost<{ user_edited_fields: string[] }>(
        `/fragments/${fragment._id}/tags`,
        { [field]: value },
      );
      if (res.user_edited_fields) {
        setEditedFields(res.user_edited_fields);
      }
      onUpdated?.();
    } catch {
      // revert on failure could be added here
    } finally {
      setSaving(false);
    }
  }

  // Remove a tag/emotion/style
  function removeTag(tag: string, source: "emotions" | "tags" | "style") {
    if (source === "emotions") {
      const next = localEmotions.filter((t) => t !== tag);
      setLocalEmotions(next);
      saveField("emotions", next);
    } else if (source === "tags") {
      const next = localTags.filter((t) => t !== tag);
      setLocalTags(next);
      saveField("tags", next);
    } else {
      const next = localStyle.filter((t) => t !== tag);
      setLocalStyle(next);
      saveField("style", next);
    }
  }

  // Add a new tag
  function addNewTag() {
    const trimmed = newTagValue.trim().toLowerCase();
    if (!trimmed || localTags.includes(trimmed)) {
      setAddingTag(false);
      setNewTagValue("");
      return;
    }
    const next = [...localTags, trimmed];
    setLocalTags(next);
    saveField("tags", next);
    setNewTagValue("");
    setAddingTag(false);
  }

  // Cycle potential
  function cyclePotential() {
    const idx = POTENTIAL_OPTIONS.indexOf(localPotential ?? "medium");
    const next = POTENTIAL_OPTIONS[(idx + 1) % POTENTIAL_OPTIONS.length];
    setLocalPotential(next);
    saveField("potential", next);
  }

  // Cycle structure
  function cycleStructure() {
    if (!localStructure) return;
    const idx = STRUCTURE_OPTIONS.indexOf(localStructure);
    const next = STRUCTURE_OPTIONS[(idx + 1) % STRUCTURE_OPTIONS.length];
    setLocalStructure(next);
    saveField("structure_hint", next);
  }

  // Start editing text
  function startEditingText() {
    setEditTextValue(fragment.text ?? "");
    setEditingText(true);
    setTimeout(() => {
      const ta = textareaRef.current;
      if (ta) { ta.focus(); ta.selectionStart = ta.value.length; }
    }, 0);
  }

  // Save edited text
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

  // Load edit history
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

  // Delete a history entry
  async function deleteHistoryEntry(entryId: string) {
    try {
      await apiPost(`/fragments/${fragment._id}/edit-history/${entryId}/delete`, {});
      setEditHistory((prev) => prev.filter((e) => e.id !== entryId));
    } catch { /* silent */ }
  }

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

  // Seek: visual-only during drag, commit on release
  function ratioFromX(clientX: number): number {
    const bar = progressBarRef.current;
    if (!bar) return 0;
    const rect = bar.getBoundingClientRect();
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  }

  function handleSeekDown(e: React.MouseEvent<HTMLDivElement>) {
    e.preventDefault();
    draggingRef.current = true;
    setDragging(true);
    const ratio = ratioFromX(e.clientX);
    setProgress(ratio);

    let lastRatio = ratio;

    const onMove = (ev: MouseEvent) => {
      if (!draggingRef.current) return;
      lastRatio = ratioFromX(ev.clientX);
      setProgress(lastRatio);
    };
    const onUp = () => {
      draggingRef.current = false;
      setDragging(false);
      // Commit seek on release
      const audio = audioRef.current;
      if (audio && duration) {
        audio.currentTime = lastRatio * duration;
      }
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function formatTime(sec: number): string {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
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
      audio.onloadedmetadata = () => setDuration(audio.duration || 0);
      audio.ontimeupdate = () => {
        if (!draggingRef.current && audio.duration) setProgress(audio.currentTime / audio.duration);
      };
      audio.onended = () => {
        if (draggingRef.current) return;
        playingRef.current = false;
        setPlaying(false);
        setProgress(0);
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
      {/* Delete button */}
      <button
        onClick={handleDelete}
        className="absolute top-3 right-3 p-1.5 rounded-full opacity-0 group-hover:opacity-100 hover:bg-powder transition-all cursor-pointer btn-press"
        aria-label="Delete fragment"
      >
        <X size={13} className="text-slate" />
      </button>

      {/* Status indicator */}
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
        <div className="space-y-2.5">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            disabled={isProcessing || loadingAudio}
            className="flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center hover:scale-105 transition-all duration-200 cursor-pointer disabled:opacity-30 btn-press"
            style={{
              background: playing
                ? "linear-gradient(135deg, #1a1a2e, #2a2a44)"
                : "linear-gradient(135deg, #1a1a2a, #222236)",
              boxShadow: playing
                ? "0 0 20px rgba(160,181,235,0.25), 0 2px 8px rgba(0,0,0,0.15)"
                : "0 2px 8px rgba(160,181,235,0.08), 0 2px 6px rgba(0,0,0,0.08)",
            }}
            aria-label={playing ? "Pause" : "Play"}
          >
            {loadingAudio ? (
              <Loader2 size={14} className="text-white animate-spin" />
            ) : playing ? (
              <Pause size={14} className="text-white" />
            ) : (
              <Play size={14} className="text-white ml-0.5" />
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
                  className="text-sm text-obsidian bg-powder rounded-lg px-2.5 py-1 outline-none border border-chalk focus:border-gravel w-full transition-colors"
                  autoFocus
                />
              </div>
            ) : (
              <div className="flex items-center gap-1.5 group/title">
                <span className="text-sm text-obsidian font-medium truncate">
                  {displayTitle}
                </span>
                <button
                  onClick={startEditing}
                  className="p-0.5 rounded opacity-0 group-hover/title:opacity-100 hover:bg-powder transition-all cursor-pointer"
                  aria-label="Edit title"
                >
                  <Pencil size={11} className="text-slate" />
                </button>
              </div>
            )}
            {(fragment.key || fragment.bpm) && (
              <span className="font-mono text-xs text-gravel">
                {fragment.key ?? ""}
                {fragment.key && fragment.bpm ? " · " : ""}
                {fragment.bpm ? `${fragment.bpm} BPM` : ""}
              </span>
            )}
          </div>
        </div>
        {/* Audio progress bar */}
        {(playing || progress > 0 || duration > 0) && (
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-slate w-8 text-right flex-shrink-0">
              {formatTime((progress * duration) || 0)}
            </span>
            {/* Outer hit area — tall for easy clicking/dragging, visual bar is thin inside */}
            <div
              ref={progressBarRef}
              onMouseDown={handleSeekDown}
              className="flex-1 py-2 cursor-pointer relative group/bar select-none"
            >
              {/* Visual track */}
              <div className="h-1 bg-powder rounded-full relative">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${progress * 100}%`,
                    background: "linear-gradient(90deg, #b0d4be, #4a8c62)",
                  }}
                />
              </div>
              {/* Thumb — visible when playing or dragging */}
              <div
                className={`absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-white shadow-md border-2 border-[#8bbfa0] transition-opacity ${
                  dragging ? "opacity-100 scale-110" : playing ? "opacity-100 group-hover/bar:scale-110" : "opacity-0 group-hover/bar:opacity-100"
                }`}
                style={{ left: `calc(${progress * 100}% - 7px)` }}
              />
            </div>
            <span className="font-mono text-[10px] text-slate w-8 flex-shrink-0">
              {formatTime(duration || 0)}
            </span>
          </div>
        )}
        </div>
      ) : fragment.text ? (
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
          {/* History toggle — only show if fragment has been edited */}
          {!editingText && (fragment.user_edited_fields?.includes("text") || fragment.raw_text) && fragment.raw_text !== fragment.text && (
            <button
              onClick={toggleHistory}
              className="flex items-center gap-1 text-[10px] text-slate hover:text-obsidian transition-colors cursor-pointer"
            >
              {loadingHistory ? <Loader2 size={9} className="animate-spin" /> : <History size={9} />}
              {showHistory ? "Hide history" : "Edit history"}
            </button>
          )}
          {/* History panel */}
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
      ) : (
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-slate" />
          <span className="text-sm text-gravel">Text fragment</span>
        </div>
      )}

      {/* Tags — editable */}
      {(allTags.length > 0 || structureLabel || localPotential || localStyle?.length) && (
        <div className="flex flex-wrap gap-1.5 stagger-children">
          {/* Structure hint — clickable to cycle */}
          {structureLabel && (
            <button
              onClick={cycleStructure}
              className={`text-[11px] font-medium px-2.5 py-1 rounded-full animate-tag-pop cursor-pointer transition-all hover:scale-105 ${
                isEdited("structure_hint")
                  ? "bg-obsidian/10 text-obsidian border border-obsidian/20"
                  : "bg-obsidian/5 text-obsidian"
              }`}
              title="Click to change"
            >
              <span className="flex items-center gap-1">
                {isEdited("structure_hint") && <UserPen size={9} className="opacity-60" />}
                {structureLabel}
              </span>
            </button>
          )}

          {/* Potential — clickable to cycle */}
          {localPotential && (
            <button
              onClick={cyclePotential}
              className={`text-[11px] font-medium px-2.5 py-1 rounded-full animate-tag-pop cursor-pointer transition-all hover:scale-105 ${
                isEdited("potential")
                  ? potentialColor + " border border-obsidian/20"
                  : potentialColor
              }`}
              title="Click to change"
            >
              <span className="flex items-center gap-1">
                {isEdited("potential") && <UserPen size={9} className="opacity-60" />}
                {localPotential}
              </span>
            </button>
          )}

          {/* Emotion tags — removable */}
          {localEmotions.map((tag) => (
            <span
              key={`e-${tag}`}
              className={`group/tag text-[11px] font-medium px-2.5 py-1 rounded-full animate-tag-pop transition-all flex items-center gap-1 ${
                isEdited("emotions")
                  ? "bg-[#a0b5eb]/15 text-[#5a6f99] border border-[#a0b5eb]/30"
                  : "bg-powder text-gravel"
              }`}
            >
              {isEdited("emotions") && <UserPen size={8} className="opacity-50 flex-shrink-0" />}
              {tag}
              <button
                onClick={() => removeTag(tag, "emotions")}
                className="opacity-0 group-hover/tag:opacity-100 hover:text-obsidian transition-opacity cursor-pointer -mr-1 flex-shrink-0"
                aria-label={`Remove ${tag}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}

          {/* Regular tags — removable */}
          {localTags.map((tag) => (
            <span
              key={`t-${tag}`}
              className={`group/tag text-[11px] font-medium px-2.5 py-1 rounded-full animate-tag-pop transition-all flex items-center gap-1 ${
                isEdited("tags")
                  ? "bg-[#e2c161]/15 text-[#8a7a3e] border border-[#e2c161]/30"
                  : "bg-powder text-gravel"
              }`}
            >
              {isEdited("tags") && <UserPen size={8} className="opacity-50 flex-shrink-0" />}
              {tag}
              <button
                onClick={() => removeTag(tag, "tags")}
                className="opacity-0 group-hover/tag:opacity-100 hover:text-obsidian transition-opacity cursor-pointer -mr-1 flex-shrink-0"
                aria-label={`Remove ${tag}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}

          {/* Style tags — removable */}
          {(localStyle ?? []).map((s) => (
            <span
              key={`s-${s}`}
              className={`group/tag text-[11px] font-medium px-2.5 py-1 rounded-full animate-tag-pop transition-all flex items-center gap-1 ${
                isEdited("style")
                  ? "bg-[#ffa773]/15 text-[#99613a] border border-[#ffa773]/30"
                  : "bg-powder text-gravel"
              }`}
            >
              {isEdited("style") && <UserPen size={8} className="opacity-50 flex-shrink-0" />}
              {s}
              <button
                onClick={() => removeTag(s, "style")}
                className="opacity-0 group-hover/tag:opacity-100 hover:text-obsidian transition-opacity cursor-pointer -mr-1 flex-shrink-0"
                aria-label={`Remove ${s}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}

          {/* Add tag button / inline input */}
          {addingTag ? (
            <span className="flex items-center gap-1">
              <input
                ref={newTagRef}
                value={newTagValue}
                onChange={(e) => setNewTagValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addNewTag();
                  if (e.key === "Escape") {
                    setAddingTag(false);
                    setNewTagValue("");
                  }
                }}
                onBlur={addNewTag}
                placeholder="new tag"
                className="text-[11px] px-2 py-1 rounded-full bg-powder text-obsidian outline-none border border-chalk focus:border-gravel w-20 transition-colors"
                autoFocus
              />
            </span>
          ) : (
            <button
              onClick={() => {
                setAddingTag(true);
                setTimeout(() => newTagRef.current?.focus(), 0);
              }}
              className="text-[11px] px-2 py-1 rounded-full bg-powder text-slate hover:text-obsidian hover:bg-chalk transition-all cursor-pointer opacity-0 group-hover:opacity-100 flex items-center gap-0.5"
              aria-label="Add tag"
            >
              <Plus size={10} />
              <span>tag</span>
            </button>
          )}
        </div>
      )}

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
        {saving && (
          <Loader2 size={10} className="animate-spin text-gravel ml-auto" />
        )}
      </div>
    </motion.div>
  );
}
