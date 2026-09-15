import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useRecorder } from "./useRecorder";

/**
 * The one thing worth pinning here: a recording that ends by itself must still
 * let go. The browser inactivates the recorder when its tracks end — permission
 * revoked from the browser's own UI, the device unplugged, the tab backgrounded
 * on a phone — and `stop()` on an inactive recorder throws, so the release used
 * to be skipped and the mic stayed lit (and, since the composer draws a meter
 * off that flag, amber and ticking) for the rest of the session.
 */

const track = { stop: vi.fn() };

class FakeMediaRecorder {
  state = "recording";
  onstop: (() => void) | null = null;
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  stream = { getTracks: () => [track] };

  start() {}

  stop() {
    if (this.state === "inactive") throw new Error("InvalidStateError");
    this.state = "inactive";
    this.onstop?.();
  }
}

let media: FakeMediaRecorder;

beforeEach(() => {
  track.stop.mockClear();
  vi.stubGlobal(
    "MediaRecorder",
    vi.fn(() => {
      media = new FakeMediaRecorder();
      return media;
    }),
  );
  vi.stubGlobal("navigator", {
    ...navigator,
    mediaDevices: { getUserMedia: vi.fn(async () => ({ getTracks: () => [track] })) },
  });
});

describe("the recorder", () => {
  it("hands back the recording and lets go of the mic", async () => {
    const { result } = renderHook(() => useRecorder());

    await act(async () => void (await result.current.start()));
    expect(result.current.isRecording).toBe(true);

    await act(async () => void (await result.current.stop()));
    expect(result.current.isRecording).toBe(false);
    expect(track.stop).toHaveBeenCalled();
  });

  it("lets go even when the recording already ended on its own", async () => {
    const { result } = renderHook(() => useRecorder());

    await act(async () => void (await result.current.start()));
    // What the browser does when the tracks end without us asking.
    media.state = "inactive";

    await act(async () => void (await result.current.stop()));
    expect(result.current.isRecording).toBe(false);
    expect(track.stop).toHaveBeenCalled();
  });
});
