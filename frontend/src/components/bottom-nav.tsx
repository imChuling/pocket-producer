"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Mic, Layers, Dna } from "lucide-react";

const tabs = [
  { href: "/", icon: Mic, label: "Capture" },
  { href: "/projects", icon: Layers, label: "Projects" },
  { href: "/dna", icon: Dna, label: "DNA" },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  if (pathname === "/login") return null;

  return (
    <nav className="fixed bottom-0 inset-x-0 z-50 bg-[#09090B] border-t border-zinc-800/50">
      <div className="max-w-[480px] mx-auto flex items-center justify-around h-16 pb-[env(safe-area-inset-bottom)]">
        {tabs.map(({ href, icon: Icon, label }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className="flex flex-col items-center gap-1 py-2 px-4 cursor-pointer"
              aria-label={label}
            >
              {active && (
                <span className="w-1 h-1 rounded-full bg-zinc-50 mb-0.5" />
              )}
              <Icon
                size={22}
                strokeWidth={active ? 2 : 1.5}
                className={active ? "text-zinc-50" : "text-zinc-600"}
              />
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
