"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronRight, X } from "lucide-react";

interface TourStep {
  title: string;
  body: string;
  target?: string;
  position?: "top" | "bottom" | "left" | "right" | "center";
}

const DASHBOARD_STEPS: TourStep[] = [
  {
    title: "Welcome to Pocket Producer",
    body: "An AI memory system for music creators. Capture ideas as fragments, and the system finds connections you might have missed.",
    position: "center",
  },
  {
    title: "Capture",
    body: "Record audio, type lyrics, drop files, or import from Audiotool. Each fragment gets analyzed for emotion, key, tempo, and structural role.",
    target: "[data-tour='capture']",
    position: "right",
  },
  {
    title: "AI Analysis Pipeline",
    body: "Audio fragments run through a CLAP audio embedding model, spectral analysis, and LLM interpretation. The pipeline takes 30-60 seconds and shows each step in real time.",
    target: "[data-tour='fragments']",
    position: "left",
  },
  {
    title: "Automatic Project Grouping",
    body: "Fragments with shared emotional DNA, harmonic compatibility, or thematic overlap are grouped into projects automatically. Open Projects to see how the system clusters your ideas.",
    target: "[data-tour='nav-projects']",
    position: "bottom",
  },
  {
    title: "Ranking Pipeline",
    body: "In an open Audiotool session, a transparent rules ranker proposes which fragments fit next, with per-signal evidence for each proposal. A learned five-signal fusion is available as an alternative you can switch to.",
    position: "center",
  },
  {
    title: "Creator DNA",
    body: "Your creative patterns over time: emotional fingerprints, peak capture hours, stylistic evolution. Open DNA to see your artistic identity in data.",
    target: "[data-tour='nav-dna']",
    position: "bottom",
  },
];

const PROJECT_STEPS: TourStep[] = [
  {
    title: "Project Detail",
    body: "Each project groups fragments the system believes belong together. The pipeline analysis shows key center, tempo, shared traits, and dominant feel.",
    target: "[data-tour='intelligence']",
    position: "bottom",
  },
  {
    title: "Rescue Score",
    body: "Four dimensions score the project's completeness: richness (variety of material), structure, emotional coherence, and freshness (recent activity).",
    target: "[data-tour='rescue-score']",
    position: "right",
  },
  {
    title: "Connection Evidence",
    body: "The system explains why these fragments connect: shared emotion, harmonic compatibility, thematic overlap. Each fragment shows its individual connection reason.",
    target: "[data-tour='connections']",
    position: "right",
  },
  {
    title: "Next Action",
    body: "An LLM-generated suggestion for what to work on next, based on what the project has and what it lacks.",
    target: "[data-tour='next-action']",
    position: "right",
  },
];

function getSteps(context: "dashboard" | "project"): TourStep[] {
  return context === "project" ? PROJECT_STEPS : DASHBOARD_STEPS;
}

