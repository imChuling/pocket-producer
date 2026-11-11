"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { FragmentCard } from "@/components/fragment-card";
import type { Fragment } from "@/types";

const API_BASE = "/api";

export default function DemoPage() {
  const [fragments, setFragments] = useState<Fragment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/demo/fragments?limit=200`)
      .then((r) => r.json())
      .then((data) => {
        setFragments(data.fragments ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="relative min-h-screen bg-[#fdfcfc]">
      <div className="max-w-[1100px] mx-auto px-6 py-10">
        <div className="flex items-center gap-4 mb-8">
          <Link
            href="/"
            className="p-2 rounded-full hover:bg-powder transition-colors"
          >
            <ArrowLeft size={16} className="text-gravel" />
          </Link>
          <div>
            <h1 className="font-heading text-2xl font-light text-obsidian tracking-tight">
              Demo Account
            </h1>
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-slate mt-0.5">
              Read-only preview of a seed library
            </p>
          </div>
        </div>

        <div className="mb-6 px-4 py-3 rounded-xl text-[13px] text-gravel leading-relaxed"
          style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.1), rgba(226,193,97,0.06))" }}
        >
          This is a read-only demo showing how Pocket Producer organizes musical fragments.
          Each fragment was analyzed by AI for emotion, key, tempo, and themes, then grouped
          into projects automatically.{" "}
          <Link href="/" className="underline text-obsidian">
            Sign in
          </Link>{" "}
          to start your own library.
        </div>

        {loading && (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 rounded-full border-2 border-chalk border-t-gravel animate-spin" />
          </div>
        )}

        {!loading && fragments.length === 0 && (
          <div className="text-center py-20 space-y-3">
            <p className="text-sm text-gravel">No demo fragments yet.</p>
            <p className="text-xs text-slate">The seed account has not been populated.</p>
          </div>
        )}

        {!loading && fragments.length > 0 && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                Fragments
              </span>
              <div className="flex-1 h-px bg-gradient-to-r from-chalk to-transparent" />
              <span
                className="font-mono text-[11px] text-gravel px-2.5 py-0.5 rounded-full"
                style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.15), rgba(226,193,97,0.1))" }}
              >
                {fragments.length}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
              <AnimatePresence mode="popLayout">
                {fragments.map((f, i) => (
                  <motion.div
                    key={f._id}
                    layout
                    initial={{ opacity: 0, y: 24, scale: 0.96, filter: "blur(4px)" }}
                    animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
                    transition={{ type: "spring", stiffness: 200, damping: 22, delay: i * 0.05 }}
                  >
                    <FragmentCard fragment={f} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
