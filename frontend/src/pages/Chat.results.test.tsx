import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EventCard } from "@shared/protocol";
import { ResultCards } from "./Chat";
import { translations } from "@/i18n/translations";
import { renderWith } from "@/test/renderWith";

const en = translations.en;

vi.mock("@/api/chat", () => ({ sendFeedback: vi.fn() }));

const cards = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ uid: `e${i}`, name: `Gig ${i}` }) as EventCard);
const render = (card: EventCard) => <p key={card.uid}>{card.name}</p>;

describe("ResultCards", () => {
  it("shows ten, then the next page on click", () => {
    renderWith(<ResultCards events={cards(14)} capped={false} render={render} />);
    expect(screen.queryByText("Gig 10")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: en.chat.showMore(4, "14") }));
    expect(screen.getByText("Gig 13")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByText(en.chat.manyResults("14"))).not.toBeInTheDocument();
  });

  it("counts a capped long list as 50+ and suggests narrowing it", () => {
    renderWith(<ResultCards events={cards(50)} capped render={render} />);
    expect(screen.getByText(en.chat.manyResults("50+"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.chat.showMore(10, "50+") })).toBeInTheDocument();
  });

  it("a short list has no button and no hint", () => {
    renderWith(<ResultCards events={cards(3)} capped={false} render={render} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
