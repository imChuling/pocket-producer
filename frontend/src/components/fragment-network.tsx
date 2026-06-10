"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { NetworkData } from "@/types";

const NODE_COLORS: Record<string, string> = {
  audio: "#a0b5eb",
  text: "#e2c161",
};

const EMOTION_ACCENTS = [
  "#6b85c2", "#ffa773", "#d4855a", "#8fa3d0", "#c4a44e", "#b8c8e8",
];

interface SimNode {
  id: string;
  title: string;
  type: "audio" | "text";
  emotions: string[];
  projectId?: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

interface SimEdge {
  source: string;
  target: string;
  projectTitle: string;
}

export function FragmentNetwork() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<NetworkData | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const hoveredRef = useRef<string | null>(null);

  useEffect(() => {
    apiFetch<NetworkData>("/dna/network")
      .then(setData)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || !data || data.nodes.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = 150;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const cx = w / 2;
    const cy = h / 2 + 20;

    const edgeLookup = new Map<string, number>();
    for (const e of data.edges) {
      edgeLookup.set(e.source, (edgeLookup.get(e.source) ?? 0) + 1);
      edgeLookup.set(e.target, (edgeLookup.get(e.target) ?? 0) + 1);
    }

    const nodes: SimNode[] = data.nodes.map((n, i) => {
      const angle = (i / data.nodes.length) * Math.PI * 2;
      const spread = Math.min(w, h) * 0.35;
      return {
        id: n.id,
        title: n.title,
        type: n.type,
        emotions: n.emotions,
        projectId: n.project_id,
        x: cx + Math.cos(angle) * spread * (0.5 + Math.random() * 0.5),
        y: cy + Math.sin(angle) * spread * (0.5 + Math.random() * 0.5),
        vx: 0,
        vy: 0,
        radius: 4 + Math.min((edgeLookup.get(n.id) ?? 0) * 1.5, 10),
      };
    });

    const edges: SimEdge[] = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      projectTitle: e.project_title,
    }));

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    const projectColors = new Map<string, string>();
    let colorIdx = 0;
    for (const e of data.edges) {
      if (!projectColors.has(e.project_id)) {
        projectColors.set(e.project_id, EMOTION_ACCENTS[colorIdx % EMOTION_ACCENTS.length]);
        colorIdx++;
      }
    }

    let frame = 0;
    let rafId = 0;
    const totalFrames = 200;

    function simulate() {
      const alpha = Math.max(0.01, 1 - frame / totalFrames);

      for (const node of nodes) {
        const dx = cx - node.x;
        const dy = cy - node.y;
        node.vx += dx * 0.0003 * alpha;
        node.vy += dy * 0.0003 * alpha;
      }

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const minDist = (a.radius + b.radius) * 3;
          if (dist < minDist) {
            const force = ((minDist - dist) / dist) * 0.05 * alpha;
            dx *= force;
            dy *= force;
            a.vx -= dx;
            a.vy -= dy;
            b.vx += dx;
            b.vy += dy;
          }
        }
      }

      for (const edge of edges) {
        const a = nodeMap.get(edge.source);
        const b = nodeMap.get(edge.target);
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const targetDist = 60;
        const force = ((dist - targetDist) / dist) * 0.02 * alpha;
        a.vx += dx * force;
        a.vy += dy * force;
        b.vx -= dx * force;
        b.vy -= dy * force;
      }

      for (const node of nodes) {
        node.vx *= 0.85;
        node.vy *= 0.85;
        node.x += node.vx;
        node.y += node.vy;
        node.x = Math.max(node.radius, Math.min(w - node.radius, node.x));
        node.y = Math.max(node.radius + 16, Math.min(h - node.radius, node.y));
      }
    }

    function draw() {
      frame++;
      if (frame <= totalFrames) simulate();

      ctx!.clearRect(0, 0, w, h);

      const drawT = Math.min(frame / 40, 1);

      for (const edge of edges) {
        const a = nodeMap.get(edge.source);
        const b = nodeMap.get(edge.target);
        if (!a || !b) continue;
        ctx!.beginPath();
        ctx!.moveTo(a.x, a.y);
        ctx!.lineTo(
          a.x + (b.x - a.x) * drawT,
          a.y + (b.y - a.y) * drawT,
        );
        const isHovered =
          hoveredRef.current === a.id || hoveredRef.current === b.id;
        ctx!.strokeStyle = isHovered
          ? "rgba(107,133,194,0.4)"
          : "rgba(160,181,235,0.15)";
        ctx!.lineWidth = isHovered ? 1.5 : 0.8;
        ctx!.stroke();
      }

      let hoveredNode: SimNode | null = null;
      for (const node of nodes) {
        if (hoveredRef.current === node.id) { hoveredNode = node; continue; }
        const baseColor = NODE_COLORS[node.type] || "#a0b5eb";
        ctx!.beginPath();
        ctx!.arc(node.x, node.y, node.radius * drawT, 0, Math.PI * 2);
        ctx!.fillStyle = baseColor + "88";
        ctx!.fill();
        ctx!.strokeStyle = "white";
        ctx!.lineWidth = 1.2;
        ctx!.stroke();
      }

      if (hoveredNode) {
        const node = hoveredNode;
        const baseColor = NODE_COLORS[node.type] || "#a0b5eb";
        const glow = ctx!.createRadialGradient(
          node.x, node.y, 0,
          node.x, node.y, node.radius * 4,
        );
        glow.addColorStop(0, baseColor + "44");
        glow.addColorStop(1, "transparent");
        ctx!.beginPath();
        ctx!.arc(node.x, node.y, node.radius * 4, 0, Math.PI * 2);
        ctx!.fillStyle = glow;
        ctx!.fill();

        ctx!.beginPath();
        ctx!.arc(node.x, node.y, node.radius * drawT, 0, Math.PI * 2);
        ctx!.fillStyle = baseColor + "cc";
        ctx!.fill();
        ctx!.strokeStyle = "white";
        ctx!.lineWidth = 1.2;
        ctx!.stroke();

        ctx!.font = "10px var(--font-ibm-plex-mono, monospace)";
        ctx!.fillStyle = "#555049";
        ctx!.textAlign = "center";
        const label = node.title.length > 30
          ? node.title.slice(0, 28) + "..."
          : node.title;
        const labelY = node.y - node.radius - 6;
        ctx!.fillText(label, node.x, labelY < 10 ? node.y + node.radius + 14 : labelY);
      }

      rafId = requestAnimationFrame(draw);
    }

    rafId = requestAnimationFrame(draw);

    function handleMouseMove(e: MouseEvent) {
      const rect = canvas!.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      let found: string | null = null;
      for (const node of nodes) {
        const dx = mx - node.x;
        const dy = my - node.y;
        if (dx * dx + dy * dy < (node.radius + 4) ** 2) {
          found = node.id;
          break;
        }
      }
      hoveredRef.current = found;
      setHovered(found);
      canvas!.style.cursor = found ? "pointer" : "default";
    }

    canvas.addEventListener("mousemove", handleMouseMove);

    return () => {
      cancelAnimationFrame(rafId);
      canvas.removeEventListener("mousemove", handleMouseMove);
    };
  }, [data]);

  if (!data || data.nodes.length === 0) return null;

  return (
    <div ref={containerRef} className="space-y-3">
      <canvas ref={canvasRef} className="w-full rounded-2xl" />
      <div className="flex items-center justify-center gap-4 text-[10px] text-gravel font-mono">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: NODE_COLORS.audio }} />
          audio
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: NODE_COLORS.text }} />
          text
        </span>
        <span className="text-slate/50">|</span>
        <span>{data.nodes.length} fragments</span>
        <span>{data.edges.length} connections</span>
      </div>
    </div>
  );
}
