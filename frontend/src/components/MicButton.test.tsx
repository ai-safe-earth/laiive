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

function renderMic(variant: "neutralOutline" | "proNeutralOutline", disabled = false) {
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
  it("outlines warm-neutral for the consumer composer, no accent", () => {
    const mic = renderMic("neutralOutline");
    expect(mic.className).toContain("border-field-border");
    expect(mic.className).toContain("bg-transparent");
    expect(mic.className).not.toContain("border-primary");
  });

  it("outlines pro-neutral for the pro composer, no accent", () => {
    const mic = renderMic("proNeutralOutline");
    expect(mic.className).toContain("border-pro-border");
    expect(mic.className).toContain("bg-transparent");
    expect(mic.className).not.toContain("border-pro-accent");
  });

  it("rests when the caller says so", () => {
    expect(renderMic("neutralOutline", true)).toBeDisabled();
  });

  it("keeps a recording in progress stoppable even while resting", () => {
    // The mic used to unmount when a turn started, which released the tracks.
    // Now it stays mounted and disabled — but a disabled button over a live
    // recording is a trapped recording, so recording overrides disabled.
    recorder.state.isRecording = true;
    expect(renderMic("neutralOutline", true)).toBeEnabled();
  });
});
