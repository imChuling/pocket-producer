"use client";

import { useState, useEffect } from "react";
import { Mic, Send, Upload } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { FragmentCard } from "@/components/fragment-card";
import { useDemoToast } from "../demo-context";
import { loadDemo } from "../demo-data";
import type { Fragment } from "@/types";

export default function DemoCapturePage() {
  const showToast = useDemoToast();
  const [fragments, setFragments] = useState<Fragment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDemo<{ fragments?: Fragment[] }>("fragments", "fragments?limit=100")
      .then((data) => setFragments(data.fragments ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="relative min-h-[calc(100vh-56px-44px)]">
      <div className="ambient-mesh" />
      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 animate-page-enter">
        <div className="flex flex-col lg:flex-row gap-8 lg:gap-10">
          {/* Left sidebar -- read-only placeholders */}
          <div className="lg:w-[340px] flex-shrink-0">
            <div className="lg:sticky lg:top-[calc(56px+44px+20px)] space-y-6">
              <div className="space-y-1">
                <p className="font-mono text-[10px] font-medium uppercase tracking-[0.3em] text-slate">
                  Demo account
                </p>
                <h1 className="font-heading text-3xl font-light text-obsidian tracking-tight leading-[1.08]">
                  Capture a moment
                </h1>
              </div>

              {/* Fake recorder button */}
              <div className="flex flex-col items-center py-4">
                <div className="relative">
                  <div
                    className="absolute inset-0 -m-10 rounded-full opacity-40 pointer-events-none"
                    style={{
                      background: "radial-gradient(circle, rgba(160,181,235,0.18) 0%, rgba(226,193,97,0.06) 50%, transparent 70%)",
                      filter: "blur(24px)",
                    }}
                  />
                  <button
                    onClick={() => showToast()}
                    className="w-[72px] h-[72px] rounded-full flex items-center justify-center cursor-pointer transition-all hover:scale-105 btn-press"
                    style={{
                      background: "linear-gradient(135deg, #a0b5eb, #e2c161)",
                      boxShadow: "0 4px 24px rgba(160,181,235,0.3)",
                    }}
                  >
                    <Mic size={28} className="text-white" />
                  </button>
                </div>
              </div>

              {/* Fake text input */}
              <div
                onClick={() => showToast()}
                className="flex items-center gap-2 bg-white rounded-2xl px-5 py-3 shadow-hairline gradient-border cursor-pointer"
              >
                <span className="flex-1 text-sm text-slate">
                  Type a lyric, idea, or note...
                </span>
                <div className="p-2 rounded-full">
                  <Send size={16} className="text-slate/40" />
                </div>
              </div>

              {/* Fake dropzone */}
              <div
                onClick={() => showToast()}
                className="border-2 border-dashed border-chalk rounded-2xl py-6 flex flex-col items-center gap-2 cursor-pointer hover:border-gravel/30 transition-colors"
              >
                <Upload size={20} className="text-slate" />
                <p className="text-xs text-slate">Drop audio file or click</p>
              </div>

              {/* Demo info banner */}
              <div
                className="rounded-xl px-4 py-3 text-[13px] text-gravel leading-relaxed"
                style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.1), rgba(226,193,97,0.06))" }}
              >
                This is a read-only demo account. Play any fragment, open a project, or browse the DNA page. Nothing you do here is saved.
              </div>
            </div>
          </div>

          {/* Right side -- fragment grid */}
          <div className="flex-1 min-w-0">
            {loading && (
              <div className="flex justify-center py-20">
                <div className="w-8 h-8 rounded-full border-2 border-chalk border-t-gravel animate-spin" />
              </div>
            )}

            {!loading && fragments.length > 0 && (
              <div className="space-y-5 pb-12">
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
                        <FragmentCard
                          fragment={f}
                          readOnly
                          onReadOnlyAction={() => showToast()}
                        />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            )}

            {!loading && fragments.length === 0 && (
              <div className="text-center py-20 space-y-3">
                <p className="text-sm text-gravel">No demo fragments yet.</p>
                <p className="text-xs text-slate">The seed account has not been populated.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
