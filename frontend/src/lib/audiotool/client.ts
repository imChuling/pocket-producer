// Isolated Audiotool Nexus lifecycle.
//
// OAuth tokens never leave this browser tab. `exportTokens()` is used once, to
// re-create the SDK client with a working WASM loader (see documentOpener);
// the values are passed straight back into the SDK and are never sent to the
// Pocket Producer backend, logged, or persisted by us.

import {
  audiotool,
  audiotoolPopup,
  createAudiotoolClient,
  createServerAuth,
} from "@audiotool/nexus";

import { createBrowserWasmLoader } from "@/lib/audiotool/wasm-loader";

import type {
  AudiotoolControllerState,
  NexusAuthorize,
  NexusAuthResult,
  NexusClientPort,
  NexusDocumentPort,
  NexusSamplesPort,
  ProjectSummary,
} from "@/types/audiotool";

export type AudiotoolController = {
  connect: () => Promise<void>;
  /**
   * Complete a pending OAuth redirect, or pick up an existing session, without
   * ever navigating the user away. Safe to call on every mount.
   */
  restore: () => Promise<void>;
  openProject: (projectName: string) => Promise<void>;
  closeProject: () => Promise<void>;
  dispose: () => Promise<void>;
  state: () => AudiotoolControllerState;
  subscribe: (
    listener: (state: AudiotoolControllerState) => void,
  ) => () => void;
  /** The currently open document, if any. Exposed for fingerprint/insert modules. */
  document: () => NexusDocumentPort | null;
  /** Sample upload API of the authenticated client, if connected. */
  samples: () => NexusSamplesPort | null;
};

const INITIAL_STATE: AudiotoolControllerState = {
  status: "idle",
  userName: null,
  projects: [],
  openProjectName: null,
  error: null,
};

