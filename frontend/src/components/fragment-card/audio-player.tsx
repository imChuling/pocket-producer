"use client";

import { useState, useRef, useCallback } from "react";
import { Loader2, Play, Pause, Pencil } from "lucide-react";
import { getIdToken } from "@/lib/firebase";

interface AudioPlayerProps {
  fragmentId: string;
  displayTitle: string;
  fragmentKey?: string | null;
  bpm?: number | null;
  isProcessing: boolean;
  editing: boolean;
  editTitle: string;
  onEditTitleChange: (v: string) => void;
  onStartEditing: () => void;
  onSaveTitle: () => void;
  onCancelEditing: () => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}

export function AudioPlayer({
  fragmentId,
  displayTitle,
  fragmentKey,
  bpm,
  isProcessing,
  editing,
  editTitle,
  onEditTitleChange,
  onStartEditing,
  onSaveTitle,
  onCancelEditing,
  inputRef,
}: AudioPlayerProps) {
  const [playing, setPlaying] = useState(false);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [dragging, setDragging] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playingRef = useRef(false);
  const progressBarRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);

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
      const audio = audioRef.current;
      if (audio) {
        const d = Number.isFinite(audio.duration) && audio.duration > 0
          ? audio.duration : duration;
        if (d > 0) audio.currentTime = lastRatio * d;
      }
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function formatTime(sec: number): string {
    if (!Number.isFinite(sec) || sec < 0) return "0:00";
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
      const res = await fetch(`/api/fragments/${fragmentId}/audio`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load audio");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const audio = new Audio(url);
      let realDuration = 0;

      const onTimeUpdate = () => {
        const d = audio.duration;
        if (Number.isFinite(d) && d > 0 && realDuration === 0) {
          realDuration = d;
          setDuration(d);
        }
        if (!draggingRef.current && realDuration > 0) {
          setProgress(audio.currentTime / realDuration);
        }
      };

      audio.ontimeupdate = onTimeUpdate;
      audio.ondurationchange = () => {
        const d = audio.duration;
        if (Number.isFinite(d) && d > 0) {
          realDuration = d;
          setDuration(d);
        }
      };

      audio.onloadedmetadata = () => {
        if (!Number.isFinite(audio.duration)) {
          const prevTime = audio.currentTime;
          audio.currentTime = 1e10;
          audio.addEventListener("seeked", function onSeeked() {
            audio.removeEventListener("seeked", onSeeked);
            const d = audio.duration;
            if (Number.isFinite(d) && d > 0) {
              realDuration = d;
              setDuration(d);
            }
            audio.currentTime = prevTime;
          });
        } else {
          realDuration = audio.duration;
          setDuration(audio.duration);
        }
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
  }, [fragmentId]);

  return (
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
                onChange={(e) => onEditTitleChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onSaveTitle();
                  if (e.key === "Escape") onCancelEditing();
                }}
                onBlur={onSaveTitle}
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
                onClick={onStartEditing}
                className="p-0.5 rounded opacity-0 group-hover/title:opacity-100 hover:bg-powder transition-all cursor-pointer"
                aria-label="Edit title"
              >
                <Pencil size={11} className="text-slate" />
              </button>
            </div>
          )}
          {(fragmentKey || bpm) && (
            <span className="font-mono text-xs text-gravel">
              {fragmentKey ?? ""}
              {fragmentKey && bpm ? " · " : ""}
              {bpm ? `${bpm} BPM` : ""}
            </span>
          )}
        </div>
      </div>
      {(playing || progress > 0 || duration > 0) && (
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-slate w-8 text-right flex-shrink-0">
            {formatTime((progress * duration) || 0)}
          </span>
          <div
            ref={progressBarRef}
            onMouseDown={handleSeekDown}
            className="flex-1 py-2 cursor-pointer relative group/bar select-none"
          >
            <div className="h-1 bg-powder rounded-full relative">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${progress * 100}%`,
                  background: "linear-gradient(90deg, #b0d4be, #4a8c62)",
                }}
              />
            </div>
            <div
              className={`absolute w-3.5 h-3.5 rounded-full bg-white shadow-md border-2 border-[#8bbfa0] transition-opacity ${
                dragging ? "opacity-100 scale-110" : playing ? "opacity-100 group-hover/bar:scale-110" : "opacity-0 group-hover/bar:opacity-100"
              }`}
              style={{ left: `calc(${progress * 100}% - 7px)`, top: "50%", marginTop: "-7px" }}
            />
          </div>
          <span className="font-mono text-[10px] text-slate w-8 flex-shrink-0">
            {formatTime(duration || 0)}
          </span>
        </div>
      )}
    </div>
  );
}
