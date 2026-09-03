import type { EventDraft } from "@shared/protocol";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EventForm } from "./EventForm";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

const api = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("@/api/client", () => ({
  apiFetch: api.fetch,
  ApiError: class extends Error {},
}));

const RAZZ = {
  uid: "v1",
  name: "Razzmatazz",
  venue_type: "club",
  address: "Carrer dels Almogàvers 122",
  city: "Barcelona",
};
const NO_ADDRESS = {
  uid: "v2",
  name: "Sala Nova",
  venue_type: null,
  address: null,
  city: "Barcelona",
};

function jsonResponse(body: unknown): Response {
  return { json: async () => body } as Response;
}

/** Complete except the venue and address — what each spec is about. */
const DRAFT: EventDraft = {
  name: "Jazz Night",
  artists: ["Ana Beck Quartet"],
  start_at: "2026-09-01T21:00",
  city: "Barcelona",
  price_min: 12,
};

function renderForm(onSave = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrap = (draft: EventDraft) => (
    <QueryClientProvider client={client}>
      <LanguageProvider>
        <EventForm draft={draft} missing={[]} onSave={onSave} saving={false} />
      </LanguageProvider>
    </QueryClientProvider>
  );
  const { rerender } = render(wrap(DRAFT));
  return { onSave, refresh: (draft: EventDraft) => rerender(wrap(draft)) };
}

/** The correction receipt and the doubt marker, rendered on their own. */
function renderWithChecks(
  corrections: { field: string; before: string; after: string; why: string }[],
  doubted: string[] = [],
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <LanguageProvider>
        <EventForm
          draft={DRAFT}
          missing={[]}
          corrections={corrections}
          doubted={doubted}
          onSave={vi.fn()}
          saving={false}
        />
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.fetch.mockReset();
  api.fetch.mockResolvedValue(jsonResponse({ venues: [RAZZ, NO_ADDRESS] }));
});

