"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { MAX_AUDIO_FILE_SIZE, MAX_RECORDING_DURATION_SEC } from "@/lib/constants";

const MAX_FILE_SIZE = MAX_AUDIO_FILE_SIZE;
const MAX_DURATION = MAX_RECORDING_DURATION_SEC;

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

interface AudioRecorderProps {
  onRecorded: (blob: Blob) => void;
}

export function AudioRecorder({ onRecorded }: AudioRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chunks = useRef<Blob[]>([]);
  const mimeRef = useRef("");
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const recordingRef = useRef(false);

  useEffect(() => {
    recordingRef.current = recording;
  }, [recording]);

  // Canvas ring visualization
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const size = 260;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const innerR = 56;
    const barCount = 80;
    let frame = 0;
    let rafId = 0;

    function draw() {
      frame++;
      ctx!.clearRect(0, 0, size, size);

      if (recordingRef.current && analyserRef.current) {
        const data = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(data);

        // Outer glow pulse
        const pulseR = innerR + 55 + Math.sin(frame * 0.03) * 8;
        const glow = ctx!.createRadialGradient(cx, cy, innerR + 10, cx, cy, pulseR);
        glow.addColorStop(0, "rgba(160,181,235,0.06)");
        glow.addColorStop(0.5, "rgba(255,167,115,0.03)");
        glow.addColorStop(1, "transparent");
        ctx!.beginPath();
        ctx!.arc(cx, cy, pulseR, 0, Math.PI * 2);
        ctx!.fillStyle = glow;
        ctx!.fill();

        // Frequency bars in a ring
        for (let i = 0; i < barCount; i++) {
          const angle = (i / barCount) * Math.PI * 2 - Math.PI / 2;
          const dataIdx = Math.floor((i / barCount) * data.length * 0.6);
          const value = (data[dataIdx] ?? 0) / 255;
          const barLen = 3 + value * 38;

          const x1 = cx + Math.cos(angle) * (innerR + 4);
          const y1 = cy + Math.sin(angle) * (innerR + 4);
          const x2 = cx + Math.cos(angle) * (innerR + 4 + barLen);
          const y2 = cy + Math.sin(angle) * (innerR + 4 + barLen);

          const t = i / barCount;
          const r = Math.round(160 + t * 95);
          const g = Math.round(181 - t * 40);
          const b = Math.round(235 - t * 120);

          ctx!.beginPath();
          ctx!.moveTo(x1, y1);
          ctx!.lineTo(x2, y2);
          ctx!.strokeStyle = `rgba(${r},${g},${b},${0.25 + value * 0.75})`;
          ctx!.lineWidth = 2;
          ctx!.lineCap = "round";
          ctx!.stroke();
        }

        // Inner subtle ring
        ctx!.beginPath();
        ctx!.arc(cx, cy, innerR + 2, 0, Math.PI * 2);
        ctx!.strokeStyle = "rgba(160,181,235,0.12)";
        ctx!.lineWidth = 0.5;
        ctx!.stroke();

      } else {
        // Idle: subtle breathing dots + orbital ring
        const dotCount = 48;
        for (let i = 0; i < dotCount; i++) {
          const angle = (i / dotCount) * Math.PI * 2 - Math.PI / 2 + frame * 0.001;
          const breathe = Math.sin(frame * 0.018 + i * 0.25) * 4;
          const r = innerR + 12 + breathe;
          const dx = cx + Math.cos(angle) * r;
          const dy = cy + Math.sin(angle) * r;

          const t = i / dotCount;
          const cr = Math.round(160 + t * 60);
          const cg = Math.round(181 - t * 20);
          const cb = Math.round(235 - t * 80);
          const alpha = 0.06 + Math.sin(frame * 0.012 + i * 0.18) * 0.05;

          ctx!.beginPath();
          ctx!.arc(dx, dy, 1.2, 0, Math.PI * 2);
          ctx!.fillStyle = `rgba(${cr},${cg},${cb},${alpha})`;
          ctx!.fill();
        }

        // Outer faint ring
        ctx!.beginPath();
        ctx!.arc(cx, cy, innerR + 16, 0, Math.PI * 2);
        ctx!.strokeStyle = "rgba(0,0,0,0.03)";
        ctx!.lineWidth = 0.5;
        ctx!.stroke();

        // Orbiting dot
        const orbAngle = frame * 0.008;
        const orbR = innerR + 12;
        const ox = cx + Math.cos(orbAngle) * orbR;
        const oy = cy + Math.sin(orbAngle) * orbR;
        ctx!.beginPath();
        ctx!.arc(ox, oy, 2, 0, Math.PI * 2);
        ctx!.fillStyle = "rgba(160,181,235,0.25)";
        ctx!.fill();
        ctx!.beginPath();
        ctx!.arc(ox, oy, 6, 0, Math.PI * 2);
        ctx!.fillStyle = "rgba(160,181,235,0.06)";
        ctx!.fill();
      }

      rafId = requestAnimationFrame(draw);
    }

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      if (audioCtx.state === "suspended") await audioCtx.resume();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mime = getSupportedMimeType();
      mimeRef.current = mime;
      const options: MediaRecorderOptions = mime ? { mimeType: mime } : {};
      const recorder = new MediaRecorder(stream, options);
      chunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      recorder.onstop = () => {
        analyserRef.current = null;
        audioCtxRef.current?.close().catch(() => {});
        audioCtxRef.current = null;
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
    } catch (err) {
      audioCtxRef.current?.close().catch(() => {});
      audioCtxRef.current = null;
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setError("Microphone access denied — check browser and OS permission settings");
      } else if (name === "NotFoundError" || name === "OverconstrainedError") {
        setError("No microphone found");
      } else if (name === "NotReadableError") {
        setError("Microphone is in use by another app");
      } else {
        setError("Could not start recording — try reloading the page");
      }
    }
  }, [onRecorded]);

  const stop = useCallback(() => {
    mediaRecorder.current?.stop();
    setRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
    analyserRef.current = null;
  }, []);

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-[260px] h-[260px] flex items-center justify-center">
        <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />

        {/* Record button */}
        <button
          onClick={recording ? stop : start}
          className={`relative z-10 w-[88px] h-[88px] rounded-full flex items-center justify-center cursor-pointer transition-all duration-300 btn-press ${
            recording
              ? "bg-obsidian"
              : "bg-white border border-chalk hover:border-gravel shadow-hairline"
          }`}
          aria-label={recording ? "Stop recording" : "Start recording"}
        >
          {recording && (
            <span className="absolute inset-0 rounded-full border-2 border-obsidian/20 animate-pulse-ring" />
          )}
          {recording ? (
            <span className="w-5 h-5 rounded-[4px] bg-white transition-all duration-200" />
          ) : (
            <span className="w-5 h-5 rounded-full bg-obsidian transition-all duration-200" />
          )}
        </button>

        {/* Timer overlay — inside the ring when recording */}
        {recording && (
          <span
            className={`absolute bottom-[38px] z-10 font-mono text-[11px] tracking-wider animate-fade-in ${
              MAX_DURATION - seconds <= 10 ? "text-red-500 animate-pulse" : "text-slate"
            }`}
          >
            {formatTime(seconds)}
            {MAX_DURATION - seconds <= 10 && (
              <span className="block text-[9px] text-center text-red-400">
                {MAX_DURATION - seconds}s left
              </span>
            )}
          </span>
        )}
      </div>

      {/* Label */}
      {!recording && (
        <p className="text-[11px] text-slate tracking-wide">Tap to record</p>
      )}

      {error && (
        <span className="text-xs text-red-500 animate-fade-in">{error}</span>
      )}
    </div>
  );
}
