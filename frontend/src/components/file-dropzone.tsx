"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Check } from "lucide-react";

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

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
    maxSize: MAX_FILE_SIZE,
    onDropAccepted: (files) => {
      setError(null);
      if (files[0]) {
        setFileName(files[0].name);
        onFile(files[0]);
        setTimeout(() => setFileName(null), 3000);
      }
    },
    onDropRejected: (rejections) => {
      const rejection = rejections[0];
      if (rejection) {
        const sizeErr = rejection.errors.find((e) => e.code === "file-too-large");
        if (sizeErr) {
          setError(`File too large (${formatSize(rejection.file.size)}). Max 25 MB.`);
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
      className={`flex flex-col items-center justify-center gap-1.5 py-4 px-4 rounded-xl border border-dashed cursor-pointer transition-colors ${
        isDragActive
          ? "border-zinc-400 bg-surface-raised"
          : "border-zinc-800 hover:border-zinc-600"
      }`}
    >
      <input {...getInputProps()} />
      <div className="flex items-center gap-2">
        {fileName ? (
          <Check size={16} className="text-emerald-400" />
        ) : (
          <Upload size={16} className="text-zinc-500" />
        )}
        <span className="text-sm text-zinc-400">
          {fileName
            ? fileName
            : isDragActive
              ? "Drop audio file here"
              : "Drop or tap to upload audio"}
        </span>
      </div>
      {!fileName && !error && (
        <span className="text-[11px] text-zinc-600">
          MP3, WAV, M4A, WebM, OGG, FLAC · Max 25 MB
        </span>
      )}
      {error && (
        <span className="text-[11px] text-red-400">{error}</span>
      )}
    </div>
  );
}
