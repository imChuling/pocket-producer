// Shared "is anyone actually here?" signal for background polling.
//
// A tab left open on a second monitor used to poll every 30 s around the
// clock, which kept the scaled-to-zero backend's instance alive for a week
// (201 billable hours in October 2026). Pollers call `shouldPoll` before each
// request: hidden tabs and tabs with no pointer or key activity for
// IDLE_AFTER_MS skip the request, and `onActive` lets them refresh once when
// the user comes back.

export const IDLE_AFTER_MS = 10 * 60 * 1000;

const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart"] as const;

let lastActivity = 0;
let listening = false;
const activeListeners = new Set<() => void>();

function now(): number {
  return Date.now();
}

function markActive() {
  const wasIdle = lastActivity > 0 && now() - lastActivity > IDLE_AFTER_MS;
  lastActivity = now();
  if (wasIdle) for (const cb of activeListeners) cb();
}

function ensureListening() {
  if (listening || typeof window === "undefined") return;
  listening = true;
  lastActivity = now();
  for (const name of ACTIVITY_EVENTS) {
    window.addEventListener(name, markActive, { passive: true, capture: true });
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") markActive();
  });
}

/** True when the tab is visible and the user did something recently. */
export function shouldPoll(idleAfterMs: number = IDLE_AFTER_MS): boolean {
  ensureListening();
  if (typeof document !== "undefined" && document.visibilityState === "hidden") return false;
  return now() - lastActivity <= idleAfterMs;
}

/** Run `cb` when the user returns after being idle or away. Returns an unsubscribe. */
export function onActive(cb: () => void): () => void {
  ensureListening();
  activeListeners.add(cb);
  return () => {
    activeListeners.delete(cb);
  };
}

/** Test hook: pretend the last activity happened `ms` ago. */
export function _setLastActivityForTests(ms: number): void {
  ensureListening();
  lastActivity = now() - ms;
}
