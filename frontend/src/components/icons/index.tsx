import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base(size: number | undefined, props: Omit<IconProps, "size">) {
  const s = size ?? 24;
  return {
    width: s,
    height: s,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export function Mic({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M12 2.5c-1.7.1-2.8 1.3-2.7 3l.2 6.2c.1 1.6 1.4 2.8 3 2.7 1.5-.1 2.6-1.4 2.5-3l-.2-6c-.1-1.7-1.3-2.9-2.8-2.9z" />
      <path d="M17.2 10.5c.3 2.8-1.8 5.4-4.6 5.7-3 .3-5.5-1.7-5.8-4.6" />
      <path d="M12 17.8v3.7" />
      <path d="M8.5 21.5h7.2" />
    </svg>
  );
}

export function Layers({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M2.5 12.3l9-5.2c.3-.2.7-.2 1 0l9 5.1" />
      <path d="M2.5 16.5l9 5.1c.3.2.8.2 1.1 0l8.9-5.2" />
      <path d="M2.5 8.2l9-5c.4-.2.8-.2 1.1 0l8.9 5.1" />
    </svg>
  );
}

export function Dna({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M5 2.5c0 5 3.5 6.8 7 8.5-3.5 1.7-7 3.5-7 8.5" />
      <path d="M19 2.5c0 5-3.5 6.8-7 8.5 3.5 1.7 7 3.5 7 8.5" />
      <path d="M6.5 6.8h11" />
      <path d="M6.5 17.2h11" />
      <path d="M9 12h6" />
    </svg>
  );
}

export function Bell({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M6.2 9.5c-.1-3.2 2.4-5.8 5.5-6 3.2-.2 5.9 2.3 6.1 5.5l.4 4.5c.1.6.4 1.1.8 1.5H5c.5-.4.8-1 .9-1.6l.3-3.9z" />
      <path d="M10 19.5c.2.8.9 1.3 1.8 1.3s1.5-.6 1.6-1.3" />
    </svg>
  );
}

export function Sparkles({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M9.5 2.5l1.2 3.5 3.3 1.2-3.3 1.3-1.2 3.5-1.3-3.5L5 7.2l3.2-1.2z" />
      <path d="M16 12l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2L13 15l2.2-.8z" />
      <path d="M7.5 16l.5 1.5 1.5.5-1.5.5-.5 1.5-.5-1.5L5 18l1.5-.5z" />
    </svg>
  );
}

export function LogOut({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M9 21.5H4.5c-1.1 0-2-.9-2-2v-15c0-1.1.9-2 2-2H9" />
      <path d="M15.5 17.5l5-5.5-5-5.5" />
      <path d="M20.5 12H9" />
    </svg>
  );
}

export function Check({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4.5 12.5l5.2 5 9.8-10.5" />
    </svg>
  );
}

export function ArrowLeft({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M10.5 5.5L3.5 12l7 6.5" />
      <path d="M3.5 12h17" />
    </svg>
  );
}

export function ArrowRight({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M13.5 5.5l7 6.5-7 6.5" />
      <path d="M20.5 12h-17" />
    </svg>
  );
}

export function Link2({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M10 13.5c.8 1 2.2 1.5 3.5 1.2 1.3-.3 2.3-1.2 2.8-2.3l1.8-3.5c.8-1.8 0-3.9-1.8-4.7-1.7-.8-3.8 0-4.6 1.7l-.8 1.6" />
      <path d="M14 10.5c-.8-1-2.2-1.5-3.5-1.2-1.3.3-2.3 1.2-2.8 2.3l-1.8 3.5c-.8 1.8 0 3.9 1.8 4.7 1.7.8 3.8 0 4.6-1.7l.8-1.6" />
    </svg>
  );
}

export function Loader2({ size, className = "", ...props }: IconProps) {
  return (
    <svg {...base(size, props)} className={className}>
      <path d="M12 2.5v4" />
      <path d="M12 17.5v4" opacity={0.3} />
      <path d="M4.9 4.9l2.8 2.8" opacity={0.8} />
      <path d="M16.3 16.3l2.8 2.8" opacity={0.2} />
      <path d="M2.5 12h4" opacity={0.6} />
      <path d="M17.5 12h4" opacity={0.15} />
      <path d="M4.9 19.1l2.8-2.8" opacity={0.4} />
      <path d="M16.3 7.7l2.8-2.8" opacity={0.9} />
    </svg>
  );
}

export function Plus({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M12 4.5v15" />
      <path d="M4.5 12h15" />
    </svg>
  );
}

export function RefreshCw({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M20.5 4.5v5h-5" />
      <path d="M3.5 19.5v-5h5" />
      <path d="M20 9.5c-1-3.3-4.2-5.5-7.8-5.2-3 .3-5.5 2.5-6.2 5.3" />
      <path d="M4 14.5c1 3.3 4.2 5.5 7.8 5.2 3-.3 5.5-2.5 6.2-5.3" />
    </svg>
  );
}

export function Trash2({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4 6.5h16" />
      <path d="M8.5 6.5v-2c0-.6.4-1 1-1h5c.6 0 1 .4 1 1v2" />
      <path d="M5.5 6.5l1 14c.1.6.5 1 1.1 1h8.8c.6 0 1-.4 1.1-1l1-14" />
      <path d="M10 10.5v6" />
      <path d="M14 10.5v6" />
    </svg>
  );
}

export function Pencil({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M16.5 3.5l4 4-12 12H4.5v-4z" />
      <path d="M13.5 6.5l4 4" />
    </svg>
  );
}

export function X({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M5.5 5.5l13 13" />
      <path d="M18.5 5.5l-13 13" />
    </svg>
  );
}

export function Play({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M6.5 3.5v17l13-8.5z" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function Pause({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M7 4.5h2.5v15H7z" fill="currentColor" stroke="none" />
      <path d="M14.5 4.5H17v15h-2.5z" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function Upload({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M12 15.5V3.5" />
      <path d="M7.5 8l4.5-4.5L16.5 8" />
      <path d="M20.5 15.5v3c0 1.1-.9 2-2 2h-13c-1.1 0-2-.9-2-2v-3" />
    </svg>
  );
}

export function Send({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M3 3.5l18.5 8.5L3 20.5v-7l13-1.5-13-1.5z" />
    </svg>
  );
}

export function Music2({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M9 17.5a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
      <path d="M9 14.5V3.5l11-2v11" />
      <path d="M20 15.5a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
    </svg>
  );
}

export function Clock({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 6.5v6l3.5 2" />
    </svg>
  );
}

export function Flame({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M12 2.5c-2 3-6 5.5-6 10 0 3.3 2.7 6 6 6s6-2.7 6-6c0-4.5-4-7-6-10z" />
      <path d="M12 18.5c-1.1 0-2-.9-2-2 0-2 2-3.5 2-3.5s2 1.5 2 3.5c0 1.1-.9 2-2 2z" />
    </svg>
  );
}

export function History({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M3.5 12c0-4.7 3.8-8.5 8.5-8.5s8.5 3.8 8.5 8.5-3.8 8.5-8.5 8.5c-3 0-5.7-1.6-7.2-4" />
      <path d="M3.5 6.5v5.5H9" />
      <path d="M12 7.5v5l3 2" />
    </svg>
  );
}

export function SkipForward({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4.5 4.5l10 7.5-10 7.5z" fill="currentColor" stroke="none" />
      <path d="M18.5 4.5v15" />
    </svg>
  );
}

export function UserPen({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="10" cy="7.5" r="4" />
      <path d="M3.5 20.5c0-3.6 2.9-6.5 6.5-6.5 1.2 0 2.4.3 3.3.9" />
      <path d="M17 15l3.5 3.5-2 2L15 17z" />
    </svg>
  );
}

export function FileText({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M14 2.5H6.5c-1.1 0-2 .9-2 2v15c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V8z" />
      <path d="M14 2.5v5.5h5.5" />
      <path d="M8.5 13.5h7" />
      <path d="M8.5 17h4.5" />
    </svg>
  );
}

export function Lightbulb({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M9 21.5h6" />
      <path d="M12 2.5c-3.5.1-6.2 3-6 6.5.1 2.3 1.4 4.2 3.2 5.3.5.3.8.9.8 1.5v1.2h4v-1.2c0-.6.3-1.2.8-1.5 1.8-1.1 3-3 3.2-5.3.2-3.5-2.5-6.4-6-6.5z" />
      <path d="M9.5 17.5h5" />
    </svg>
  );
}

export function GitMerge({ size, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="6.5" cy="6" r="3" />
      <circle cx="17.5" cy="12" r="3" />
      <circle cx="6.5" cy="18" r="3" />
      <path d="M6.5 9v6" />
      <path d="M6.5 9c0 3 2.5 5.5 8 3" />
    </svg>
  );
}

export { X as XIcon };
