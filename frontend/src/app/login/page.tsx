"use client";

import { useRouter } from "next/navigation";
import { signInWithGoogle } from "@/lib/firebase";
import { useAuth } from "@/hooks/use-auth";
import { useEffect } from "react";
import { ArrowRight } from "lucide-react";

export default function LoginPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [user, loading, router]);

  async function handleLogin() {
    await signInWithGoogle();
    router.replace("/");
  }

  if (loading) return null;

  return (
    <div className="relative min-h-[calc(100vh-56px)]">
      {/* Ambient background */}
      <div className="ambient-mesh" />

      {/* Decorative morphing blob */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
        <div
          className="w-[350px] h-[350px] morph-blob opacity-25"
          style={{
            background: "linear-gradient(135deg, rgba(160,181,235,0.5), rgba(255,148,115,0.3))",
          }}
        />
      </div>

      <div className="relative z-10 flex flex-col items-center justify-center min-h-[calc(100vh-56px)] animate-page-enter">
        <h1 className="font-heading text-5xl font-light mb-3 tracking-tight leading-tight shimmer-heading">
          Welcome back
        </h1>
        <p className="text-sm text-gravel mb-14">
          Sign in to access your creative memory.
        </p>
        <button
          onClick={handleLogin}
          className="flex items-center gap-3 bg-obsidian text-white px-7 py-3.5 rounded-full text-sm font-medium cursor-pointer hover:opacity-90 transition-opacity btn-press shadow-hairline"
        >
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
          </svg>
          Sign in with Google
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
