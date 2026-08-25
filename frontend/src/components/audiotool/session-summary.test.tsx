import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionSummary } from "./session-summary";
import type { ParsedIntent, SessionFingerprint } from "@/types/audiotool";

const parseIntentMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/ranking-api", () => ({ parseIntent: parseIntentMock }));

afterEach(() => {
  cleanup();
  parseIntentMock.mockReset();
});

function fingerprint(textIntent = ""): SessionFingerprint {
  return {
    project_id: "p1",
    bpm: 120,
    key: null,
    playhead_seconds: 0,
    track_count: 1,
    active_track_types: ["audio"],
    recent_entity_ids: [],
    text_intent: textIntent,
  };
}

const parsed: ParsedIntent = {
  tags: ["dark", "cinematic"],
  roles: ["bass"],
  bpm: 90,
  key: "a minor",
};

describe("SessionSummary intent chips", () => {
  it("renders the user-approved reading as removable chips", () => {
    render(
      <SessionSummary
        fingerprint={fingerprint("darker, cinematic")}
        onIntentChange={() => {}}
        parsedIntent={parsed}
        onParsedIntentChange={() => {}}
      />,
    );
    expect(screen.getByText("dark")).toBeDefined();
    expect(screen.getByText("cinematic")).toBeDefined();
    expect(screen.getByText("needs bass")).toBeDefined();
    expect(screen.getByText("~90 BPM")).toBeDefined();
    expect(screen.getByText("a minor")).toBeDefined();
  });

  it("removing a chip narrows the parsed intent", async () => {
    const onChange = vi.fn();
    render(
      <SessionSummary
        fingerprint={fingerprint("darker, cinematic")}
        onIntentChange={() => {}}
        parsedIntent={parsed}
        onParsedIntentChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Remove dark" }));
    expect(onChange).toHaveBeenCalledWith({ ...parsed, tags: ["cinematic"] });
  });

  it("removing the last chip clears the parsed intent entirely", async () => {
    const onChange = vi.fn();
    render(
      <SessionSummary
        fingerprint={fingerprint("slow")}
        onIntentChange={() => {}}
        parsedIntent={{ tags: [], roles: [], bpm: 70, key: null }}
        onParsedIntentChange={onChange}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Remove ~70 BPM" }),
    );
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("asks the server for a reading after the user pauses typing", async () => {
    parseIntentMock.mockResolvedValue(parsed);
    const onChange = vi.fn();
    render(
      <SessionSummary
        fingerprint={fingerprint("darker, more cinematic")}
        onIntentChange={() => {}}
        parsedIntent={null}
        onParsedIntentChange={onChange}
      />,
    );
    await waitFor(
      () => {
        expect(parseIntentMock).toHaveBeenCalledWith("darker, more cinematic");
        expect(onChange).toHaveBeenCalledWith(parsed);
      },
      { timeout: 3000 },
    );
  });

  it("does not call the server without a parsed-intent handler", async () => {
    render(
      <SessionSummary
        fingerprint={fingerprint("darker, more cinematic")}
        onIntentChange={() => {}}
      />,
    );
    await new Promise((resolve) => setTimeout(resolve, 1000));
    expect(parseIntentMock).not.toHaveBeenCalled();
  });
});
