"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Send, Loader2 } from "lucide-react";
import { motion, AnimatePresence, useScroll, useTransform } from "motion/react";
import { useAuth } from "@/hooks/use-auth";
import { useFragments } from "@/hooks/use-fragments";
import { apiPost } from "@/lib/api";
import { signInWithGoogle } from "@/lib/firebase";
import { AudioRecorder } from "@/components/audio-recorder";
import { FileDropzone } from "@/components/file-dropzone";
import { FragmentCard } from "@/components/fragment-card";

/* ═══════════════════════════════════════════════════════════════════════
   NOISE TEXTURE — film grain for editorial feel
   ═══════════════════════════════════════════════════════════════════════ */
function NoiseTexture() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    c.width = 256;
    c.height = 256;
    const img = ctx.createImageData(256, 256);
    for (let i = 0; i < img.data.length; i += 4) {
      const v = Math.random() * 255;
      img.data[i] = v;
      img.data[i + 1] = v;
      img.data[i + 2] = v;
      img.data[i + 3] = 14;
    }
    ctx.putImageData(img, 0, 0);
  }, []);
  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-[100] opacity-30"
      style={{ width: "100%", height: "100%", mixBlendMode: "multiply" }}
    />
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   INK CANVAS — organic generative background
   ═══════════════════════════════════════════════════════════════════════ */
function InkCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    let w = 0, h = 0;

    function resize() {
      const r = canvas!.getBoundingClientRect();
      w = r.width; h = r.height;
      canvas!.width = w * dpr;
      canvas!.height = h * dpr;
      ctx!.setTransform(1, 0, 0, 1, 0, 0);
      ctx!.scale(dpr, dpr);
    }
    resize();
    window.addEventListener("resize", resize);

    let frame = 0;
    let raf = 0;

    const palette = [
      [160, 181, 235],
      [255, 148, 115],
      [226, 193, 97],
      [143, 163, 208],
      [200, 170, 160],
    ];

    function draw() {
      frame++;
      const t = frame * 0.005;
      ctx!.clearRect(0, 0, w, h);

      // Flowing ink strands
      for (let strand = 0; strand < 7; strand++) {
        const col = palette[strand % palette.length];
        const phase = strand * 1.3;
        const yBase = h * (0.12 + strand * 0.115);

        ctx!.beginPath();
        ctx!.moveTo(-20, yBase);

        for (let x = -20; x <= w + 20; x += 3) {
          const nx = x / w;
          const wave1 = Math.sin(nx * 4 + t * 1.2 + phase) * 45;
          const wave2 = Math.sin(nx * 8 + t * 0.7 - phase * 0.5) * 22;
          const wave3 = Math.cos(nx * 2.5 + t * 0.4 + strand) * 30;
          const breathe = Math.sin(t * 0.3 + strand * 0.6) * 15;
          const y = yBase + wave1 + wave2 + wave3 + breathe;
          ctx!.lineTo(x, y);
        }

        const alpha = 0.09 + Math.sin(t * 0.5 + strand) * 0.025;
        ctx!.strokeStyle = `rgba(${col[0]},${col[1]},${col[2]},${alpha * 3.2})`;
        ctx!.lineWidth = 1.8 + Math.sin(t + strand) * 0.7;
        ctx!.stroke();

        ctx!.lineTo(w + 20, h);
        ctx!.lineTo(-20, h);
        ctx!.closePath();
        ctx!.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${alpha * 0.5})`;
        ctx!.fill();
      }

      // Drifting particles
      for (let i = 0; i < 45; i++) {
        const seed = i * 137.508;
        const px = ((seed * 7.3 + t * 25 * (0.3 + (i % 3) * 0.2)) % (w + 100)) - 50;
        const py = (seed * 3.1 + Math.sin(t + i) * 50) % h;
        const size = 1.2 + (i % 4) * 0.8;
        const col = palette[i % palette.length];
        const a = 0.25 + Math.sin(t * 2 + seed) * 0.12;
        ctx!.beginPath();
        ctx!.arc(px, py, size, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${a})`;
        ctx!.fill();
      }

      raf = requestAnimationFrame(draw);
    }

    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />;
}

/* ═══════════════════════════════════════════════════════════════════════
   REVEAL — scroll-triggered entrance with spring physics
   ═══════════════════════════════════════════════════════════════════════ */
