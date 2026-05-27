"use client";

import { useEffect, useRef } from "react";

/**
 * Ambient floating particles + gradient mesh background for app pages.
 * Renders a subtle, artistic atmosphere behind content.
 */
export function AmbientBackground({ variant = "default" }: { variant?: "default" | "warm" | "cool" }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) return;

    const dpr = window.devicePixelRatio || 1;

    function resize() {
      canvas!.width = window.innerWidth * dpr;
      canvas!.height = window.innerHeight * dpr;
      canvas!.style.width = `${window.innerWidth}px`;
      canvas!.style.height = `${window.innerHeight}px`;
      ctx!.scale(dpr, dpr);
    }
    resize();
    window.addEventListener("resize", resize);

    // Floating particles
    const colors =
      variant === "warm"
        ? ["rgba(255,148,115,0.3)", "rgba(226,193,97,0.25)", "rgba(255,167,115,0.2)"]
        : variant === "cool"
          ? ["rgba(160,181,235,0.3)", "rgba(167,252,205,0.2)", "rgba(160,181,235,0.15)"]
          : ["rgba(160,181,235,0.25)", "rgba(255,148,115,0.15)", "rgba(226,193,97,0.15)"];

    const particles = Array.from({ length: 18 }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      size: Math.random() * 3 + 1.5,
      speedX: (Math.random() - 0.5) * 0.15,
      speedY: (Math.random() - 0.5) * 0.12,
      color: colors[Math.floor(Math.random() * colors.length)],
      phase: Math.random() * Math.PI * 2,
    }));

    let frame = 0;
    let rafId = 0;

    function draw() {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx!.clearRect(0, 0, w, h);

      particles.forEach((p) => {
        p.x += p.speedX + Math.sin(frame * 0.003 + p.phase) * 0.1;
        p.y += p.speedY + Math.cos(frame * 0.002 + p.phase) * 0.08;

        // Wrap around
        if (p.x < -20) p.x = w + 20;
        if (p.x > w + 20) p.x = -20;
        if (p.y < -20) p.y = h + 20;
        if (p.y > h + 20) p.y = -20;

        const pulse = Math.sin(frame * 0.008 + p.phase) * 0.5 + 0.5;
        const radius = p.size + pulse * 1.5;

        ctx!.beginPath();
        ctx!.arc(p.x, p.y, radius, 0, Math.PI * 2);
        ctx!.fillStyle = p.color;
        ctx!.fill();

        // Soft glow around each particle
        const glow = ctx!.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius * 6);
        glow.addColorStop(0, p.color.replace(/[\d.]+\)$/, `${0.06 * pulse})`));
        glow.addColorStop(1, "transparent");
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, radius * 6, 0, Math.PI * 2);
        ctx!.fillStyle = glow;
        ctx!.fill();
      });

      frame++;
      rafId = requestAnimationFrame(draw);
    }

    rafId = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resize);
    };
  }, [variant]);

  return (
    <>
      {/* CSS gradient mesh */}
      <div className="ambient-mesh" />
      {/* Canvas particles */}
      <canvas
        ref={canvasRef}
        className="fixed inset-0 pointer-events-none z-0"
        style={{ opacity: 0.7 }}
      />
    </>
  );
}
