"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { shouldPoll } from "@/lib/idle";
import { useAuth } from "./use-auth";
import type { Fragment } from "@/types";

const POLL_INTERVAL = 10_000;
const EMPTY_FRAGMENTS: Fragment[] = [];

type FragmentPage = { fragments: Fragment[]; next_cursor?: string | null };

export function useFragments(before: string | null = null) {
  const { user } = useAuth();
  const [loaded, setLoaded] = useState<{
    scope: string;
    page: FragmentPage;
    error?: string;
  } | null>(null);
  const latestRequest = useRef<symbol | null>(null);
  const scope = JSON.stringify([user?.uid, before]);
  const current = loaded?.scope === scope ? loaded : null;
  const fragments = current?.page.fragments ?? EMPTY_FRAGMENTS;
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    const request = Symbol();
    latestRequest.current = request;
    const query = new URLSearchParams({ limit: "200" });
    if (before) query.set("before", before);
    try {
      const page = await apiFetch<FragmentPage>(`/fragments?${query}`);
      if (request === latestRequest.current) setLoaded({ scope, page });
    } catch {
      if (request === latestRequest.current) {
        setLoaded((previous) => ({
          scope,
          page: previous?.scope === scope ? previous.page : { fragments: [] },
          error: "Could not load your sketches.",
        }));
      }
    }
  }, [user, before, scope]);

  // Initial fetch
  useEffect(() => {
    const id = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => {
      window.clearTimeout(id);
      latestRequest.current = null;
    };
  }, [refresh]);

  // Auto-poll while any fragment can still finish processing
  useEffect(() => {
    const hasProcessing = fragments.some((fragment) => fragment.status === "processing" &&
      !fragment.analysis_stalled &&
      fragment.pipeline_step !== "done" && fragment.pipeline_step !== "error");

    if (hasProcessing) {
      if (!timerRef.current) {
        timerRef.current = setInterval(() => {
          // A hidden or idle tab gets the fresh list when the user is back.
          if (!shouldPoll()) return;
          void refresh();
        }, POLL_INTERVAL);
      }
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [fragments, refresh]);

  return { fragments, loading: !current, refresh, nextCursor: current?.page.next_cursor, error: current?.error };
}