export function createAudiotoolController(deps: {
  authorize: NexusAuthorize;
}): AudiotoolController {
  let state: AudiotoolControllerState = { ...INITIAL_STATE };
  let client: NexusClientPort | null = null;
  let openDocument: NexusDocumentPort | null = null;
  let authorizing: Promise<void> | null = null;
  let disposed = false;
  const listeners = new Set<(state: AudiotoolControllerState) => void>();

  function setState(patch: Partial<AudiotoolControllerState>) {
    state = { ...state, ...patch };
    for (const listener of listeners) listener(state);
  }

  async function adoptClient(result: NexusClientPort): Promise<void> {
    client = result;
    let projects: ProjectSummary[] = [];
    let projectsError: string | null = null;
    try {
      projects = await result.listProjects();
    } catch (cause) {
      projectsError = `Could not load projects: ${messageOf(cause)}`;
    }
    setState({
      status: "connected",
      userName: result.userName,
      projects,
      error: projectsError,
    });
  }

  async function connect(): Promise<void> {
    if (disposed) throw new Error("Audiotool controller has been disposed");
    if (state.status === "connected" || state.status === "project-open") return;
    if (authorizing) return authorizing;

    setState({ status: "authorizing", error: null });
    authorizing = (async () => {
      let result: NexusAuthResult;
      try {
        result = await deps.authorize({ interactive: true });
      } catch (cause) {
        setState({ status: "error", error: messageOf(cause) });
        return;
      } finally {
        authorizing = null;
      }
      if (result.status !== "authenticated") {
        setState({
          status: "error",
          error: result.error?.message ?? "Authorization was not completed",
        });
        return;
      }
      await adoptClient(result);
    })();
    return authorizing;
  }

  async function restore(): Promise<void> {
    if (disposed || authorizing) return;
    if (state.status !== "idle") return;
    let result: NexusAuthResult;
    try {
      result = await deps.authorize({ interactive: false });
    } catch {
      // No session to restore; stay idle so the user can start one.
      return;
    }
    if (result.status !== "authenticated" || disposed) return;
    await adoptClient(result);
  }

  async function openProject(projectName: string): Promise<void> {
    if (disposed) throw new Error("Audiotool controller has been disposed");
    if (client === null || state.status === "idle" || state.status === "authorizing") {
      throw new Error("Not connected to Audiotool yet");
    }
    if (openDocument !== null) await closeProject();
    try {
      const doc = await client.open(projectName);
      await doc.start();
      openDocument = doc;
      setState({
        status: "project-open",
        openProjectName: projectName,
        error: null,
      });
    } catch (cause) {
      const message = messageOf(cause);
      setState({ status: "connected", openProjectName: null, error: message });
      throw cause instanceof Error ? cause : new Error(message);
    }
  }

  async function closeProject(): Promise<void> {
    const doc = openDocument;
    openDocument = null;
    if (doc !== null) {
      try {
        await doc.stop();
      } catch {
        // The document is being thrown away either way.
      }
    }
    if (state.status === "project-open") {
      setState({ status: "connected", openProjectName: null });
    }
  }

  async function dispose(): Promise<void> {
    if (disposed) return;
    disposed = true;
    const doc = openDocument;
    openDocument = null;
    if (doc !== null) {
      try {
        await doc.stop();
      } catch {
        // Shutting down regardless.
      }
    }
    setState({ ...INITIAL_STATE });
    listeners.clear();
    client = null;
  }

  return {
    connect,
    restore,
    openProject,
    closeProject,
    dispose,
    state: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    document: () => openDocument,
    samples: () => client?.samples ?? null,
  };
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

type AuthenticatedNexus = {
  userName: string;
  open: (project: string) => Promise<NexusDocumentPort>;
  samples: unknown;
  projects: { listProjects: (request: object) => Promise<unknown> };
  logout: () => void;
  exportTokens?: () => {
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
  };
};

/**
 * Build a client that can actually open documents.
 *
 * The client returned by `audiotool()` carries no WASM loader, so `open()`
 * fails in a Next.js bundle (see wasm-loader.ts). Re-create it from the same
 * tokens with an explicit browser loader. Tokens stay in this tab — they are
 * never sent to the Pocket Producer backend.
 */
function documentOpener(
  result: AuthenticatedNexus,
  clientId: string,
): (project: string) => Promise<NexusDocumentPort> {
  let clientPromise: Promise<{
    open: (project: string) => Promise<NexusDocumentPort>;
  }> | null = null;

  return async (project: string) => {
    if (typeof result.exportTokens !== "function") {
      return result.open(project);
    }
    if (clientPromise === null) {
      const tokens = result.exportTokens();
      clientPromise = createAudiotoolClient({
        auth: createServerAuth({ ...tokens, clientId }),
        wasm: createBrowserWasmLoader(),
      }) as unknown as Promise<{
        open: (project: string) => Promise<NexusDocumentPort>;
      }>;
    }
    const client = await clientPromise;
    return client.open(project);
  };
}

/** Adapt the SDK's authenticated client to our narrow port. */
function adaptAuthenticated(
  result: AuthenticatedNexus,
  clientId: string,
): NexusAuthResult {
  return {
    status: "authenticated",
    userName: result.userName,
    open: documentOpener(result, clientId),
    samples: result.samples as NexusSamplesPort,
    listProjects: async () => {
      const all: { name: string; displayName: string }[] = [];
      let pageToken = "";
      for (;;) {
        const response = await result.projects.listProjects({
          pageSize: 100,
          pageToken,
        });
        if (response instanceof Error) throw response;
        const page = response as {
          projects?: { name?: string; displayName?: string }[];
          nextPageToken?: string;
        };
        for (const p of page.projects ?? []) {
          all.push({
            name: p.name ?? "",
            displayName: p.displayName ?? p.name ?? "Untitled",
          });
        }
        if (!page.nextPageToken) break;
        pageToken = page.nextPageToken;
      }
      return all;
    },
    logout: () => result.logout(),
  };
}

/**
 * Production authorize function using the full-page redirect flow.
 *
 * The popup flow is not usable: as of 2026-08-01 Audiotool's
 * `accounts.audiotool.com/oauth/popup/start` endpoint returns 404, and popups
 * are blocked by default anyway. `audiotool()` navigates the whole tab to the
 * consent screen and returns here, so no pop-up permission is ever needed.
 *
 * `redirectUrl` must match a redirect URI registered for the application
 * exactly, including the path.
 */
export function createRedirectAuthorize(config: {
  clientId: string;
  redirectUrl: string;
  scope?: string;
}): NexusAuthorize {
  return async ({ interactive = true } = {}) => {
    const result = await audiotool({
      clientId: config.clientId,
      redirectUrl: config.redirectUrl,
      scope: config.scope ?? "project:write",
    });
    if (result.status !== "authenticated") {
      // Navigates away; the promise below never settles in practice.
      if (interactive) result.login();
      return { status: "unauthenticated", error: result.error };
    }
    return adaptAuthenticated(
      result as unknown as AuthenticatedNexus,
      config.clientId,
    );
  };
}

/**
 * Popup-based authorize, kept for embedded (iframe) contexts where a full-page
 * redirect is impossible. Not the default — see createRedirectAuthorize.
 *
 * `audiotoolPopup` is imported statically on purpose: a dynamic `await
 * import()` here would yield before opening the window, the browser would no
 * longer see a user gesture, and the popup would be blocked.
 */
export function createPopupAuthorize(config: {
  clientId: string;
  scope?: string;
}): NexusAuthorize {
  return async () => {
    const result = await audiotoolPopup({
      clientId: config.clientId,
      scope: config.scope ?? "project:write",
    });
    if (result.status !== "authenticated") {
      return { status: "unauthenticated", error: result.error };
    }
    return adaptAuthenticated(
      result as unknown as AuthenticatedNexus,
      config.clientId,
    );
  };
}
