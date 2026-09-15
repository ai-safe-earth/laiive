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

function renderMic(
  variant: "neutralOutline" | "proNeutralOutline",
  disabled = false,
  onRecordingChange = vi.fn(),
) {
  render(
    <LanguageProvider>
      <MicButton
        variant={variant}
        disabled={disabled}
        transcribe={vi.fn()}
        onTranscript={vi.fn()}
        onRecordingChange={onRecordingChange}
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
    // Filled on this surface, unlike the consumer mic: the promoter ground
    // carries the watermark, and a transparent pill reads as a hole in it.
    const mic = renderMic("proNeutralOutline");
    expect(mic.className).toContain("border-pro-border");
    expect(mic.className).toContain("bg-pro-control");
    expect(mic.className).not.toContain("border-pro-accent");
  });

  it("rests when the caller says so", () => {
    expect(renderMic("neutralOutline", true)).toBeDisabled();
  });

  // Both surfaces: the amber has to beat the pro variant's own fill, and only
  // tailwind-merge decides that.
  it.each(["neutralOutline", "proNeutralOutline"] as const)(
    "fills amber and breathes while the mic is live (%s)",
    (variant) => {
      recorder.state.isRecording = true;
      const mic = renderMic(variant);
      expect(mic.className).toContain("bg-secondary");
      expect(mic.className).toContain("text-secondary-foreground");
      expect(mic.className).toContain("animate-pulse");
      // The variant's own hover is a separate key to tailwind-merge, so it
      // survives unless the recording state restates it — and cream on amber
      // is the 3.45:1 pair the brand rules ban.
      expect(mic.className).toContain("hover:text-secondary-foreground");
      expect(mic.className).not.toMatch(/hover:text-(foreground|pro-fg)\b/);
    },
  );

  it("tells the composer when the recording starts, so the field can show it", () => {
    const onRecordingChange = vi.fn();
    recorder.state.isRecording = true;
    renderMic("neutralOutline", false, onRecordingChange);
    expect(onRecordingChange).toHaveBeenCalledWith(true);
  });

  it("keeps a recording in progress stoppable even while resting", () => {
    // The mic used to unmount when a turn started, which released the tracks.
    // Now it stays mounted and disabled — but a disabled button over a live
    // recording is a trapped recording, so recording overrides disabled.
    recorder.state.isRecording = true;
    expect(renderMic("neutralOutline", true)).toBeEnabled();
  });
});
