import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

function renderComposer(props: Partial<Parameters<typeof Composer>[0]> = {}) {
  const handlers = {
    onChange: vi.fn(),
    onSend: vi.fn(),
    onStop: vi.fn(),
    transcribe: vi.fn(),
    onTranscript: vi.fn(),
  };
  render(
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
  return handlers;
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

  it("wears fuchsia on the consumer side", () => {
    renderComposer({ value: "x" });
    expect(screen.getByRole("button", { name: en.chat.send }).className).toContain("bg-primary");
    expect(screen.getByRole("button", { name: en.voice.speak }).className).toContain(
      "border-primary",
    );
  });

  it("wears cyan on pro", () => {
    renderComposer({ value: "x", accent: "pro", placeholder: en.pro.placeholder });
    expect(screen.getByRole("button", { name: en.pro.send }).className).toContain(
      "bg-pro-accent",
    );
    expect(screen.getByRole("button", { name: en.voice.speak }).className).toContain(
      "border-pro-accent",
    );
  });

  it("renders an attach slot only when the surface brings one", () => {
    renderComposer({ attachSlot: <button type="button" aria-label="bring a flyer" /> });
    expect(screen.getByRole("button", { name: "bring a flyer" })).toBeInTheDocument();
  });

  it("has no attach control of its own", () => {
    renderComposer();
    expect(screen.queryByRole("button", { name: en.pro.attach })).toBeNull();
  });
});
