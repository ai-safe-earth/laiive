import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MicButton } from "./MicButton";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

// Mutable recorder state, so a spec can put a recording in progress without
// reaching for real media devices.
const recorder = vi.hoisted(() => ({
  state: { isRecording: false, start: vi.fn(), stop: vi.fn() },
}));
vi.mock("@/audio/useRecorder", () => ({ useRecorder: () => recorder.state }));

beforeEach(() => {
  recorder.state.isRecording = false;
});

function renderMic(variant: "fuchsiaOutline" | "cyanOutline", disabled = false) {
  render(
    <LanguageProvider>
      <MicButton
        variant={variant}
        disabled={disabled}
        transcribe={vi.fn()}
        onTranscript={vi.fn()}
      />
    </LanguageProvider>,
  );
  return screen.getByRole("button", {
    name: recorder.state.isRecording ? en.voice.stop : en.voice.speak,
  });
}

describe("the mic's outline variants", () => {
  it("outlines fuchsia for the consumer composer", () => {
    const mic = renderMic("fuchsiaOutline");
    expect(mic.className).toContain("border-primary");
    expect(mic.className).toContain("bg-transparent");
  });

  it("outlines cyan for the pro composer", () => {
    const mic = renderMic("cyanOutline");
    expect(mic.className).toContain("border-pro-accent");
    expect(mic.className).toContain("bg-transparent");
  });

  it("rests when the caller says so", () => {
    expect(renderMic("fuchsiaOutline", true)).toBeDisabled();
  });

  it("keeps a recording in progress stoppable even while resting", () => {
    // The mic used to unmount when a turn started, which released the tracks.
    // Now it stays mounted and disabled — but a disabled button over a live
    // recording is a trapped recording, so recording overrides disabled.
    recorder.state.isRecording = true;
    expect(renderMic("fuchsiaOutline", true)).toBeEnabled();
  });
});
