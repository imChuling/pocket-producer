"use client";

import { useEffect, useState } from "react";

// The backend scales to zero between visitors (a deployment-cost choice, see
// docs/MAINTAINING.md), so the first visit after a quiet period waits while
// the container starts and loads the audio model. This banner says so, and
// tracks /ready until the backend answers that it is up; then it disappears.

type Phase = "checking" | "starting" | "loading" | "ready" | "slow";

const POLL_MS = 5_000;
const GIVE_UP_MS = 4 * 60_000;
const SHOW_AFTER_MS = 2_500;

const COPY: Record<Exclude<Phase, "ready" | "checking">, string> = {
  starting:
    "Because of deployment limits this demo scales to zero when idle. The backend is starting now, which takes one to two minutes after a quiet period.",
  loading:
    "The backend is up and is loading the audio model (about a minute). You can sign in meanwhile; audio-aware ranking works as soon as this notice disappears.",
  slow:
    "The backend is taking longer than usual to start. Please reload the page in a minute.",
};

async function probe(): Promise<Phase> {
  try {
    const response = await fetch("/ready", { cache: "no-store" });
    if (response.status >= 500 && response.status !== 503) return "starting";
    const data = (await response.json()) as { mongo?: string; clap?: string };
    if (data.mongo !== "ok") return "starting";
    if (data.clap === "loading") return "loading";
    return "ready";
  } catch {
    return "starting";
  }
}

export function BackendStatus() {
  const [phase, setPhase] = useState<Phase>("checking");

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();
    let timer: ReturnType<typeof setTimeout> | null = null;

    // Only show the banner if the backend has not answered quickly: a warm
    // backend replies in well under a second and nobody needs to see this.
    const reveal = setTimeout(() => {
      setPhase((current) => (current === "checking" ? "starting" : current));
    }, SHOW_AFTER_MS);

    const tick = async () => {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        timer = setTimeout(tick, POLL_MS);
        return;
      }
      const next = await probe();
      if (cancelled) return;
      if (next === "ready") {
        setPhase("ready");
        return;
      }
      setPhase(Date.now() - started > GIVE_UP_MS ? "slow" : next);
      if (Date.now() - started <= GIVE_UP_MS) timer = setTimeout(tick, POLL_MS);
    };
    void tick();

    return () => {
      cancelled = true;
      clearTimeout(reveal);
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (phase === "ready" || phase === "checking") return null;

  return (
    <div
      role="status"
      className="mx-auto mt-3 w-full max-w-3xl rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-center text-xs text-amber-900"
    >
      {COPY[phase]}
    </div>
  );
}
