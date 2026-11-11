"use client";

import { createContext, useContext } from "react";

export const DemoToastContext = createContext<(msg?: string) => void>(() => {});

export function useDemoToast() {
  return useContext(DemoToastContext);
}
