import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TurnFeedback } from "./Chat";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

const api = vi.hoisted(() => ({ sendFeedback: vi.fn(() => Promise.resolve()) }));
vi.mock("@/api/chat", () => ({ sendFeedback: api.sendFeedback }));

describe("TurnFeedback", () => {
  it("posts the down on click — before any reason — then the reason as a second post", async () => {
    render(
      <LanguageProvider>
        <TurnFeedback requestId="req-9" />
      </LanguageProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: en.chat.feedbackDown }));
    expect(api.sendFeedback).toHaveBeenCalledWith("req-9");

    const input = await screen.findByPlaceholderText(en.chat.feedbackReasonPlaceholder);
    fireEvent.change(input, { target: { value: "wrong city" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(api.sendFeedback).toHaveBeenCalledWith("req-9", "wrong city");
    expect(screen.getByText(en.chat.feedbackThanks)).toBeInTheDocument();
  });

  it("does not post an abandoned empty reason", () => {
    render(
      <LanguageProvider>
        <TurnFeedback requestId="req-10" />
      </LanguageProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: en.chat.feedbackDown }));
    const input = screen.getByPlaceholderText(en.chat.feedbackReasonPlaceholder);
    fireEvent.keyDown(input, { key: "Enter" });

    expect(api.sendFeedback).toHaveBeenCalledTimes(1);
    expect(api.sendFeedback).toHaveBeenCalledWith("req-10");
  });
});
