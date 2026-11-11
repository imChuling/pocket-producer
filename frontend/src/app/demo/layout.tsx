"use client";

import { useState, useCallback, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Mic, Layers, Dna, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { DemoToastContext } from "./demo-context";

const demoNavLinks = [
  { href: "/demo/capture", icon: Mic, label: "Capture" },
  { href: "/demo/projects", icon: Layers, label: "Projects" },
  { href: "/demo/dna", icon: Dna, label: "DNA" },
] as const;

export default function DemoLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((msg?: string) => {
    setToast(msg || "This is a read-only demo. Your content will not be transmitted or processed.");
    setTimeout(() => setToast(null), 4000);
  }, []);

  return (
    <DemoToastContext.Provider value={showToast}>
      {/* Demo sub-nav below the main TopNav */}
      <div className="sticky top-14 z-40 bg-[#fdfcfb]/80 backdrop-blur-xl border-b border-chalk/40">
        <div className="flex items-center justify-center h-11 px-6 gap-1">
          {demoNavLinks.map(({ href, icon: Icon, label }) => {
            const active = pathname === href || (href === "/demo/capture" && pathname === "/demo");
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm transition-all duration-200 cursor-pointer btn-press ${
                  active
                    ? "text-white"
                    : "text-gravel hover:text-obsidian hover:bg-powder"
                }`}
                style={active ? {
                  background: "linear-gradient(135deg, #1a1a1a, #2a2a3a)",
                } : undefined}
              >
                <Icon size={15} strokeWidth={active ? 2 : 1.5} />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </div>
      </div>

      <p className="px-6 pt-4 text-center text-[11px] leading-relaxed text-slate">
        Fragment audio is royalty-free loops from{" "}
        <a
          href="https://www.looperman.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2 hover:text-gravel"
        >
          Looperman
        </a>
        . Lyrics are AI-generated samples.
      </p>

      {children}

      {/* Toast overlay */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: 20, filter: "blur(4px)" }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-2xl shadow-lg max-w-md"
            style={{
              background: "linear-gradient(135deg, rgba(26,26,26,0.95), rgba(42,42,58,0.95))",
              backdropFilter: "blur(12px)",
            }}
          >
            <p className="text-sm text-white/90 leading-snug">{toast}</p>
            <button
              onClick={() => setToast(null)}
              className="p-1 rounded-full hover:bg-white/10 transition-colors flex-shrink-0 cursor-pointer"
            >
              <X size={14} className="text-white/60" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </DemoToastContext.Provider>
  );
}
