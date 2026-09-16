import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

// The mic owns the recorder; a spec that wants the field's meter has to put a
// recording in progress from here.
const recorder = vi.hoisted(() => ({
  state: { isRecording: false, start: vi.fn(), stop: vi.fn() },
}));
vi.mock("@/audio/useRecorder", () => ({ useRecorder: () => recorder.state }));

beforeEach(() => {
  recorder.state.isRecording = false;
});

function renderComposer(props: Partial<Parameters<typeof Composer>[0]> = {}) {
  const handlers = {
    onChange: vi.fn(),
    onSend: vi.fn(),
    onStop: vi.fn(),
    transcribe: vi.fn(),
    onTranscript: vi.fn(),
  };
  const { container } = render(
    <LanguageProvider>
      <Composer
        value=""
        accent="consumer"
        placeholder={en.chat.placeholder}
        {...handlers}
        {...props}
      />
    </LanguageProvider>,
  );
  return { ...handlers, container };
}

describe("the shared composer", () => {
  it("keeps send disabled until there is something to send", () => {
    renderComposer();
    expect(screen.getByRole("button", { name: en.chat.send })).toBeDisabled();
  });

  it("sends on click and on Enter", async () => {
    const user = userEvent.setup();
    const { onSend } = renderComposer({ value: "jazz tonight" });

    await user.click(screen.getByRole("button", { name: en.chat.send }));
    await user.type(screen.getByRole("textbox"), "{Enter}");
    expect(onSend).toHaveBeenCalledTimes(2);
  });

  it("swallows Enter on an empty field", async () => {
    const user = userEvent.setup();
    const { onSend } = renderComposer();

    await user.type(screen.getByRole("textbox"), "{Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("swaps send for stop while streaming and rests the mic", async () => {
    const user = userEvent.setup();
    const { onSend, onStop } = renderComposer({ value: "jazz tonight", isStreaming: true });

    expect(screen.queryByRole("button", { name: en.chat.send })).toBeNull();
    expect(screen.getByRole("button", { name: en.voice.speak })).toBeDisabled();

    // Enter mid-stream must not queue a second turn.
    await user.type(screen.getByRole("textbox"), "{Enter}");
    expect(onSend).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: en.chat.stop }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("waits whole while busy without a stream — ingest, publish", () => {
    renderComposer({ value: "jazz tonight", disabled: true });
    expect(screen.getByRole("button", { name: en.chat.send })).toBeDisabled();
    expect(screen.getByRole("button", { name: en.voice.speak })).toBeDisabled();
  });

  it("keeps the fuchsia on the send alone on the consumer side", () => {
    renderComposer({ value: "x" });
    expect(screen.getByRole("button", { name: en.chat.send }).className).toContain("bg-primary");
    // The mic moved inside the field, so it carries no frame of its own now —
    // what matters is still that it never wears the send's accent.
    const mic = screen.getByRole("button", { name: en.voice.speak });
    expect(mic.className).not.toContain("bg-primary");
    expect(mic.className).not.toContain("border-primary");
  });

  it("keeps the cyan on the send alone on pro", () => {
    renderComposer({ value: "x", accent: "pro", placeholder: en.pro.placeholder });
    expect(screen.getByRole("button", { name: en.pro.send }).className).toContain(
      "bg-pro-accent",
    );
    const mic = screen.getByRole("button", { name: en.voice.speak });
    expect(mic.className).not.toContain("bg-pro-accent");
    expect(mic.className).not.toContain("border-pro-accent");
  });

  it("renders an attach slot only when the surface brings one", () => {
    renderComposer({ attachSlot: <button type="button" aria-label="bring a flyer" /> });
    expect(screen.getByRole("button", { name: "bring a flyer" })).toBeInTheDocument();
  });

  it("has no attach control of its own", () => {
    renderComposer();
    expect(screen.queryByRole("button", { name: en.pro.attach })).toBeNull();
  });

  it("puts attach and mic inside the field and leaves the send outside", () => {
    // Messenger shape. Reading order is field, then the two controls sitting
    // in it, then the send — which is also the tab order, and the only control
    // outside the pill is the one that commits.
    const { container } = renderComposer({
      attachSlot: <button type="button" aria-label={en.pro.attach} />,
    });
    const row = [...container.querySelectorAll("button, textarea")].map(
      (element) => element.getAttribute("aria-label"),
    );
    expect(row).toEqual([en.chat.placeholder, en.pro.attach, en.voice.speak, en.chat.send]);

    const field = screen.getByRole("textbox");
    const inField = field.parentElement as HTMLElement;
    expect(inField).toContainElement(screen.getByRole("button", { name: en.pro.attach }));
    expect(inField).toContainElement(screen.getByRole("button", { name: en.voice.speak }));
    expect(inField).not.toContainElement(screen.getByRole("button", { name: en.chat.send }));
  });

  it("sends on Enter without leaving the newline behind", async () => {
    const user = userEvent.setup();
    const { onSend, onChange } = renderComposer({ value: "jazz tonight" });

    await user.type(screen.getByRole("textbox"), "{Enter}");
    expect(onSend).toHaveBeenCalledTimes(1);
    // The field is a textarea now: without preventDefault the turn goes out
    // and a stray "\n" stays in the box.
    expect(onChange).not.toHaveBeenCalled();
  });

  it("breaks the line on shift+Enter instead of sending", async () => {
    const user = userEvent.setup();
    const { onSend, onChange } = renderComposer({ value: "jazz tonight" });

    await user.type(screen.getByRole("textbox"), "{Shift>}{Enter}{/Shift}");
    expect(onSend).not.toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith("jazz tonight\n");
  });

  it("keeps the send accent while it waits, rather than going grey", () => {
    renderComposer();
    const send = screen.getByRole("button", { name: en.chat.send });
    expect(send).toBeDisabled();
    expect(send.className).toContain("disabled:bg-primary/45");
    expect(send.className).not.toContain("disabled:bg-card");
  });

  it("draws the meter in the field only while the mic is live", () => {
    expect(renderComposer().container.querySelector("[data-testid=recording-waveform]"))
      .toBeNull();

    recorder.state.isRecording = true;
    const { container } = renderComposer();
    const meter = container.querySelector("[data-testid=recording-waveform]");
    expect(meter).not.toBeNull();
    // Bars, not letters — and the same amber the live mic wears.
    expect(meter?.textContent).toMatch(/^[▁▂▃▄▅▆▇]+$/u);
    expect(meter?.className).toContain("text-secondary");
  });
});
