import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnnotatePanel, type PairTask } from "./annotate-panel";

afterEach(cleanup);

function pair(id = "pair1"): PairTask {
  return {
    pair_id: id,
    context_project_id: "proj1",
    context: [
      { fragment_id: "c1", title: "Context loop", audio_url: "/a/c1" },
    ],
    left: { fragment_id: "l1", title: "Left idea", audio_url: "/a/l1" },
    right: { fragment_id: "r1", title: "Right idea", audio_url: "/a/r1" },
  };
}

function setup(overrides: Partial<Parameters<typeof AnnotatePanel>[0]> = {}) {
  const props = {
    fetchNext: vi.fn(async () => ({
      done: false as const,
      remaining: 5,
      pair: pair(),
    })),
    submitLabel: vi.fn(async () => {}),
    onPreview: vi.fn(async () => {}),
    ...overrides,
  };
  render(<AnnotatePanel {...props} />);
  return props;
}

describe("AnnotatePanel", () => {
  it("loads and shows the pair with context and remaining count", async () => {
    setup();
    expect(await screen.findByText("Left idea")).toBeInTheDocument();
    expect(screen.getByText("Right idea")).toBeInTheDocument();
    expect(screen.getByText("Context loop")).toBeInTheDocument();
    expect(screen.getByText(/5 pairs left/i)).toBeInTheDocument();
  });

  it("requires a choice before submitting", async () => {
    setup();
    await screen.findByText("Left idea");
    expect(
      screen.getByRole("button", { name: /^submit$/i }),
    ).toBeDisabled();
  });

  it("submits choice with reason codes and confidence then loads next", async () => {
    const tasks = [
      { done: false as const, remaining: 2, pair: pair("pair1") },
      { done: false as const, remaining: 1, pair: pair("pair2") },
    ];
    const fetchNext = vi.fn(async () => tasks.shift()!);
    const props = setup({ fetchNext });
    await screen.findByText("Left idea");
    await userEvent.click(screen.getByRole("button", { name: /choose a/i }));
    await userEvent.click(screen.getByRole("button", { name: /tempo fit/i }));
    await userEvent.click(screen.getByRole("button", { name: /^submit$/i }));
    await waitFor(() => expect(props.submitLabel).toHaveBeenCalledTimes(1));
    expect(props.submitLabel).toHaveBeenCalledWith("pair1", {
      choice: "left",
      reason_codes: ["tempo_fit"],
      confidence: 3,
    });
    expect(fetchNext).toHaveBeenCalledTimes(2);
  });

  it("supports the neither option", async () => {
    const props = setup();
    await screen.findByText("Left idea");
    await userEvent.click(
      screen.getByRole("button", { name: /neither works/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: /^submit$/i }));
    await waitFor(() =>
      expect(props.submitLabel).toHaveBeenCalledWith(
        "pair1",
        expect.objectContaining({ choice: "neither" }),
      ),
    );
  });

  it("shows the done state when no pairs remain", async () => {
    setup({
      fetchNext: vi.fn(async () => ({
        done: true as const,
        remaining: 0 as const,
      })),
    });
    expect(
      await screen.findByText(/all pairs labeled/i),
    ).toBeInTheDocument();
  });

  it("previews call the preview handler", async () => {
    const props = setup();
    await screen.findByText("Left idea");
    const previews = screen.getAllByRole("button", { name: /preview/i });
    await userEvent.click(previews[0]);
    expect(props.onPreview).toHaveBeenCalled();
  });
});
