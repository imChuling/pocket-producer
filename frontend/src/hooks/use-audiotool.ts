"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import {
  createAudiotoolController,
  createRedirectAuthorize,
} from "@/lib/audiotool/client";
import type {
  AudiotoolControllerState,
  NexusAuthorize,
  NexusDocumentPort,
} from "@/types/audiotool";

const SERVER_SNAPSHOT: AudiotoolControllerState = {
  status: "idle",
  userName: null,
  projects: [],
  openProjectName: null,
  error: null,
};

export function useAudiotool(options?: { authorize?: NexusAuthorize }) {
  // The controller is created exactly once per hook instance; the authorize
  // implementation is captured on first render by design.
  const [controller] = useState(() =>
    createAudiotoolController({
      authorize:
        options?.authorize ??
        createRedirectAuthorize({
          clientId: process.env.NEXT_PUBLIC_AUDIOTOOL_CLIENT_ID ?? "",
          // Must exactly match a redirect URI registered for the application.
          redirectUrl:
            typeof window === "undefined"
              ? ""
              : `${window.location.origin}/audiotool`,
        }),
    }),
  );

  const state = useSyncExternalStore(
    controller.subscribe,
    controller.state,
    () => SERVER_SNAPSHOT,
  );

  useEffect(() => {
    // Finish a pending OAuth redirect (or reuse a stored session) without
    // navigating anywhere. Deferred a tick so it never sets state during render.
    const timer = window.setTimeout(() => {
      void controller.restore();
    }, 0);

    // Release the synced document, but keep the controller usable: React
    // StrictMode remounts with the same instance, and `dispose()` is terminal.
    // Subscriptions are already torn down by useSyncExternalStore.
    return () => {
      window.clearTimeout(timer);
      void controller.closeProject();
    };
  }, [controller]);

  const connect = useCallback(() => controller.connect(), [controller]);
  const openProject = useCallback(
    (projectName: string) => controller.openProject(projectName),
    [controller],
  );
  const closeProject = useCallback(
    () => controller.closeProject(),
    [controller],
  );
  const document = useCallback(
    (): NexusDocumentPort | null => controller.document(),
    [controller],
  );
  const samples = useCallback(() => controller.samples(), [controller]);

  return {
    status: state.status,
    userName: state.userName,
    projects: state.projects,
    openProjectName: state.openProjectName,
    error: state.error,
    connect,
    openProject,
    closeProject,
    document,
    samples,
  };
}
