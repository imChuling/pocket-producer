"use client";

import { useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import {
  AnnotatePanel,
  type NextPairResponse,
  type PairFragment,
  type PairLabelPayload,
} from "@/components/annotate/annotate-panel";
import { useAuth } from "@/hooks/use-auth";
import { apiFetch, apiPost } from "@/lib/api";
import { getIdToken } from "@/lib/firebase";

export default function AnnotatePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const previewUrlRef = useRef<string | null>(null);

  const releasePreview = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    return () => releasePreview();
  }, [releasePreview]);

  const fetchNext = useCallback(
    () => apiFetch<NextPairResponse>("/ranking/pairs/next"),
    [],
  );
  const submitLabel = useCallback(
    (pairId: string, label: PairLabelPayload) =>
      apiPost(`/ranking/pairs/${pairId}/label`, label).then(() => undefined),
    [],
  );
  const preview = useCallback(async (fragment: PairFragment) => {
    if (!fragment.audio_url) return;
    const token = await getIdToken();
    const response = await fetch(fragment.audio_url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return;
    const url = URL.createObjectURL(await response.blob());
    releasePreview();
    const audio = new Audio(url);
    audioRef.current = audio;
    previewUrlRef.current = url;
    try {
      await audio.play();
    } catch (e) {
      // Rapid preview switches abort the pending play(); that is expected.
      if (!(e instanceof DOMException && e.name === "AbortError")) throw e;
    }
  }, [releasePreview]);

  if (authLoading || !user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate" />
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 space-y-6">
      <header>
        <h1 className="text-lg font-medium text-obsidian">
          Which fragment continues this session better?
        </h1>
        <p className="mt-1 text-sm text-slate">
          Listen to the context, preview both candidates, and pick the one you
          would try next. There is no right answer — your judgment is the data.
        </p>
      </header>
      <AnnotatePanel
        fetchNext={fetchNext}
        submitLabel={submitLabel}
        onPreview={preview}
      />
    </main>
  );
}
