"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "./use-auth";
import type { Fragment } from "@/types";

const POLL_INTERVAL = 10_000;
// After this long a "processing" fragment is stuck (the capture page shows
// the same threshold with a fix-up action); polling it would never end.
const STUCK_AFTER_MS = 2 * 60 * 1000;

function stillProcessing(fragment: Fragment): boolean {
  if (fragment.status !== "processing") return false;
  if (fragment.tags && fragment.tags.length > 0) return false;
  const started = new Date(fragment.created_at).getTime();
  return !Number.isFinite(started) || Date.now() - started < STUCK_AFTER_MS;
}

export function useFragments() {
  const { user } = useAuth();
  const [fragments, setFragments] = useState<Fragment[]>([]);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiFetch<{ fragments: Fragment[] }>("/fragments?limit=200");
      setFragments(data.fragments);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [user]);

  // Initial fetch
  useEffect(() => {
    const id = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(id);
  }, [refresh]);

  // Auto-poll while any fragment can still finish processing
  useEffect(() => {
    const hasProcessing = fragments.some(stillProcessing);

    if (hasProcessing) {
      if (!timerRef.current) {
        timerRef.current = setInterval(() => {
          // A background tab gets the fresh list when it comes back.
          if (document.visibilityState === "hidden") return;
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

  return { fragments, loading, refresh };
}
