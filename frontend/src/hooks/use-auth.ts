"use client";

import { useState, useEffect, createContext, useContext } from "react";
import { auth, onAuthStateChanged, type User } from "@/lib/firebase";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}

export const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  error: null,
});

// If auth never resolves, the app must not hang on a spinner forever.
const AUTH_TIMEOUT_MS = 10_000;

export function useAuthState(): AuthState {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let settled = false;
    const timer = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      console.error("Firebase auth did not resolve within 10s");
      setState({
        user: null,
        loading: false,
        error: "Sign-in service did not respond. Check your connection and reload.",
      });
    }, AUTH_TIMEOUT_MS);

    const unsubscribe = onAuthStateChanged(
      auth,
      (user) => {
        settled = true;
        window.clearTimeout(timer);
        setState({ user, loading: false, error: null });
      },
      // Without this handler Firebase errors are swallowed and the UI hangs.
      (error) => {
        settled = true;
        window.clearTimeout(timer);
        console.error("Firebase auth error:", error);
        setState({ user: null, loading: false, error: error.message });
      },
    );

    return () => {
      window.clearTimeout(timer);
      unsubscribe();
    };
  }, []);

  return state;
}

export function useAuth() {
  return useContext(AuthContext);
}
