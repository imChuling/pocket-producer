"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Check, Loader2 } from "lucide-react";
import { MAX_AUDIO_FILE_SIZE } from "@/lib/constants";
import { validateAudioDuration } from "@/lib/audio-validation";

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileDropzoneProps {
  onFile: (file: File) => void;
}

export function FileDropzone({ onFile }: FileDropzoneProps) {
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);

  const handleAccepted = async (files: File[]) => {
    setError(null);
    const file = files[0];
    if (!file) return;

    setValidating(true);
    setFileName(file.name);
    const result = await validateAudioDuration(file);
    setValidating(false);

    if (!result.valid) {
      setError(result.error!);
      setFileName(null);
      setTimeout(() => setError(null), 5000);
      return;
    }
    onFile(file);
    setTimeout(() => setFileName(null), 3000);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "audio/mpeg": [".mp3"],
      "audio/wav": [".wav"],
      "audio/x-m4a": [".m4a"],
      "audio/mp4": [".m4a"],
      "audio/webm": [".webm"],
      "audio/ogg": [".ogg"],
      "audio/flac": [".flac"],
    },
    maxFiles: 1,
    maxSize: MAX_AUDIO_FILE_SIZE,
    disabled: validating,
    onDropAccepted: handleAccepted,
    onDropRejected: (rejections) => {
      const rejection = rejections[0];
      if (rejection) {
        const sizeErr = rejection.errors.find((e) => e.code === "file-too-large");
        if (sizeErr) {
          setError(`File too large (${formatSize(rejection.file.size)}). Max 10 MB.`);
        } else {
          setError(rejection.errors[0]?.message ?? "File not accepted");
        }
        setTimeout(() => setError(null), 5000);
      }
    },
  });

  return (
    <div
      {...getRootProps()}
      className={`relative flex flex-col items-center justify-center gap-2 py-6 px-4 rounded-[20px] border border-dashed cursor-pointer transition-all duration-300 overflow-hidden ${
        isDragActive
          ? "border-sky-mint/60 scale-[1.01]"
          : "border-chalk hover:border-slate/50"
      }`}
      style={{
        background: isDragActive
          ? "linear-gradient(135deg, rgba(160,181,235,0.08), rgba(226,193,97,0.04))"
          : "rgba(255,255,255,0.3)",
      }}
    >
      <input {...getInputProps()} />
      {/* Decorative gradient on drag */}
      {isDragActive && (
        <div
          className="absolute inset-0 pointer-events-none animate-fade-in"
          style={{
            background: "radial-gradient(circle at center, rgba(160,181,235,0.08) 0%, transparent 70%)",
          }}
        />
      )}
      <div className="relative flex items-center gap-2.5">
        {validating ? (
          <div className="w-8 h-8 rounded-full bg-powder flex items-center justify-center">
            <Loader2 size={14} className="text-slate animate-spin" />
          </div>
        ) : fileName ? (
          <div className="w-8 h-8 rounded-full bg-obsidian/5 flex items-center justify-center">
            <Check size={14} className="text-obsidian" />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-powder flex items-center justify-center">
            <Upload size={14} className="text-slate" />
          </div>
        )}
        <span className="text-sm text-gravel">
          {validating
            ? "Checking audio..."
            : fileName
              ? fileName
              : isDragActive
                ? "Drop audio file here"
                : "Drop or tap to upload audio"}
        </span>
      </div>
      {!fileName && !validating && !error && (
        <span className="text-[10px] text-slate tracking-wide">
          MP3, WAV, M4A, WebM, OGG, FLAC · Max 10 MB / 5 min
        </span>
      )}
      {error && (
        <span className="text-[11px] text-red-500 animate-fade-in">{error}</span>
      )}
    </div>
  );
}
