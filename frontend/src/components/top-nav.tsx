"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useNotifications } from "@/hooks/use-notifications";
import { signOut, signInWithGoogle } from "@/lib/firebase";
import { Mic, Layers, Dna, LogOut, Bell, Sparkles, Check } from "lucide-react";

const navLinks = [
  { href: "/", icon: Mic, label: "Capture" },
  { href: "/projects", icon: Layers, label: "Projects" },
  { href: "/dna", icon: Dna, label: "DNA" },
] as const;

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function TopNav() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close panel on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Close panel on route change
  useEffect(() => {
    const id = window.setTimeout(() => setOpen(false), 0);
    return () => window.clearTimeout(id);
  }, [pathname]);

  // Hide nav on login page
  if (pathname === "/login") return null;

  return (
    <header className="sticky top-0 z-50 bg-[#fdfcfb]/80 backdrop-blur-xl border-b border-chalk/60">
      <div className="flex items-center justify-between h-14 px-6 md:px-10">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 cursor-pointer">
          <span className="font-heading text-xl font-light text-obsidian tracking-tight">
            Pocket Producer
          </span>
        </Link>

        {/* Nav links — only show when logged in */}
        {!loading && user && (
          <nav className="flex items-center gap-1">
            {navLinks.map(({ href, icon: Icon, label }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
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
          </nav>
        )}

        {/* Right side */}
        <div className="flex items-center gap-2">
          {!loading && user ? (
            <>
              {/* Notification bell */}
              <div className="relative" ref={panelRef}>
                <button
                  onClick={() => setOpen((v) => !v)}
                  className="relative p-2 rounded-full text-gravel hover:text-obsidian hover:bg-powder transition-colors cursor-pointer btn-press"
                  aria-label="Notifications"
                >
                  <Bell size={16} />
                  {unreadCount > 0 && (
                    <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-obsidian text-white text-[9px] font-bold flex items-center justify-center leading-none animate-tag-pop">
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                  )}
                </button>

                {/* Dropdown panel */}
                {open && (
                  <div className="absolute right-0 top-full mt-2 w-[340px] bg-white/90 backdrop-blur-xl rounded-[24px] shadow-hairline border border-white/60 overflow-hidden animate-fade-in z-50">
                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-chalk">
                      <span className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate">
                        Notifications
                      </span>
                      {unreadCount > 0 && (
                        <button
                          onClick={markAllRead}
                          className="text-[11px] text-gravel hover:text-obsidian transition-colors cursor-pointer flex items-center gap-1"
                        >
                          <Check size={10} />
                          Mark all read
                        </button>
                      )}
                    </div>

                    {/* List */}
                    <div className="max-h-[360px] overflow-y-auto">
                      {notifications.length === 0 ? (
                        <div className="py-10 text-center">
                          <Bell size={20} className="text-chalk mx-auto mb-2" />
                          <p className="text-xs text-slate">No notifications yet</p>
                        </div>
                      ) : (
                        notifications.map((n) => (
                          <Link
                            key={n._id}
                            href={`/projects/${n.sleeping_project_id}`}
                            onClick={() => {
                              if (!n.read) markRead(n._id);
                            }}
                            className={`block px-4 py-3 transition-colors hover:bg-powder/60 cursor-pointer ${
                              !n.read ? "bg-atmosphere/10" : ""
                            }`}
                          >
                            <div className="flex gap-3">
                              <div className="flex-shrink-0 mt-0.5">
                                <div
                                  className="w-8 h-8 rounded-full flex items-center justify-center"
                                  style={{
                                    background: !n.read
                                      ? "linear-gradient(135deg, rgba(160,181,235,0.3), rgba(255,148,115,0.2))"
                                      : "#f5f3f1",
                                  }}
                                >
                                  <Sparkles size={13} className={!n.read ? "text-obsidian" : "text-slate"} />
                                </div>
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className={`text-sm leading-snug ${!n.read ? "text-obsidian" : "text-gravel"}`}>
                                  A new fragment matches{" "}
                                  <span className="font-medium">
                                    {n.sleeping_project_title || "a sleeping project"}
                                  </span>
                                </p>
                                <div className="flex items-center gap-2 mt-1">
                                  <span className="text-[10px] text-slate">
                                    {timeAgo(n.created_at)}
                                  </span>
                                  <span className="text-[10px] text-slate">
                                    · {Math.round(n.similarity_score * 100)}% match
                                  </span>
                                </div>
                              </div>
                              {!n.read && (
                                <div className="flex-shrink-0 mt-2">
                                  <div className="w-2 h-2 rounded-full bg-obsidian" />
                                </div>
                              )}
                            </div>
                          </Link>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Sign out */}
              <button
                onClick={() => signOut()}
                className="flex items-center gap-1.5 text-xs text-slate hover:text-obsidian transition-colors cursor-pointer btn-press px-3 py-1.5 rounded-full hover:bg-powder"
                aria-label="Sign out"
              >
                <LogOut size={14} />
                <span className="hidden sm:inline">Sign out</span>
              </button>
            </>
          ) : !loading ? (
            <button
              onClick={() => signInWithGoogle()}
              className="btn-gradient text-white px-5 py-2 rounded-full text-sm font-medium hover:opacity-90 transition-opacity btn-press cursor-pointer whitespace-nowrap"
            >
              Sign in
            </button>
          ) : (
            <div className="w-16" />
          )}
        </div>
      </div>
    </header>
  );
}
