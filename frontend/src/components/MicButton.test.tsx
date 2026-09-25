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

/** `ghost` on both surfaces — it is the only variant the Composer passes. */
function renderMic(disabled = false, onRecordingChange = vi.fn()) {
  render(
    <LanguageProvider>
      <MicButton
        variant="ghost"
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

describe("the mic in the composer's field", () => {
  it("sits unfilled and unaccented at rest", () => {
    const mic = renderMic();
    expect(mic.className).toContain("text-ink-dim");
    expect(mic.className).not.toContain("bg-primary");
    expect(mic.className).not.toContain("bg-pro-accent");
  });

  it("rests when the caller says so", () => {
    expect(renderMic(true)).toBeDisabled();
  });

  it("fills amber and breathes while the mic is live", () => {
    recorder.state.isRecording = true;
    const mic = renderMic();
    expect(mic.className).toContain("bg-secondary");
    expect(mic.className).toContain("text-secondary-foreground");
    expect(mic.className).toContain("animate-pulse");
    // The variant's own hover is a separate key to tailwind-merge, so it
    // survives unless the recording state restates it — and cream on amber
    // is the 3.45:1 pair the brand rules ban.
    expect(mic.className).toContain("hover:text-secondary-foreground");
    expect(mic.className).not.toMatch(/hover:text-(foreground|pro-fg)\b/);
  });

  it("tells the composer when the recording starts, so the field can show it", () => {
    const onRecordingChange = vi.fn();
    recorder.state.isRecording = true;
    renderMic(false, onRecordingChange);
    expect(onRecordingChange).toHaveBeenCalledWith(true);
  });

  it("keeps a recording in progress stoppable even while resting", () => {
    // The mic used to unmount when a turn started, which released the tracks.
    // Now it stays mounted and disabled — but a disabled button over a live
    // recording is a trapped recording, so recording overrides disabled.
    recorder.state.isRecording = true;
    expect(renderMic(true)).toBeEnabled();
  });
});
