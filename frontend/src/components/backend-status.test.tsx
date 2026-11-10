import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BackendStatus } from "./backend-status";

function readyResponse(body: object, status = 200) {
  return { status, json: async () => body };
}

describe("BackendStatus", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("shows nothing when the backend is already up", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => readyResponse({ mongo: "ok", clap: "ready" })));
    render(<BackendStatus />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("explains the wait while the backend starts, then while the model loads, then disappears", async () => {
    const answers = [
      readyResponse({ mongo: "error: TimeoutError", clap: "loading" }, 503),
      readyResponse({ mongo: "ok", clap: "loading" }),
      readyResponse({ mongo: "ok", clap: "ready" }),
    ];
    vi.stubGlobal("fetch", vi.fn(async () => answers.shift() ?? readyResponse({ mongo: "ok", clap: "ready" })));
    render(<BackendStatus />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByRole("status").textContent).toMatch(/deployment limits/);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByRole("status").textContent).toMatch(/loading the audio model/);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("treats a network failure as the backend still starting", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("offline");
    }));
    render(<BackendStatus />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByRole("status").textContent).toMatch(/starting now/);
  });
});