function Spotlight({
  step,
  current,
  total,
  onNext,
  onClose,
}: {
  step: TourStep;
  current: number;
  total: number;
  onNext: () => void;
  onClose: () => void;
}) {
  // Measured per step; `pos: null` means the step's target was not found.
  const [measured, setMeasured] = useState<{
    step: TourStep;
    pos: { top: number; left: number } | null;
  } | null>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  useEffect(() => {
    const { target, position } = step;
    if (!target || position === "center") return;
    // Measure in the next frame so the step's target has been laid out.
    const frame = requestAnimationFrame(() => {
      const el = document.querySelector(target);
      if (!el) {
        setMeasured({ step, pos: null });
        return;
      }
      const rect = el.getBoundingClientRect();
      const scrollY = window.scrollY;
      const scrollX = window.scrollX;

      let top = rect.top + scrollY;
      let left = rect.left + scrollX;

      switch (position) {
        case "bottom":
          top = rect.bottom + scrollY + 12;
          left = rect.left + scrollX + rect.width / 2;
          break;
        case "top":
          top = rect.top + scrollY - 12;
          left = rect.left + scrollX + rect.width / 2;
          break;
        case "right":
          top = rect.top + scrollY + rect.height / 2;
          left = rect.right + scrollX + 12;
          break;
        case "left":
          top = rect.top + scrollY + rect.height / 2;
          left = rect.left + scrollX - 12;
          break;
      }

      const pad = 16;
      top = Math.max(pad, Math.min(top, document.documentElement.scrollHeight - pad));
      left = Math.max(pad, Math.min(left, window.innerWidth - pad));

      setMeasured({ step, pos: { top, left } });
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    return () => cancelAnimationFrame(frame);
  }, [step]);

  const measure = measured?.step === step ? measured : null;
  const pos = measure?.pos ?? null;
  const isCenter =
    !step.target || step.position === "center" || (measure !== null && pos === null);
  // A targeted step stays hidden for the frame before its target is measured.
  const pending = !isCenter && measure === null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-[9999]"
      onClick={onNext}
    >
      <div className="absolute inset-0 bg-obsidian/30 backdrop-blur-[2px]" />

      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -10, scale: 0.97 }}
        transition={{ type: "spring", stiffness: 300, damping: 25 }}
        className="absolute bg-white rounded-2xl p-5 shadow-xl max-w-[340px] w-[90vw]"
        style={
          isCenter || pending
            ? {
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                visibility: pending ? "hidden" : undefined,
              }
            : {
                top: pos!.top,
                left: pos!.left,
                transform:
                  step.position === "bottom" || step.position === "top"
                    ? "translateX(-50%)"
                    : step.position === "left"
                    ? "translate(-100%, -50%)"
                    : "translateY(-50%)",
              }
        }
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 p-1 rounded-full hover:bg-powder transition-colors"
          aria-label="Close tour"
        >
          <X size={14} className="text-slate" />
        </button>

        <div className="space-y-2.5 pr-6">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-slate">
              {current + 1}/{total}
            </span>
          </div>
          <h3 className="text-sm font-medium text-obsidian">{step.title}</h3>
          <p className="text-xs text-gravel leading-relaxed">{step.body}</p>
        </div>

        <div className="flex items-center justify-between mt-4 pt-3 border-t border-chalk">
          <button
            onClick={onClose}
            className="text-[11px] text-slate hover:text-gravel transition-colors"
          >
            Skip tour
          </button>
          <button
            onClick={onNext}
            className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-obsidian text-white text-[11px] font-medium hover:bg-obsidian/85 transition-colors"
          >
            {current < total - 1 ? (
              <>
                Next <ChevronRight size={12} />
              </>
            ) : (
              "Done"
            )}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

const TOUR_KEY = "pocket-producer-tour-seen";

export function useGuidedTour(context: "dashboard" | "project") {
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const steps = getSteps(context);

  const start = useCallback(() => {
    setStepIndex(0);
    setActive(true);
  }, []);

  const close = useCallback(() => {
    setActive(false);
    try {
      const seen = JSON.parse(localStorage.getItem(TOUR_KEY) || "{}");
      seen[context] = true;
      localStorage.setItem(TOUR_KEY, JSON.stringify(seen));
    } catch {}
  }, [context]);

  const next = useCallback(() => {
    if (stepIndex < steps.length - 1) {
      setStepIndex((i) => i + 1);
    } else {
      close();
    }
  }, [stepIndex, steps.length, close]);

  const shouldAutoStart = useCallback(() => {
    try {
      const seen = JSON.parse(localStorage.getItem(TOUR_KEY) || "{}");
      return !seen[context];
    } catch {
      return false;
    }
  }, [context]);

  return { active, stepIndex, steps, start, close, next, shouldAutoStart };
}

export function GuidedTour({
  context,
  autoStart = false,
}: {
  context: "dashboard" | "project";
  autoStart?: boolean;
}) {
  const { active, stepIndex, steps, start, close, next, shouldAutoStart } = useGuidedTour(context);

  useEffect(() => {
    if (autoStart && shouldAutoStart()) {
      const timer = setTimeout(() => start(), 800);
      return () => clearTimeout(timer);
    }
  }, [autoStart, shouldAutoStart, start]);

  return (
    <>
      <AnimatePresence>
        {active && (
          <Spotlight
            step={steps[stepIndex]}
            current={stepIndex}
            total={steps.length}
            onNext={next}
            onClose={close}
          />
        )}
      </AnimatePresence>

      {!active && (
        <button
          onClick={start}
          className="fixed bottom-5 right-5 z-50 w-9 h-9 rounded-full bg-white shadow-lg flex items-center justify-center text-sm font-medium text-gravel hover:text-obsidian hover:shadow-xl transition-all border border-chalk"
          aria-label="Start guided tour"
          title="Take a tour"
        >
          ?
        </button>
      )}
    </>
  );
}
