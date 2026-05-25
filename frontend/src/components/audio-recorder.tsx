"use client";

import { useState, useRef, useCallback } from "react";

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
const MAX_DURATION = 300; // 5 minutes

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface AudioRecorderProps {
  onRecorded: (blob: Blob) => void;
}

function getSupportedMimeType(): string {
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
    "audio/wav",
  ];
  for (const t of types) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
}

function extensionForMime(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("mp4")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  return "wav";
}

export function AudioRecorder({ onRecorded }: AudioRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chunks = useRef<Blob[]>([]);
  const mimeRef = useRef("");

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = getSupportedMimeType();
      mimeRef.current = mime;
      const options: MediaRecorderOptions = mime ? { mimeType: mime } : {};
      const recorder = new MediaRecorder(stream, options);
      chunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      recorder.onstop = () => {
        const blobType = mimeRef.current || "audio/webm";
        const blob = new Blob(chunks.current, { type: blobType });
        if (blob.size > MAX_FILE_SIZE) {
          setError(`Recording too large (${formatSize(blob.size)}). Max ${formatSize(MAX_FILE_SIZE)}.`);
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        onRecorded(blob);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.current = recorder;
      recorder.start();
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => {
        setSeconds((s) => {
          if (s + 1 >= MAX_DURATION) {
            recorder.stop();
            setRecording(false);
            if (timerRef.current) clearInterval(timerRef.current);
          }
          return s + 1;
        });
      }, 1000);
    } catch {
      setError("Microphone access denied");
    }
  }, [onRecorded]);

  const stop = useCallback(() => {
    mediaRecorder.current?.stop();
    setRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        onClick={recording ? stop : start}
        className={`relative w-20 h-20 rounded-full flex items-center justify-center cursor-pointer transition-colors ${
          recording
            ? "bg-red-500"
            : "bg-zinc-800/80 border border-zinc-700 hover:bg-zinc-700/80"
        }`}
        aria-label={recording ? "Stop recording" : "Start recording"}
      >
        {recording && (
          <span className="absolute inset-0 rounded-full ring-2 ring-red-500/30 animate-pulse-ring" />
        )}
        {recording ? (
          <span className="w-4 h-4 rounded-sm bg-white" />
        ) : (
          <span className="w-5 h-5 rounded-full bg-white" />
        )}
      </button>
      {recording && (
        <span className="font-mono text-sm text-red-500">
          {formatTime(seconds)}
        </span>
      )}
      {error && (
        <span className="text-xs text-red-400">{error}</span>
      )}
    </div>
  );
}