function Reveal({
  children,
  className = "",
  delay = 0,
  direction = "up",
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "left" | "right";
}) {
  const variants = {
    up: { y: 60, x: 0 },
    left: { y: 0, x: -60 },
    right: { y: 0, x: 60 },
  };
  const from = variants[direction];
  return (
    <motion.div
      initial={{ opacity: 0, ...from, filter: "blur(6px)" }}
      whileInView={{ opacity: 1, y: 0, x: 0, filter: "blur(0px)" }}
      viewport={{ once: false, amount: 0.12 }}
      transition={{ type: "spring", stiffness: 45, damping: 16, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   MARQUEE — kinetic horizontal scroll divider
   ═══════════════════════════════════════════════════════════════════════ */
function Marquee({ text, className = "" }: { text: string; className?: string }) {
  return (
    <div className={`overflow-hidden whitespace-nowrap ${className}`}>
      <motion.div
        className="inline-block"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: 50, ease: "linear", repeat: Infinity }}
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <span key={i} className="mx-8">{text}</span>
        ))}
      </motion.div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   LANDING PAGE — editorial, artistic, breaking the grid
   ═══════════════════════════════════════════════════════════════════════ */
function LandingPage() {
  const { scrollYProgress, scrollY } = useScroll();
  const heroOpacity = useTransform(scrollYProgress, [0, 0.12], [1, 0]);
  const ghostY = useTransform(scrollY, [0, 800], [0, 100]);
  const titleShiftL = useTransform(scrollY, [0, 800], [0, -50]);
  const titleShiftR = useTransform(scrollY, [0, 800], [0, 40]);
  const isShiftY = useTransform(scrollY, [0, 800], [0, 25]);

  return (
    <div className="overflow-hidden bg-[#fdfcfc]">
      <NoiseTexture />

      {/* ═════════════════════════════════════════════════════════════
          HERO — full-bleed typographic statement, not a neat grid
          ═════════════════════════════════════════════════════════════ */}
      <section className="relative min-h-screen flex flex-col justify-end pb-16 md:pb-24 overflow-x-clip">
        {/* Gradient wash — subtle warm→cool */}
        <div
          className="absolute inset-0"
          style={{
            background: "linear-gradient(160deg, rgba(207,218,245,0.18) 0%, rgba(253,252,252,0) 35%, rgba(255,167,115,0.08) 70%, rgba(226,193,97,0.06) 100%)",
          }}
        />

        {/* Generative ink background */}
        <div className="absolute inset-0 opacity-90">
          <InkCanvas />
        </div>

        {/* Ghost word — bleeds off screen, parallax */}
        <motion.div
          style={{ y: ghostY }}
          className="absolute top-[4vh] inset-x-0 pointer-events-none select-none leading-[0.82] overflow-visible"
        >
          <span
            className="font-heading font-light flex flex-col leading-[0.85]"
            style={{
              color: "transparent",
              WebkitTextStroke: "1.5px rgba(0,0,0,0.06)",
            }}
          >
            <span className="text-right" style={{ fontSize: "clamp(8rem, 18vw, 24rem)" }}>POCKET</span>
            <span className="text-left pl-[2vw]" style={{ fontSize: "clamp(8rem, 18vw, 24rem)", letterSpacing: "0.06em" }}>PRODUCER</span>
          </span>
        </motion.div>

        {/* Headline — staggered type, breaking alignment */}
        <motion.div style={{ opacity: heroOpacity }} className="relative z-20 px-6 md:px-12">
          <div className="mb-8 md:mb-12 max-w-[1300px] mx-auto">
            {/* "Nothing" — massive, left flush */}
            <motion.h1
              initial={{ opacity: 0, y: 40, filter: "blur(14px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{ type: "spring", stiffness: 28, damping: 14, delay: 0.5 }}
              style={{ x: titleShiftL }}
              className="font-heading font-light text-obsidian tracking-[-0.03em] leading-[0.85] mb-2"
            >
              <span style={{ fontSize: "clamp(4.5rem, 13vw, 11rem)" }}>Nothing</span>
            </motion.h1>

            {/* "is lost" — indented, "is" italic & faded — visual tension */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 30, damping: 14, delay: 0.8 }}
              className="flex items-baseline gap-4 md:gap-6 ml-[10vw] md:ml-[15vw]"
            >
              <motion.span
                style={{ y: isShiftY }}
                className="font-heading font-light italic text-gravel/40 leading-[0.85]"
              >
                <span style={{ fontSize: "clamp(4rem, 10vw, 8rem)" }}>is</span>
              </motion.span>
              <motion.span
                style={{ x: titleShiftR }}
                className="font-heading font-light text-obsidian tracking-[-0.03em] leading-[0.85]"
              >
                <span style={{ fontSize: "clamp(4.5rem, 13vw, 11rem)" }}>lost</span>
              </motion.span>
            </motion.div>
          </div>

          {/* Subtext + CTA — asymmetric placement */}
          <div className="max-w-[1300px] mx-auto flex flex-col md:flex-row md:items-end justify-between gap-8">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 1.2 }}
              className="max-w-[340px] md:ml-[15vw]"
            >
              <p className="text-[13px] md:text-[14px] text-gravel leading-[1.9]">
                The melody you hummed at 3 AM.<br />
                The lyric that arrived mid-conversation.<br />
                <span className="text-obsidian">AI preserves the spark.</span>
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.6 }}
              className="flex flex-col items-end gap-4 self-start md:self-auto"
            >
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 1.2, delay: 0.2 }}
                className="font-mono text-[9px] md:text-[10px] font-medium uppercase tracking-[0.4em] text-slate"
              >
                An AI memory for music makers
              </motion.p>
              <button
                onClick={() => signInWithGoogle()}
                className="group flex items-center gap-3 text-[12px] font-mono uppercase tracking-[0.2em] text-obsidian cursor-pointer"
              >
                <motion.span
                  className="block w-12 h-[1px] bg-obsidian"
                  whileHover={{ width: 80 }}
                  transition={{ type: "spring", stiffness: 200, damping: 20 }}
                />
                Begin
              </button>
            </motion.div>
          </div>
        </motion.div>

        {/* Scroll line */}
        <div className="absolute bottom-0 left-12 w-[1px] h-24 overflow-hidden hidden md:block">
          <motion.div
            animate={{ y: ["-100%", "100%"] }}
            transition={{ duration: 2, ease: "easeInOut", repeat: Infinity }}
            className="w-full h-full bg-gradient-to-b from-sky-mint to-transparent"
          />
        </div>
      </section>

      {/* ═════════════════════════════════════════════════════════════
          MARQUEE DIVIDER — kinetic energy
          ═════════════════════════════════════════════════════════════ */}
      <div className="py-6 border-y border-chalk/60">
        <Marquee
          text="CAPTURE · REMEMBER · CONNECT · DISCOVER · CREATE"
          className="font-mono text-[10px] tracking-[0.4em] text-fog"
        />
      </div>

      {/* ═════════════════════════════════════════════════════════════
          PHILOSOPHY — editorial 12-col asymmetry
          ═════════════════════════════════════════════════════════════ */}
      <section className="py-32 md:py-48 px-6 md:px-12">
        <div className="max-w-[1300px] mx-auto grid md:grid-cols-12 gap-8 md:gap-4 items-start">
          {/* Oversized editorial number */}
          <div className="md:col-span-3 relative">
            <Reveal>
              <span
                className="font-heading font-light text-[120px] md:text-[180px] leading-none tracking-tight select-none block"
                style={{ color: "rgba(207,218,245,0.25)" }}
              >
                01
              </span>
              <p className="font-mono text-[9px] uppercase tracking-[0.4em] text-slate mt-4 ml-2">
                The problem
              </p>
            </Reveal>
          </div>

          {/* Text — offset from top */}
          <Reveal className="md:col-span-7 md:col-start-5 md:pt-20" delay={0.15}>
            <h2
              className="font-heading font-light text-obsidian tracking-tight leading-[1.2] mb-8"
              style={{ fontSize: "clamp(2rem, 4vw, 2.4rem)" }}
            >
              Inspiration doesn&apos;t wait<br />
              <span className="italic text-gravel/70">for the studio</span>
            </h2>
            <div
              className="w-16 h-[1px] mb-8"
              style={{ background: "linear-gradient(to right, #a0b5eb, transparent)" }}
            />
            <p className="text-[14px] text-gravel leading-[2] max-w-[480px]">
              Most songs die as voice memos. The creator forgets the feeling.
              The context fades. A verse that belonged with a chorus
              recorded three weeks apart never finds its other half.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ═════════════════════════════════════════════════════════════
          THREE PILLARS — overlapping collage, not a neat 3-col grid
          ═════════════════════════════════════════════════════════════ */}
      <section id="how" className="py-20 md:py-32 relative">
        {/* Atmosphere wash */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "linear-gradient(180deg, transparent 0%, rgba(207,218,245,0.08) 30%, rgba(255,148,115,0.04) 70%, transparent 100%)",
          }}
        />

        <div className="relative z-10 max-w-[1300px] mx-auto px-6 md:px-12">
          <Reveal className="mb-16 md:mb-24">
            <p className="font-mono text-[9px] uppercase tracking-[0.5em] text-slate">
              How it works
            </p>
          </Reveal>

          {/* Cards — stacked on mobile, overlapping collage on desktop via CSS */}
          <div className="relative md:min-h-[520px] flex flex-col md:block gap-6">
            {/* Card 1 — Capture, top-left, tilted */}
            <Reveal delay={0} direction="left" className="relative md:absolute md:left-0 md:top-0 md:w-[380px] z-10">
              <motion.div
                whileHover={{ y: -8, rotate: 0, transition: { type: "spring", stiffness: 200, damping: 18 } }}
                className="rounded-[20px] p-8 md:p-10 relative overflow-hidden cursor-default"
                style={{
                  background: "linear-gradient(150deg, rgba(207,218,245,0.4) 0%, rgba(207,218,245,0.08) 100%)",
                  rotate: -1.5,
                }}
              >
                <span className="absolute top-4 right-5 font-mono text-[10px]" style={{ color: "rgba(160,181,235,0.5)" }}>01</span>
                <h3 className="font-heading font-light text-[32px] md:text-[40px] leading-[1] tracking-tight text-obsidian mb-5">Capture</h3>
                <p className="text-[13px] text-gravel leading-[1.9] max-w-[280px]">Record a melody. Type a lyric. Drop a voice memo. The moment is safe before the thought dissolves.</p>
                <div className="mt-8 h-8 flex items-end">
                  {[12, 20, 8, 28, 16, 10, 24, 6, 18, 14, 22, 10, 26, 8, 16, 20, 12, 24, 8, 18].map((h, j) => (
                    <motion.div
                      key={j}
                      className="w-[2px] rounded-full mr-[3px]"
                      animate={{ scaleY: [1, 0.4, 1] }}
                      transition={{ duration: 1.5, delay: j * 0.08, repeat: Infinity, ease: "easeInOut" }}
                      style={{ height: `${h}px`, background: `rgba(160,181,235,${0.2 + (j % 3) * 0.1})`, transformOrigin: "bottom" }}
                    />
                  ))}
                </div>
              </motion.div>
            </Reveal>

            {/* Card 2 — Connect, center-offset, overlapping */}
            <Reveal delay={0.15} className="relative md:absolute md:left-[32%] md:top-[70px] md:w-[380px] z-20">
              <motion.div
                whileHover={{ y: -8, rotate: 0, transition: { type: "spring", stiffness: 200, damping: 18 } }}
                className="rounded-[20px] p-8 md:p-10 relative overflow-hidden cursor-default"
                style={{
                  background: "linear-gradient(150deg, rgba(255,200,170,0.4) 0%, rgba(255,148,115,0.08) 100%)",
                  rotate: 0.8,
                  boxShadow: "0 8px 32px rgba(0,0,0,0.04)",
                }}
              >
                <span className="absolute top-4 right-5 font-mono text-[10px]" style={{ color: "rgba(255,148,115,0.5)" }}>02</span>
                <h3 className="font-heading font-light text-[32px] md:text-[40px] leading-[1] tracking-tight text-obsidian mb-5">Connect</h3>
                <p className="text-[13px] text-gravel leading-[1.9] max-w-[280px]">A verse from Tuesday shares emotional DNA with a hook from last month. AI finds what your memory missed.</p>
                <div className="mt-8 h-8 flex items-center">
                  <div className="w-3 h-3 rounded-full border" style={{ background: "rgba(255,148,115,0.3)", borderColor: "rgba(255,148,115,0.4)" }} />
                  <div className="flex-1 h-[1px] mx-2" style={{ background: "linear-gradient(90deg, rgba(255,148,115,0.4), rgba(226,193,97,0.3))" }} />
                  <div className="w-3 h-3 rounded-full border" style={{ background: "rgba(226,193,97,0.3)", borderColor: "rgba(226,193,97,0.4)" }} />
                  <div className="flex-1 h-[1px] mx-2" style={{ background: "linear-gradient(90deg, rgba(226,193,97,0.3), rgba(160,181,235,0.3))" }} />
                  <div className="w-3 h-3 rounded-full border" style={{ background: "rgba(160,181,235,0.3)", borderColor: "rgba(160,181,235,0.4)" }} />
                </div>
              </motion.div>
            </Reveal>

            {/* Card 3 — Discover, right side, lower */}
            <Reveal delay={0.3} direction="right" className="relative md:absolute md:right-0 md:top-[140px] md:w-[380px] z-10">
              <motion.div
                whileHover={{ y: -8, rotate: 0, transition: { type: "spring", stiffness: 200, damping: 18 } }}
                className="rounded-[20px] p-8 md:p-10 relative overflow-hidden cursor-default"
                style={{
                  background: "linear-gradient(150deg, rgba(226,193,97,0.3) 0%, rgba(240,210,140,0.06) 100%)",
                  rotate: -0.6,
                }}
              >
                <span className="absolute top-4 right-5 font-mono text-[10px]" style={{ color: "rgba(226,193,97,0.5)" }}>03</span>
                <h3 className="font-heading font-light text-[32px] md:text-[40px] leading-[1] tracking-tight text-obsidian mb-5">Discover</h3>
                <p className="text-[13px] text-gravel leading-[1.9] max-w-[280px]">See your artistic identity in data. Emotional patterns, creative rhythms, and dormant projects — surfaced.</p>
                <div className="mt-8 h-8 flex items-end">
                  {[0.3, 0.7, 0.5, 0.9, 0.4, 0.6, 0.8].map((h, j) => (
                    <div key={j} className="w-4 rounded-sm mr-2" style={{ height: `${h * 32}px`, background: `rgba(226,193,97,${0.15 + h * 0.25})` }} />
                  ))}
                </div>
              </motion.div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ═════════════════════════════════════════════════════════════
          FRAGMENT SHOWCASE — floating UI pieces + oversized "AI"
          ═════════════════════════════════════════════════════════════ */}
      <section className="py-32 md:py-48 px-6 md:px-12 relative overflow-hidden">
        <div className="max-w-[1300px] mx-auto grid md:grid-cols-12 gap-8 items-center">
          {/* Text side */}
          <div className="md:col-span-5 relative">
            {/* Oversized "AI" ghost text */}
            <Reveal direction="left" className="absolute -top-16 -left-4">
              <span
                className="font-heading font-light text-[180px] md:text-[260px] leading-none select-none pointer-events-none"
                style={{ color: "rgba(255,148,115,0.05)" }}
              >
                AI
              </span>
            </Reveal>

            <Reveal delay={0.15} className="relative z-10">
              <p className="font-mono text-[9px] uppercase tracking-[0.5em] text-slate mb-6">
                Intelligent memory
              </p>
              <h2
                className="font-heading font-light text-obsidian tracking-tight leading-[1.15] mb-6"
                style={{ fontSize: "clamp(2rem, 3.5vw, 2.8rem)" }}
              >
                Every fragment<br />
                has a <span className="italic text-gravel/70">fingerprint</span>
              </h2>
              <p className="text-[14px] text-gravel leading-[2] max-w-[380px]">
                Emotion. Key. Tempo. Theme. Each idea gets a complete profile the moment
                you capture it. When two fragments resonate, the system surfaces the connection.
              </p>
            </Reveal>
          </div>

          {/* Floating mock cards — tilted collage */}
          <div className="md:col-span-6 md:col-start-7 relative min-h-[380px] md:min-h-[420px]">
            <Reveal delay={0.3}>
              <motion.div
                className="absolute top-0 left-0 md:left-8 w-[270px] md:w-[300px]"
                style={{ rotate: -2 }}
                whileHover={{ rotate: 0, scale: 1.03 }}
                transition={{ type: "spring", stiffness: 200, damping: 18 }}
              >
                <div className="bg-white rounded-[16px] p-5 shadow-hairline">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(160,181,235,0.15)", color: "#7b8fc4" }}>melancholy</span>
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(255,148,115,0.15)", color: "#d97b5a" }}>Am</span>
                  </div>
                  <p className="text-[13px] text-obsidian leading-snug mb-3">Rain on empty streets at 2 AM, neon reflections...</p>
                  <div className="flex items-center gap-1 opacity-40">
                    {[4, 8, 6, 12, 5, 9, 7, 3, 10, 6, 8, 4].map((h, j) => (
                      <div key={j} className="w-[2px] rounded-full bg-obsidian" style={{ height: `${h}px` }} />
                    ))}
                  </div>
                </div>
              </motion.div>
            </Reveal>

            <Reveal delay={0.5}>
              <motion.div
                className="absolute top-[170px] left-[40px] md:left-[100px] w-[270px] md:w-[300px] z-10"
                style={{ rotate: 1.5 }}
                whileHover={{ rotate: 0, scale: 1.03 }}
                transition={{ type: "spring", stiffness: 200, damping: 18 }}
              >
                <div className="bg-white rounded-[16px] p-5" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(226,193,97,0.15)", color: "#b89540" }}>nostalgia</span>
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(160,181,235,0.15)", color: "#7b8fc4" }}>72 bpm</span>
                  </div>
                  <p className="text-[13px] text-obsidian leading-snug">We used to drive with the windows down...</p>
                </div>
              </motion.div>
            </Reveal>

            {/* Connection line between cards */}
            <Reveal delay={0.7}>
              <div
                className="absolute top-[140px] left-[65px] md:left-[130px] w-[2px] h-[35px] z-20"
                style={{ background: "linear-gradient(180deg, rgba(160,181,235,0.5), rgba(255,148,115,0.3))" }}
              />
            </Reveal>

            <Reveal delay={0.8}>
              <div className="absolute top-[310px] left-[20px] md:left-[60px]">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white shadow-hairline">
                  <div className="w-1.5 h-1.5 rounded-full bg-sky-mint" />
                  <span className="font-mono text-[10px] text-gravel">2 fragments connected</span>
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ═════════════════════════════════════════════════════════════
          FEATURES — magazine-style list with sideways label
          ═════════════════════════════════════════════════════════════ */}
      <section className="py-32 md:py-44 px-6 md:px-12">
        <div className="max-w-[1300px] mx-auto grid md:grid-cols-12 gap-8">
          {/* Rotated sideways label */}
          <div className="md:col-span-2 relative hidden md:block">
            <span
              className="font-mono text-[9px] uppercase tracking-[0.5em] text-slate origin-bottom-left whitespace-nowrap absolute top-0 left-5"
              style={{ transform: "rotate(-90deg) translateX(-100%)" }}
            >
              Core capabilities
            </span>
          </div>

          <div className="md:col-span-8 md:col-start-4">
            {[
              { title: "Emotion Detection", detail: "22 musical emotions mapped in real-time using AI analysis", color: "#a0b5eb" },
              { title: "Vector Memory", detail: "Semantic search finds connections your memory missed", color: "#ffa773" },
              { title: "Auto-Grouping", detail: "Related fragments form projects automatically across time", color: "#e2c161" },
              { title: "Creative DNA", detail: "Your artistic patterns visualized — emotions, themes, rhythms", color: "#8fa3d0" },
              { title: "Rescue Score", detail: "Forgotten ideas resurfaced before they disappear forever", color: "#ff9473" },
            ].map((f, i) => (
              <Reveal key={f.title} delay={i * 0.08}>
                <div className="group flex items-start gap-6 py-7 border-b border-chalk/50 cursor-default">
                  <motion.div
                    className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
                    style={{ background: f.color }}
                    whileHover={{ scale: 2.5 }}
                    transition={{ type: "spring", stiffness: 300, damping: 15 }}
                  />
                  <div className="flex-1">
                    <div className="flex items-baseline justify-between gap-4">
                      <h4 className="text-[16px] md:text-[18px] font-medium tracking-tight">{f.title}</h4>
                      <span className="font-mono text-[10px] text-fog opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                        0{i + 1}
                      </span>
                    </div>
                    <p className="text-[13px] text-gravel leading-[1.8] mt-1 max-w-[400px]">{f.detail}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═════════════════════════════════════════════════════════════
          QUOTE — cinematic full-bleed typography
          ═════════════════════════════════════════════════════════════ */}
      <section className="py-40 md:py-56 relative overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: "radial-gradient(ellipse 100% 60% at 50% 50%, rgba(207,218,245,0.1), transparent 70%)" }}
        />
        <Reveal className="max-w-[900px] mx-auto px-6 md:px-12 text-center relative z-10">
          <blockquote
            className="font-heading font-light italic text-obsidian tracking-tight leading-[1.3]"
            style={{ fontSize: "clamp(1.8rem, 4.5vw, 3.5rem)" }}
          >
            &ldquo;The best song you&apos;ll ever write is already inside you
            <span className="text-gravel/60"> — scattered across a hundred quiet moments.</span>&rdquo;
          </blockquote>
        </Reveal>
      </section>

      {/* ═════════════════════════════════════════════════════════════
          CTA — horizon line + cinematic ending
          ═════════════════════════════════════════════════════════════ */}
      <section className="py-32 md:py-44 relative overflow-hidden">
        {/* Gradient horizon */}
        <div
          className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-[1px]"
          style={{ background: "linear-gradient(90deg, transparent 5%, rgba(160,181,235,0.5) 20%, rgba(255,148,115,0.4) 50%, rgba(226,193,97,0.3) 80%, transparent 95%)" }}
        />
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[300px] rounded-full pointer-events-none"
          style={{ background: "radial-gradient(ellipse, rgba(160,181,235,0.08) 0%, transparent 70%)" }}
        />

        <Reveal className="relative z-10 text-center px-6">
          <p className="font-mono text-[9px] uppercase tracking-[0.5em] text-slate mb-8">
            Ready?
          </p>
          <h2
            className="font-heading font-light text-obsidian tracking-tight leading-[1.1] mb-14"
            style={{ fontSize: "clamp(2.8rem, 7vw, 5.5rem)" }}
          >
            The song is waiting.
          </h2>
          <motion.button
            onClick={() => signInWithGoogle()}
            whileHover={{ scale: 1.04, boxShadow: "0 0 40px rgba(160,181,235,0.3), 0 0 80px rgba(255,148,115,0.15)" }}
            whileTap={{ scale: 0.97 }}
            className="relative inline-flex items-center gap-3 bg-obsidian text-white font-mono text-[12px] uppercase tracking-[0.2em] px-10 py-5 rounded-full overflow-hidden group cursor-pointer"
          >
            <span className="relative z-10">Begin capturing</span>
            <span className="relative z-10 transition-transform duration-500 group-hover:translate-x-1">&rarr;</span>
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700"
              style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.2), rgba(255,148,115,0.15), rgba(226,193,97,0.1))" }}
            />
          </motion.button>
        </Reveal>
      </section>

      {/* ═════════════════════════════════════════════════════════════
          FOOTER — minimal, asymmetric
          ═════════════════════════════════════════════════════════════ */}
      <footer className="py-12 md:py-16 px-6 md:px-12 border-t border-chalk/40">
        <div className="max-w-[1300px] mx-auto flex flex-col md:flex-row items-start md:items-end justify-between gap-4">
          <div>
            <span className="font-heading font-light text-[20px] tracking-tight text-obsidian/30 block mb-1">
              Pocket Producer
            </span>
            <span className="font-mono text-[9px] text-fog tracking-[0.2em]">
              An AI memory for music makers
            </span>
          </div>
          <span className="font-mono text-[9px] text-fog tracking-wider">
            Built with Gemini on Google Cloud
          </span>
        </div>
      </footer>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   CAPTURE DASHBOARD (logged in state) — kept consistent with inner pages
   ═══════════════════════════════════════════════════════════════════════ */
