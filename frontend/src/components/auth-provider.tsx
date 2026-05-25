"use client";

import { ReactNode } from "react";
import { AuthContext, useAuthState } from "@/hooks/use-auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const state = useAuthState();
  return <AuthContext value={state}>{children}</AuthContext>;
}
