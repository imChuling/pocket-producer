import { describe, expect, it, vi } from "vitest";

import { createAudiotoolController } from "./client";
import type {
  NexusAuthResult,
  NexusAuthorize,
  NexusDocumentPort,
} from "@/types/audiotool";

function fakeDocument(overrides: Partial<NexusDocumentPort> = {}) {
  return {
    start: vi.fn(async () => {}),
    stop: vi.fn(async () => {}),
    ...overrides,
  };
}

function fakeAuthenticated(overrides: Record<string, unknown> = {}) {
  const doc = fakeDocument();
  const client = {
    status: "authenticated" as const,
    userName: "chuling",
    open: vi.fn(async () => doc),
    listProjects: vi.fn(async () => [
      { name: "projects/p1", displayName: "Night Bus" },
    ]),
    logout: vi.fn(),
    ...overrides,
  };
  return { client, doc };
}

function authorizeWith(result: NexusAuthResult): NexusAuthorize {
  return vi.fn(async () => result);
}

describe("createAudiotoolController", () => {
  it("never opens a project before authorization succeeds", async () => {
    let resolveAuth: (value: NexusAuthResult) => void = () => {};
    const pending = new Promise<NexusAuthResult>((resolve) => {
      resolveAuth = resolve;
    });
    const { client } = fakeAuthenticated();
    const controller = createAudiotoolController({ authorize: () => pending });

    const connecting = controller.connect();
    await expect(controller.openProject("projects/p1")).rejects.toThrow(
      /not connected/i,
    );
    expect(client.open).not.toHaveBeenCalled();
    expect(controller.state().status).toBe("authorizing");

    resolveAuth({ ...client });
    await connecting;
    expect(controller.state().status).toBe("connected");
  });

  it("reaches connected with user name and project list on success", async () => {
    const { client } = fakeAuthenticated();
    const controller = createAudiotoolController({
      authorize: authorizeWith({ ...client }),
    });
    await controller.connect();
    const state = controller.state();
    expect(state.status).toBe("connected");
    expect(state.userName).toBe("chuling");
    expect(state.projects).toHaveLength(1);
    expect(state.error).toBeNull();
  });

  it("enters error state when authorization is rejected or popup closed", async () => {
    const controller = createAudiotoolController({
      authorize: authorizeWith({
        status: "unauthenticated",
        error: new Error("popup closed"),
      }),
    });
    await controller.connect();
    expect(controller.state().status).toBe("error");
    expect(controller.state().error).toMatch(/popup closed/);
  });

  it("recovers by reconnecting after an auth failure", async () => {
    const { client } = fakeAuthenticated();
    const results: NexusAuthResult[] = [
      { status: "unauthenticated", error: new Error("denied") },
      { ...client },
    ];
    const authorize = vi.fn(async () => results.shift() as NexusAuthResult);
    const controller = createAudiotoolController({ authorize });
    await controller.connect();
    expect(controller.state().status).toBe("error");
    await controller.connect();
    expect(controller.state().status).toBe("connected");
  });

  it("ignores duplicate connect calls while authorizing", async () => {
    let resolveAuth: (value: NexusAuthResult) => void = () => {};
    const pending = new Promise<NexusAuthResult>((resolve) => {
      resolveAuth = resolve;
    });
    const authorize = vi.fn(() => pending);
    const controller = createAudiotoolController({ authorize });
    const first = controller.connect();
    const second = controller.connect();
    const { client } = fakeAuthenticated();
    resolveAuth({ ...client });
    await Promise.all([first, second]);
    expect(authorize).toHaveBeenCalledTimes(1);
  });

  it("opens and starts a project after connecting", async () => {
    const { client, doc } = fakeAuthenticated();
    const controller = createAudiotoolController({
      authorize: authorizeWith({ ...client }),
    });
    await controller.connect();
    await controller.openProject("projects/p1");
    expect(client.open).toHaveBeenCalledWith("projects/p1");
    expect(doc.start).toHaveBeenCalledTimes(1);
    expect(controller.state().status).toBe("project-open");
    expect(controller.state().openProjectName).toBe("projects/p1");
  });

  it("reports a recoverable error when the project does not exist", async () => {
    const { client } = fakeAuthenticated({
      open: vi.fn(async () => {
        throw new Error("project not found");
      }),
    });
    const controller = createAudiotoolController({
      authorize: authorizeWith({ ...client }),
    });
    await controller.connect();
    await expect(controller.openProject("projects/nope")).rejects.toThrow(
      /not found/,
    );
    expect(controller.state().status).toBe("connected");
    expect(controller.state().error).toMatch(/not found/);
  });

  it("stops the document when closing a project", async () => {
    const { client, doc } = fakeAuthenticated();
    const controller = createAudiotoolController({
      authorize: authorizeWith({ ...client }),
    });
    await controller.connect();
    await controller.openProject("projects/p1");
    await controller.closeProject();
    expect(doc.stop).toHaveBeenCalledTimes(1);
    expect(controller.state().status).toBe("connected");
    expect(controller.state().openProjectName).toBeNull();
  });

  it("dispose stops any open document and unsubscribes listeners", async () => {
    const { client, doc } = fakeAuthenticated();
    const controller = createAudiotoolController({
      authorize: authorizeWith({ ...client }),
    });
    const listener = vi.fn();
    const unsubscribe = controller.subscribe(listener);
    await controller.connect();
    await controller.openProject("projects/p1");
    const callsBefore = listener.mock.calls.length;
    await controller.dispose();
    expect(doc.stop).toHaveBeenCalledTimes(1);
    unsubscribe();
    await controller.connect().catch(() => {});
    expect(listener.mock.calls.length).toBe(callsBefore + 1); // only dispose notified
  });

  describe("restore (OAuth redirect return)", () => {
    it("adopts an existing session without asking to log in", async () => {
      const { client } = fakeAuthenticated();
      const authorize = vi.fn(async () => ({ ...client }));
      const controller = createAudiotoolController({ authorize });

      await controller.restore();

      expect(authorize).toHaveBeenCalledWith({ interactive: false });
      expect(controller.state().status).toBe("connected");
      expect(controller.state().userName).toBe("chuling");
    });

    it("stays idle — not error — when there is no session", async () => {
      const controller = createAudiotoolController({
        authorize: authorizeWith({ status: "unauthenticated" }),
      });

      await controller.restore();

      expect(controller.state().status).toBe("idle");
      expect(controller.state().error).toBeNull();
    });

    it("stays idle when the authorize call throws", async () => {
      const controller = createAudiotoolController({
        authorize: vi.fn(async () => {
          throw new Error("network down");
        }),
      });

      await controller.restore();

      expect(controller.state().status).toBe("idle");
    });

    it("does not disturb an already connected controller", async () => {
      const { client } = fakeAuthenticated();
      const authorize = vi.fn(async () => ({ ...client }));
      const controller = createAudiotoolController({ authorize });
      await controller.connect();
      const callsAfterConnect = authorize.mock.calls.length;

      await controller.restore();

      expect(authorize).toHaveBeenCalledTimes(callsAfterConnect);
      expect(controller.state().status).toBe("connected");
    });

    it("connect asks for an interactive authorization", async () => {
      const { client } = fakeAuthenticated();
      const authorize = vi.fn(async () => ({ ...client }));
      await createAudiotoolController({ authorize }).connect();
      expect(authorize).toHaveBeenCalledWith({ interactive: true });
    });
  });

  // Regression: React StrictMode remounts run the effect cleanup between two
  // mounts with the same controller, so cleanup must not make it unusable.
  it("stays usable after a close/reconnect cycle", async () => {
    const { client, doc } = fakeAuthenticated();
    const controller = createAudiotoolController({
      authorize: authorizeWith({ ...client }),
    });
    await controller.connect();
    await controller.openProject("projects/p1");

    await controller.closeProject();
    expect(doc.stop).toHaveBeenCalledTimes(1);

    await expect(controller.connect()).resolves.toBeUndefined();
    await expect(
      controller.openProject("projects/p1"),
    ).resolves.toBeUndefined();
    expect(controller.state().status).toBe("project-open");
  });

  it("notifies subscribers on every transition", async () => {
    const { client } = fakeAuthenticated();
    const controller = createAudiotoolController({
      authorize: authorizeWith({ ...client }),
    });
    const seen: string[] = [];
    controller.subscribe((state) => seen.push(state.status));
    await controller.connect();
    expect(seen).toEqual(["authorizing", "connected"]);
  });
});
