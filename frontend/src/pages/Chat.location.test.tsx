import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ShareLocation } from "./Chat";
import { translations } from "@/i18n/translations";
import { renderWith } from "@/test/renderWith";

const en = translations.en;

vi.mock("@/api/chat", () => ({ sendFeedback: vi.fn() }));

const geolocation = (answer: (ok: PositionCallback, fail: PositionErrorCallback) => void) =>
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition: answer },
  });

describe("ShareLocation", () => {
  afterEach(() => {
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
  });

  it("hands the position over when the browser shares it", () => {
    geolocation((ok) => ok({ coords: { latitude: 45.7, longitude: 9.67 } } as GeolocationPosition));
    const onShared = vi.fn();
    renderWith(<ShareLocation onShared={onShared} />);

    fireEvent.click(screen.getByRole("button", { name: en.chat.shareLocation }));
    expect(onShared).toHaveBeenCalledWith({ latitude: 45.7, longitude: 9.67 });
  });

  it("words the once-per-session offer as an offer", () => {
    geolocation((ok) => ok({ coords: { latitude: 45.7, longitude: 9.67 } } as GeolocationPosition));
    const onShared = vi.fn();
    renderWith(<ShareLocation label={en.chat.offerLocation} onShared={onShared} />);

    fireEvent.click(screen.getByRole("button", { name: en.chat.offerLocation }));
    expect(onShared).toHaveBeenCalledOnce();
  });

  it("says to type a city when the browser refuses", () => {
    geolocation((_, fail) => fail({ code: 1 } as GeolocationPositionError));
    const onShared = vi.fn();
    renderWith(<ShareLocation onShared={onShared} />);

    fireEvent.click(screen.getByRole("button", { name: en.chat.shareLocation }));
    expect(onShared).not.toHaveBeenCalled();
    expect(screen.getByText(en.chat.locationDenied)).toBeInTheDocument();
  });
});
