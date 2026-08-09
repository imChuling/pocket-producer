"use client";

import { Cable, Loader2 } from "lucide-react";

import type { AudiotoolStatus } from "@/types/audiotool";

export function ConnectionPanel({
  status,
  error,
  onConnect,
}: {
  status: AudiotoolStatus;
  error: string | null;
  onConnect: () => void;
}) {
  const busy = status === "authorizing";
  return (
    <div className="mx-auto max-w-md rounded-xl border border-chalk bg-powder p-8 text-center space-y-4">
      <Cable className="mx-auto h-8 w-8 text-slate" />
      <h1 className="text-lg font-medium text-obsidian">
        Continue a session in Audiotool
      </h1>
      <p className="text-sm text-slate">
        Pocket Producer reads your open project&apos;s tempo and tracks to
        suggest fragments from your own library. It asks for{" "}
        <code className="text-gravel">project:write</code> so it can insert a
        fragment you choose — every insert is undoable, and you can disconnect
        at any time. Your Audiotool login never leaves this browser.
      </p>
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-left text-sm text-red-700"
        >
          <p>{error}</p>
          {/^popup was blocked/i.test(error) && (
            <p className="mt-2 text-red-600">
              Your browser blocked the sign-in window. Allow pop-ups for this
              site (the blocked-pop-up icon sits at the right of the address
              bar), then press Connect again.
            </p>
          )}
        </div>
      )}
      <button
        type="button"
        disabled={busy}
        onClick={onConnect}
        className="inline-flex items-center gap-2 rounded-lg bg-obsidian px-4 py-2 text-sm font-medium text-white hover:bg-gravel disabled:opacity-60"
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        {busy ? "Waiting for Audiotool…" : "Connect Audiotool"}
      </button>
    </div>
  );
}