describe("the venue combobox", () => {
  it("offers graph venues while typing, and a pick answers the address itself", async () => {
    const user = userEvent.setup();
    const { onSave } = renderForm();

    await user.type(screen.getByLabelText(/^venue/i), "razz");
    const listbox = await screen.findByRole("listbox", {
      name: en.form.venueSuggestionsAria,
    });
    await user.click(within(listbox).getByRole("option", { name: /Razzmatazz/ }));

    expect(screen.getByLabelText(/^venue/i)).toHaveValue("Razzmatazz");
    // The graph already knows the street: no address input, the on-file line.
    expect(screen.queryByLabelText(/^address/i)).toBeNull();
    expect(screen.getByText(new RegExp(en.form.addressOnFile))).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: en.form.publish }));
    // The on-file address rides the draft (the walk must see it as settled);
    // the uid rides beside it.
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ venue: "Razzmatazz", address: RAZZ.address }),
      "v1",
    );

    // The lookup carried the fragment and the city scope.
    const calledUrl = api.fetch.mock.calls[0]![0] as string;
    expect(calledUrl).toContain("/api/venues?q=razz");
    expect(calledUrl).toContain("city=Barcelona");
  });

  it("can be driven by keyboard alone", async () => {
    const user = userEvent.setup();
    renderForm();

    const input = screen.getByLabelText(/^venue/i);
    await user.type(input, "sala");
    await screen.findByRole("listbox", { name: en.form.venueSuggestionsAria });

    await user.keyboard("{ArrowDown}{Enter}");
    expect(input).toHaveValue("Sala Nova");
    // Enter picked instead of submitting — the address is still open.
    expect(screen.getByLabelText(/^address/i)).toBeInTheDocument();
  });

  it("keeps asking for the address when the picked venue has none on file", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText(/^venue/i), "sala");
    await user.click(await screen.findByRole("option", { name: /Sala Nova/ }));

    expect(screen.getByLabelText(/^address/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.form.publish })).toBeDisabled();
  });

  it("keeps the pick when the server merely respells the venue", async () => {
    // Every turn re-extracts the whole conversation, and the server never saw
    // the pick — it respells freely. A casing change must not cost the uid
    // and re-ask an address the graph already answered.
    const user = userEvent.setup();
    const { refresh } = renderForm();

    await user.type(screen.getByLabelText(/^venue/i), "razz");
    await user.click(await screen.findByRole("option", { name: /Razzmatazz/ }));
    refresh({ ...DRAFT, venue: "  RAZZMATAZZ " });

    expect(screen.queryByLabelText(/^address/i)).toBeNull();
    expect(screen.getByText(new RegExp(en.form.addressOnFile))).toBeInTheDocument();
  });

  it("keeps the pick when the server re-emits only the fragment that found it", async () => {
    // "razz" is what the promoter chatted, so it is what re-extraction keeps
    // emitting; the pick's canonical name wins the field back.
    const user = userEvent.setup();
    const { refresh } = renderForm();

    await user.type(screen.getByLabelText(/^venue/i), "razz");
    await user.click(await screen.findByRole("option", { name: /Razzmatazz/ }));
    refresh({ ...DRAFT, venue: "razz" });

    expect(screen.getByLabelText(/^venue/i)).toHaveValue("Razzmatazz");
    expect(screen.getByText(new RegExp(en.form.addressOnFile))).toBeInTheDocument();
  });

  it("drops the pick when the server names a different venue", async () => {
    const user = userEvent.setup();
    const { refresh } = renderForm();

    await user.type(screen.getByLabelText(/^venue/i), "razz");
    await user.click(await screen.findByRole("option", { name: /Razzmatazz/ }));
    refresh({ ...DRAFT, venue: "Sala Apolo" });

    expect(screen.getByLabelText(/^address/i)).toBeInTheDocument();
  });

  it("gives back the typed address when the promoter un-picks", async () => {
    // A pick with an on-file address replaces whatever was typed; dropping
    // the pick must return the promoter's own words, not an empty field.
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText(/^address/i), "Via Roma 1");
    await user.type(screen.getByLabelText(/^venue/i), "razz");
    await user.click(await screen.findByRole("option", { name: /Razzmatazz/ }));
    expect(screen.queryByLabelText(/^address/i)).toBeNull();

    await user.type(screen.getByLabelText(/^venue/i), "!");
    expect(screen.getByLabelText(/^address/i)).toHaveValue("Via Roma 1");
  });

  it("publishes a hand-typed venue with no uid at all", async () => {
    api.fetch.mockResolvedValue(jsonResponse({ venues: [] }));
    const user = userEvent.setup();
    const { onSave } = renderForm();

    await user.type(screen.getByLabelText(/^venue/i), "Nuovo Posto");
    await user.type(screen.getByLabelText(/^address/i), "Via Roma 1");
    await user.click(screen.getByRole("button", { name: en.form.publish }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ venue: "Nuovo Posto", address: "Via Roma 1" }),
      null,
    );
  });
});


describe("what the correction layer changed", () => {
  it("shows the old value beside the new one", () => {
    // The old value is the whole point: a receipt saying only "we changed the
    // city" gives the promoter nothing to disagree with.
    renderWithChecks([
      { field: "city", before: "barcelona", after: "Barcelona", why: "spelling from the map" },
    ]);
    expect(screen.getByText("barcelona")).toBeInTheDocument();
    expect(screen.getByText("Barcelona")).toBeInTheDocument();
    expect(screen.getByText(en.form.correctedTitle)).toBeInTheDocument();
  });

  it("says nothing when nothing was changed", () => {
    renderWithChecks([]);
    expect(screen.queryByText(en.form.correctedTitle)).not.toBeInTheDocument();
  });

  it("marks a field the chat asked about", () => {
    renderWithChecks([], ["start_at"]);
    expect(screen.getByText(en.form.checkThis)).toBeInTheDocument();
  });

  it("marks nothing when there is no doubt", () => {
    renderWithChecks([]);
    expect(screen.queryByText(en.form.checkThis)).not.toBeInTheDocument();
  });
});