function CaptureDashboard() {
  const { user } = useAuth();
  const { fragments, loading, refresh } = useFragments();
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const stuckCount = fragments.filter(
    (f) => f.status === "processing" && f.tags && f.tags.length > 0
  ).length;

  const handleFixStuck = useCallback(async () => {
    try {
      await apiPost("/fix-stuck", {});
      refresh();
    } catch {}
  }, [refresh]);


  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 6) return "Late night session";
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  })();

  const firstName = user?.displayName?.split(" ")[0] ?? "";

  const handleRecorded = useCallback(
    async (blob: Blob) => {
      setSubmitting(true);
      setStatus("Processing audio...");
      try {
        const form = new FormData();
        const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
        form.append("file", blob, `recording.${ext}`);
        await apiPost("/ingest", form);
        setStatus("Saved!");
        refresh();
      } catch (e) {
        setStatus(e instanceof Error ? e.message : "Processing failed");
      } finally {
        setSubmitting(false);
        setTimeout(() => setStatus(null), 3000);
      }
    },
    [refresh],
  );

  const handleFile = useCallback(
    async (file: File) => {
      setSubmitting(true);
      setStatus("Uploading...");
      try {
        const form = new FormData();
        form.append("file", file);
        await apiPost("/ingest", form);
        setStatus("Saved!");
        refresh();
      } catch (e) {
        setStatus(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setSubmitting(false);
        setTimeout(() => setStatus(null), 3000);
      }
    },
    [refresh],
  );

  async function submitText() {
    if (!text.trim() || submitting) return;
    setSubmitting(true);
    setStatus("Processing...");
    try {
      const form = new FormData();
      form.append("text", text.trim());
      await apiPost("/ingest", form);
      setText("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "20px";
        textareaRef.current.style.overflowY = "hidden";
      }
      setStatus("Saved!");
      refresh();
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
      setTimeout(() => setStatus(null), 3000);
    }
  }

  return (
    <div className="relative min-h-[calc(100vh-56px)]">
      <div className="ambient-mesh" />
      <div className="relative z-10 max-w-[1100px] mx-auto px-6 py-10 animate-page-enter">
        <div className="flex flex-col lg:flex-row gap-8 lg:gap-10">
          <div className="lg:w-[340px] flex-shrink-0">
            <div className="lg:sticky lg:top-20 space-y-6">
              <div className="space-y-1">
                <p className="font-mono text-[10px] font-medium uppercase tracking-[0.3em] text-slate">
                  {greeting}{firstName ? `, ${firstName}` : ""}
                </p>
                <h1 className="font-heading text-3xl font-light text-obsidian tracking-tight leading-[1.08]">
                  Capture a moment
                </h1>
              </div>
              <div className="flex flex-col items-center py-4">
                <div className="relative">
                  <div
                    className="absolute inset-0 -m-10 rounded-full opacity-40 pointer-events-none"
                    style={{
                      background: "radial-gradient(circle, rgba(160,181,235,0.18) 0%, rgba(226,193,97,0.06) 50%, transparent 70%)",
                      filter: "blur(24px)",
                    }}
                  />
                  <AudioRecorder onRecorded={handleRecorded} />
                </div>
              </div>
              <AnimatePresence>
                {status && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, filter: "blur(4px)" }}
                    animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                    exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
                    transition={{ type: "spring", stiffness: 200, damping: 20 }}
                    className="flex items-center justify-center gap-2 text-sm text-gravel"
                  >
                    {submitting && <Loader2 size={14} className="animate-spin" />}
                    {status}
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="flex items-center gap-2 bg-white rounded-2xl px-5 py-3 shadow-hairline gradient-border">
                <textarea
                  ref={textareaRef}
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    const el = e.target;
                    el.style.height = "0";
                    el.style.height = `${el.scrollHeight}px`;
                    el.style.overflowY = el.scrollHeight > 200 ? "auto" : "hidden";
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      submitText();
                    }
                  }}
                  placeholder="Type a lyric, idea, or note..."
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-obsidian placeholder:text-slate outline-none resize-none leading-5 max-h-[200px]"
                  style={{ height: "20px", overflowY: "hidden" }}
                  disabled={submitting}
                />
                <button
                  onClick={submitText}
                  disabled={!text.trim() || submitting}
                  className="p-2 rounded-full hover:bg-powder cursor-pointer transition-colors disabled:opacity-30 btn-press flex-shrink-0"
                  aria-label="Send"
                >
                  <Send size={16} className="text-gravel" />
                </button>
              </div>
              <FileDropzone onFile={handleFile} />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            {!loading && fragments.length > 0 && (
              <div className="space-y-5 pb-12">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                    Your fragments
                  </span>
                  <div className="flex-1 h-px bg-gradient-to-r from-chalk to-transparent" />
                  <span
                    className="font-mono text-[11px] text-gravel px-2.5 py-0.5 rounded-full"
                    style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.15), rgba(226,193,97,0.1))" }}
                  >
                    {fragments.length}
                  </span>
                </div>
                {stuckCount > 0 && (
                  <button
                    onClick={handleFixStuck}
                    className="text-xs text-gravel hover:text-obsidian transition-colors"
                  >
                    {stuckCount} fragment{stuckCount > 1 ? "s" : ""} stuck processing —{" "}
                    <span className="underline">fix now</span>
                  </button>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
                  <AnimatePresence mode="popLayout">
                    {fragments.map((f, i) => (
                      <motion.div
                        key={f._id}
                        layout
                        initial={{ opacity: 0, y: 24, scale: 0.96, filter: "blur(4px)" }}
                        animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
                        exit={{ opacity: 0, scale: 0.94, filter: "blur(4px)" }}
                        transition={{ type: "spring", stiffness: 200, damping: 22, delay: i * 0.05 }}
                      >
                        <FragmentCard fragment={f} onDeleted={refresh} onUpdated={refresh} />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            )}
            {!loading && fragments.length === 0 && (
              <div className="flex flex-col items-center justify-center py-24 space-y-4 animate-fade-in">
                <div
                  className="w-24 h-24 rounded-full opacity-50 morph-blob"
                  style={{ background: "linear-gradient(135deg, rgba(160,181,235,0.4), rgba(226,193,97,0.2))" }}
                />
                <p className="text-sm text-gravel text-center">Record, type, or upload your first musical idea</p>
                <p className="text-xs text-slate text-center max-w-[280px]">
                  Fragments appear here as a masonry grid once you start capturing
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   PAGE ROUTER
   ═══════════════════════════════════════════════════════════════════════ */
export default function HomePage() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <LandingPage />;
  return <CaptureDashboard />;
}
