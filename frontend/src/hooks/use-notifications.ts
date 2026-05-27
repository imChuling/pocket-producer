"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import { useAuth } from "./use-auth";
import type { Notification } from "@/types";

const POLL_INTERVAL = 30_000; // 30 seconds

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
    if (user) refresh();
  }, [user, refresh]);

  // Poll periodically for new notifications
  useEffect(() => {
    if (!user) return;
    timerRef.current = setInterval(refresh, POLL_INTERVAL);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
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
