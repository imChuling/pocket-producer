import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IDLE_AFTER_MS, _setLastActivityForTests } from "@/lib/idle";

const apiFetchMock = vi.fn();
// One stable user object: a fresh object per render would re-run the hook's
// effects on every state update and inflate the call counts.
const USER = vi.hoisted(() => ({ uid: "u1" }));
vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  apiPost: vi.fn(),
}));
vi.mock("./use-auth", () => ({ useAuth: () => ({ user: USER }) }));

import { useNotifications } from "./use-notifications";

const POLL = 30_000;

describe("useNotifications polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({ notifications: [], unread_count: 0 });
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
    _setLastActivityForTests(0);
  });

  afterEach(() => {
    // Unmount so this test's onActive subscription does not fire in the next.
    cleanup();
    vi.useRealTimers();
  });

  it("polls while the tab is visible and in use", async () => {
    renderHook(() => useNotifications());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(apiFetchMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL * 2);
    });
    expect(apiFetchMock).toHaveBeenCalledTimes(3);
  });

  it("stops polling once the user has been idle, and does not wake the backend", async () => {
    renderHook(() => useNotifications());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    _setLastActivityForTests(IDLE_AFTER_MS + 1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL * 10);
    });
    expect(apiFetchMock).toHaveBeenCalledTimes(1);
  });

  it("skips hidden tabs", async () => {
    renderHook(() => useNotifications());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL * 5);
    });
    expect(apiFetchMock).toHaveBeenCalledTimes(1);
  });

  it("refreshes once when the user comes back after being idle", async () => {
    renderHook(() => useNotifications());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    _setLastActivityForTests(IDLE_AFTER_MS + 1);
    await act(async () => {
      window.dispatchEvent(new Event("pointerdown"));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(apiFetchMock).toHaveBeenCalledTimes(2);
  });
});
