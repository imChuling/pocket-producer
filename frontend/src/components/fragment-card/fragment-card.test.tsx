import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Fragment } from "@/types";

const apiPost = vi.fn();
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  apiPost: (...args: unknown[]) => apiPost(...args),
}));

// Child components import the auth client at module load; keep tests off Firebase.
vi.mock("@/lib/firebase", () => ({ getIdToken: vi.fn(async () => "token") }));

import { FragmentCard } from "./index";

afterEach(() => {
  cleanup();
  apiPost.mockReset();
});

const textFragment: Fragment = {
  _id: "f1",
  user_id: "u1",
  type: "text",
  title: "Rain line",
  text: "rain on the window",
  tags: [],
  emotions: [],
  themes: [],
  created_at: "2026-07-01T00:00:00Z",
  status: "ready",
} as Fragment;

describe("FragmentCard delete", () => {
  it("says so when a delete fails", async () => {
    apiPost.mockRejectedValueOnce(new Error("network"));
    const onDeleted = vi.fn();
    render(<FragmentCard fragment={textFragment} onDeleted={onDeleted} />);

    await userEvent.click(screen.getByRole("button", { name: /delete fragment/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not delete/i);
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
