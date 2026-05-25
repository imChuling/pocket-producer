"use client";

import { useState, useEffect, createContext, useContext } from "react";
import { auth, onAuthStateChanged, type User } from "@/lib/firebase";

interface AuthState {
  user: User | null;
  loading: boolean;
}

export const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
});

export function useAuthState(): AuthState {
  const [state, setState] = useState<AuthState>({ user: null, loading: true });

  useEffect(() => {
    return onAuthStateChanged(auth, (user) => {
      setState({ user, loading: false });
    });
  }, []);

  return state;
}

export function useAuth() {
  return useContext(AuthContext);
}
