import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ShareLocation } from "./Chat";
import { rememberLocation, storedLocation } from "@/api/chat";
import { translations } from "@/i18n/translations";
import { renderWith } from "@/test/renderWith";

const en = translations.en;

vi.mock("@/api/chat", async (original) => ({
  ...(await original<typeof import("@/api/chat")>()),
  sendFeedback: vi.fn(),
}));

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

describe("the remembered location", () => {
  it("survives to the next visit, to about 100 m", () => {
    expect(storedLocation()).toBeNull();
    rememberLocation({ latitude: 45.69812, longitude: 9.67734 });
    expect(storedLocation()).toEqual({ latitude: 45.698, longitude: 9.677 });
  });

  it("is replaced by a newer one", () => {
    rememberLocation({ latitude: 45.7, longitude: 9.67 });
    rememberLocation({ latitude: 41.39, longitude: 2.17 });
    expect(storedLocation()).toEqual({ latitude: 41.39, longitude: 2.17 });
  });

  it("ignores a broken entry", () => {
    localStorage.setItem("laiive-location", "{not json");
    expect(storedLocation()).toBeNull();
  });
});
