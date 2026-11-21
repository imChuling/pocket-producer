import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ContinuationPanel } from "./continuation-panel";
import type { Fragment } from "@/types";
import type { RankResponse, SessionFingerprint } from "@/types/audiotool";

// SessionSummary imports ranking-api -> lib/api -> firebase, which
// initializes auth at module load; stub the api layer so tests never
// touch Firebase or the network.
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  apiPost: vi.fn(),
}));

afterEach(cleanup);

const fingerprint: SessionFingerprint = {
  project_id: "p1",
  bpm: 120,
  key: null,
  playhead_seconds: 12,
  track_count: 2,
  active_track_types: ["audio", "note"],
  recent_entity_ids: [],
  text_intent: "dark bass",
};

function fragment(id: string, title: string): Fragment {
  return {
    _id: id,
    user_id: "u1",
    type: "audio",
    title,
    tags: ["dark"],
    emotions: [],
    themes: [],
    created_at: "2026-07-01T00:00:00Z",
    audio_url: `gs://bucket/${id}`,
    upload: { duration_sec: 5 },
  } as Fragment;
}

function response(ids: string[], fallback = false): RankResponse {
  return {
    request_id: "req-1",
    model_id: fallback ? "rules-v1" : "rules-v1",
    fallback_used: fallback,
    candidates: ids.map((id, index) => ({
      fragment_id: id,
      score: 1 - index * 0.1,
      evidence: [
        {
          code: "tempo_match" as const,
          label: "Tempo close to the project's BPM",
          contribution: 0.3,
        },
      ],
    })),
  };
}

function setup(overrides: Partial<Parameters<typeof ContinuationPanel>[0]> = {}) {
  const fragments = [
    fragment("f1", "Night bass"),
    fragment("f2", "Rain pad"),
    fragment("f3", "Tape loop"),
  ];
  const props = {
    fingerprint,
    fragments,
    requestRecommendations: vi.fn(async () => response(["f1", "f2", "f3"])),
    onIntentChange: vi.fn(),
    onPreview: vi.fn(async () => {}),
    onInsert: vi.fn(async () => {}),
    onFeedback: vi.fn(),
    ...overrides,
  };
  const view = render(<ContinuationPanel {...props} />);
  return { ...props, update: (changes: Partial<typeof props>) =>
    view.rerender(<ContinuationPanel {...props} {...changes} />) };
}

