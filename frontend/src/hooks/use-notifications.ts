"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import { onActive, shouldPoll } from "@/lib/idle";
import { useAuth } from "./use-auth";
import type { Notification } from "@/types";

const POLL_INTERVAL = 30_000; // 30 seconds, only while the tab is visible and in use

export function useNotifications() {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiFetch<{
        notifications: Notification[];
        unread_count: number;
      }>("/notifications");
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [user]);

  // Initial fetch
  useEffect(() => {
    if (!user) return;
    const id = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(id);
  }, [user, refresh]);

  // Poll periodically for new notifications. A hidden or idle tab skips the
  // request (see lib/idle.ts) and catches up once the user is back.
  useEffect(() => {
    if (!user) return;
    timerRef.current = setInterval(() => {
      if (shouldPoll()) void refresh();
    }, POLL_INTERVAL);
    const stop = onActive(() => void refresh());
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      stop();
    };
  }, [user, refresh]);

  const markRead = useCallback(
    async (id: string) => {
      try {
        await apiPost(`/notifications/${id}/read`, {});
        setNotifications((prev) =>
          prev.map((n) => (n._id === id ? { ...n, read: true } : n))
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch {
        /* silent */
      }
    },
    []
  );

  const markAllRead = useCallback(async () => {
    try {
      await apiPost("/notifications/read-all", {});
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch {
      /* silent */
    }
  }, []);

  return { notifications, unreadCount, loading, refresh, markRead, markAllRead };
}
