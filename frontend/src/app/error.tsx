"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 px-6">
      <h2 className="font-heading text-2xl text-obsidian">
        Something went wrong
      </h2>
      <p className="text-sm text-gravel max-w-md text-center">
        An unexpected error occurred. You can try again, or go back to the home
        page.
      </p>
      {error.digest && (
        <code className="font-mono text-[10px] text-slate">
          {error.digest}
        </code>
      )}
      <div className="flex gap-3">
        <button
          onClick={() => unstable_retry()}
          className="px-5 py-2 rounded-full bg-obsidian text-white text-xs font-mono tracking-wider hover:bg-obsidian/90 transition-colors btn-press"
        >
          Try again
        </button>
        <Link
          href="/"
          className="px-5 py-2 rounded-full border border-chalk text-gravel text-xs font-mono tracking-wider hover:border-slate/50 transition-colors"
        >
          Home
        </Link>
      </div>
    </div>
  );
}
