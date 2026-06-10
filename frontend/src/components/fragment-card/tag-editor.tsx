"use client";

import { useState, useRef, useEffect } from "react";
import { X, Plus, UserPen, Loader2 } from "lucide-react";
import { apiPost } from "@/lib/api";
import type { Fragment } from "@/types";

const POTENTIAL_OPTIONS: Fragment["potential"][] = ["high", "medium", "low"];
const STRUCTURE_OPTIONS = [
  "verse_candidate", "chorus_candidate", "hook_candidate",
  "bridge_candidate", "intro_candidate", "outro_candidate",
  "interlude_candidate", "loop_candidate", "drop_candidate",
  "buildup_candidate", "breakdown_candidate", "ad_lib_candidate",
  "near_complete_demo",
];

interface TagEditorProps {
  fragment: Fragment;
  onUpdated?: () => void;
}

export function TagEditor({ fragment, onUpdated }: TagEditorProps) {
  const [localTags, setLocalTags] = useState<string[]>(fragment.tags ?? []);
  const [localEmotions, setLocalEmotions] = useState<string[]>(fragment.emotions ?? []);
  const [localStyle, setLocalStyle] = useState<string[]>(fragment.style ?? []);
  const [localPotential, setLocalPotential] = useState(fragment.potential);
  const [localStructure, setLocalStructure] = useState(fragment.structure_hint);
  const [editedFields, setEditedFields] = useState<string[]>(fragment.user_edited_fields ?? []);

  useEffect(() => {
    setLocalTags(fragment.tags ?? []);
    setLocalEmotions(fragment.emotions ?? []);
    setLocalStyle(fragment.style ?? []);
    setLocalPotential(fragment.potential);
    setLocalStructure(fragment.structure_hint);
    setEditedFields(fragment.user_edited_fields ?? []);
  }, [fragment.tags, fragment.emotions, fragment.style, fragment.potential, fragment.structure_hint, fragment.user_edited_fields]);
  const [addingTag, setAddingTag] = useState(false);
  const [newTagValue, setNewTagValue] = useState("");
  const [saving, setSaving] = useState(false);
  const newTagRef = useRef<HTMLInputElement | null>(null);

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

  const isEdited = (field: string) => editedFields.includes(field);

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

  function cyclePotential() {
    const idx = POTENTIAL_OPTIONS.indexOf(localPotential ?? "medium");
    const next = POTENTIAL_OPTIONS[(idx + 1) % POTENTIAL_OPTIONS.length];
    setLocalPotential(next);
    saveField("potential", next);
  }

  function cycleStructure() {
    if (!localStructure) return;
    const idx = STRUCTURE_OPTIONS.indexOf(localStructure);
    const next = STRUCTURE_OPTIONS[(idx + 1) % STRUCTURE_OPTIONS.length];
    setLocalStructure(next);
    saveField("structure_hint", next);
  }

  if (!allTags.length && !structureLabel && !localPotential && !localStyle?.length) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1.5 stagger-children relative">
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

      {saving && (
        <Loader2 size={10} className="animate-spin text-gravel absolute -right-5 top-1" />
      )}
    </div>
  );
}
