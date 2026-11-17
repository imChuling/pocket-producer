import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AudioRecorder } from "./audio-recorder";

class FakeRecorder {
  static instances: FakeRecorder[] = [];
  static isTypeSupported() {
    return true;
  }
  state = "inactive";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  constructor() {
    FakeRecorder.instances.push(this);
  }
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["take"]) });
    this.onstop?.();
  }
}

class FakeAudioContext {
  state = "running";
  createMediaStreamSource() {
    return { connect() {} };
  }
  createAnalyser() {
    return { fftSize: 0, frequencyBinCount: 0, getByteFrequencyData() {} };
  }
  close() {
    return Promise.resolve();
  }
}

describe("AudioRecorder", () => {
  let grant: (stream: unknown) => void;
  let getUserMedia: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    FakeRecorder.instances = [];
    getUserMedia = vi.fn(
      () =>
        new Promise((resolve) => {
          grant = resolve;
        }),
    );
    vi.stubGlobal("MediaRecorder", FakeRecorder);
    vi.stubGlobal("AudioContext", FakeAudioContext);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("opens one recorder when the button is clicked again during the permission prompt", async () => {
    const onRecorded = vi.fn();
    render(<AudioRecorder onRecorded={onRecorded} />);
    const button = screen.getByRole("button", { name: "Start recording" });

    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);
    expect(getUserMedia).toHaveBeenCalledTimes(1);

    await act(async () => {
      grant({ getTracks: () => [{ stop() {} }] });
    });
    expect(FakeRecorder.instances).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Stop recording" }));
    expect(onRecorded).toHaveBeenCalledTimes(1);
  });
});
