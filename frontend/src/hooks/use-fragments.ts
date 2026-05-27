"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "./use-auth";
import type { Fragment } from "@/types";

const POLL_INTERVAL = 10_000;

export function useFragments() {
  const { user } = useAuth();
  const [fragments, setFragments] = useState<Fragment[]>([]);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiFetch<{ fragments: Fragment[] }>("/fragments?limit=20");
      setFragments(data.fragments);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [user]);

  // Initial fetch
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Auto-poll while any fragment is still processing
  useEffect(() => {
    const hasProcessing = fragments.some((f) => f.status === "processing");

    if (hasProcessing) {
      if (!timerRef.current) {
        timerRef.current = setInterval(refresh, POLL_INTERVAL);
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