describe("ContinuationPanel", () => {
  it("renders three candidates with evidence after requesting suggestions", async () => {
    const props = setup();
    await userEvent.click(
      screen.getByRole("button", { name: /suggest 3/i }),
    );
    expect(await screen.findByText("Night bass")).toBeInTheDocument();
    expect(screen.getByText("Rain pad")).toBeInTheDocument();
    expect(screen.getByText("Tape loop")).toBeInTheDocument();
    expect(
      screen.getAllByText(/tempo close to the project's bpm/i).length,
    ).toBeGreaterThan(0);
    expect(props.requestRecommendations).toHaveBeenCalledTimes(1);
  });

  it("shows the empty-library state without fake recommendations", async () => {
    setup({ fragments: [] });
    expect(
      screen.getByText(/no fragments in your library yet/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /suggest 3/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a recoverable error when the backend fails", async () => {
    setup({
      requestRecommendations: vi.fn(async () => {
        throw new Error("rank API down");
      }),
    });
    await userEvent.click(screen.getByRole("button", { name: /suggest 3/i }));
    expect(
      await screen.findByText(/couldn't get suggestions/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("labels results served by the rules fallback", async () => {
    setup({
      requestRecommendations: vi.fn(async () =>
        response(["f1", "f2", "f3"], true),
      ),
    });
    await userEvent.click(screen.getByRole("button", { name: /suggest 3/i }));
    expect(await screen.findByText(/fallback to rules-v1/i)).toBeInTheDocument();
  });

  it("shows which model actually served non-fallback results", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /suggest 3/i }));
    expect(await screen.findByText(/served by rules-v1/i)).toBeInTheDocument();
  });

  it("offers only server-registered models and sends the selected id", async () => {
    const props = setup({
      availableModels: ["rules-v1", "mean-session-v1", "pocketrank-context-v1"],
    });
    const select = screen.getByRole("combobox", { name: /ranking model/i });
    const options = Array.from(select.querySelectorAll("option")).map(
      (option) => option.value,
    );
    expect(options).toEqual([
      "rules-v1",
      "mean-session-v1",
      "pocketrank-context-v1",
    ]);
    await userEvent.selectOptions(select, "pocketrank-context-v1");
    await userEvent.click(screen.getByRole("button", { name: /suggest 3/i }));
    expect(props.requestRecommendations).toHaveBeenCalledWith(
      3,
      "pocketrank-context-v1",
      new Set(),
    );
  });

  it("labels the role-gap ranker", () => {
    setup({ availableModels: ["rules-v1", "role-gap-v1"] });
    expect(screen.getByRole("option", { name: "Role gap" })).toHaveValue("role-gap-v1");
  });

  it("offers only the rules fallback when the model list is unavailable", () => {
    setup({ availableModels: undefined });
    const select = screen.getByRole("combobox", { name: /ranking model/i });
    const options = Array.from(select.querySelectorAll("option")).map(
      (option) => option.value,
    );
    expect(options).toEqual(["rules-v1"]);
  });

  it("ignores duplicate clicks while a request is in flight", async () => {
    let resolveRank: (value: RankResponse) => void = () => {};
    const pending = new Promise<RankResponse>((resolve) => {
      resolveRank = resolve;
    });
    const props = setup({
      requestRecommendations: vi.fn(() => pending),
    });
    const button = screen.getByRole("button", { name: /suggest 3/i });
    await userEvent.click(button);
    await userEvent.click(button);
    resolveRank(response(["f1", "f2", "f3"]));
    await screen.findByText("Night bass");
    expect(props.requestRecommendations).toHaveBeenCalledTimes(1);
  });

  it("sends preview feedback with rank position", async () => {
    const props = setup();
    await userEvent.click(screen.getByRole("button", { name: /suggest 3/i }));
    await screen.findByText("Night bass");
    await userEvent.click(
      screen.getAllByRole("button", { name: /preview/i })[0],
    );
    expect(props.onPreview).toHaveBeenCalledTimes(1);
    expect(props.onFeedback).toHaveBeenCalledWith(
      expect.objectContaining({
        request_id: "req-1",
        fragment_id: "f1",
        event: "preview",
        rank_position: 1,
      }),
    );
  });

  it("skip removes the card and records feedback", async () => {
    const props = setup();
    await userEvent.click(screen.getByRole("button", { name: /suggest 3/i }));
    await screen.findByText("Night bass");
    await userEvent.click(screen.getAllByRole("button", { name: /skip/i })[0]);
    await waitFor(() =>
      expect(screen.queryByText("Night bass")).not.toBeInTheDocument(),
    );
    expect(props.onFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ event: "reject", fragment_id: "f1" }),
    );
  });

  it("ranks beyond the first three and lets the musician restore skipped sketches", async () => {
    const fragments = ["A", "B", "C", "D"].map(id => fragment(id, id));
    const rank = vi.fn(async (limit: number, _model: string, skipped = new Set<string>()) =>
      response(fragments.map(f => f._id).filter(id => !skipped.has(id)).slice(0, limit)),
    );
    setup({ fragments, requestRecommendations: rank });
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    for (const skip of screen.getAllByRole("button", { name: "Skip" })) {
      await userEvent.click(skip);
    }
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3 again" }));
    expect(screen.queryByRole("heading", { name: "A" })).toBeNull();
    expect(screen.getByRole("heading", { name: "D" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(screen.getByText(/skipped every playable sketch on this page/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suggest 3 again" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Include skipped sketches" }));
    expect(screen.getByRole("heading", { name: "A" })).toBeInTheDocument();
    expect(rank).toHaveBeenLastCalledWith(3, "rules-v1", new Set());
  });

  it("remembers skips across library pages and clears them for a new intent or project", async () => {
    const { update, requestRecommendations } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Skip" })[0]);
    update({ libraryReady: false });
    update({ libraryPage: "older" });
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    expect(requestRecommendations).toHaveBeenLastCalledWith(3, "rules-v1", new Set(["f1"]));
    expect(screen.queryByText("Night bass")).toBeNull();

    const changedIntent = { ...fingerprint, text_intent: "warm brass" };
    update({ fingerprint: changedIntent });
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    expect(screen.getByText("Night bass")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Skip" })[0]);
    update({ fingerprint: { ...changedIntent, project_id: "p2" } });
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    expect(requestRecommendations).toHaveBeenLastCalledWith(3, "rules-v1", new Set());
    expect(screen.getByText("Night bass")).toBeInTheDocument();
  });

  it("shows when a library page has no playable sketches", () => {
    setup({ fragments: [{ ...fragment("f1", "Draft"), type: "text" }] });
    expect(screen.getByText(/no playable sketches on this page/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suggest 3" })).toBeNull();
  });

  it("treats a partly playable page as exhausted after its last playable sketch is skipped", async () => {
    setup({
      fragments: [fragment("f1", "Bass"), { ...fragment("f2", "Lyrics"), type: "text" }],
      requestRecommendations: async () => response(["f1"]),
    });
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    await userEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(screen.getByRole("button", { name: "Suggest 3 again" })).toBeDisabled();
    expect(screen.getByText(/skipped every playable sketch/i)).toBeInTheDocument();
  });

  it("keeps skips when a reading arrives and starts a new round when the musician edits it", async () => {
    const { update, requestRecommendations } = setup({ onParsedIntentChange: vi.fn() });
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Skip" })[0]);
    update({ parsedIntent: { tags: ["dark"], roles: [], key: null, bpm: null } });
    expect(screen.queryByText("Night bass")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Remove dark" }));
    expect(screen.queryByText("Rain pad")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Suggest 3" }));
    expect(requestRecommendations).toHaveBeenLastCalledWith(3, "rules-v1", new Set());
    expect(screen.getByText("Night bass")).toBeInTheDocument();
  });
});
