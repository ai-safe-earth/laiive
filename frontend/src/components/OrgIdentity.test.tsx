import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OrgIdentity } from "./OrgIdentity";
import { becomePromoter } from "@/auth/becomePromoter";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

const auth = vi.hoisted(() => ({ state: { user: { id: "u1" }, role: "user" } }));
vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => auth.state }));

const create = vi.hoisted(() => vi.fn());
vi.mock("@/api/organizations", () => ({
  useCreateOrg: () => ({ mutateAsync: create, isPending: false }),
}));
vi.mock("@/api/profile", () => ({ usePromoterProfile: () => ({ data: null }) }));
vi.mock("@/auth/becomePromoter", () => ({ becomePromoter: vi.fn() }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const grant = vi.mocked(becomePromoter);

beforeEach(() => {
  auth.state = { user: { id: "u1" }, role: "user" };
  create.mockReset().mockResolvedValue("org-1");
  grant.mockReset().mockResolvedValue(undefined);
});

async function fillAndSubmit() {
  render(
    <LanguageProvider>
      <OrgIdentity />
    </LanguageProvider>,
  );
  await userEvent.type(screen.getByPlaceholderText(en.org.namePlaceholder), "Razzmatazz");
  await userEvent.selectOptions(screen.getByLabelText(en.org.relation), "owner");
  await userEvent.click(screen.getByRole("button", { name: en.org.create }));
}

describe("the identity step as the promoter door", () => {
  it("grants the role before founding the organisation for a plain user", async () => {
    await fillAndSubmit();

    // Order matters: create_organization refuses a caller whose user_roles
    // row still says 'user', and the grant is what flips that row.
    expect(grant).toHaveBeenCalledWith("u1", "Razzmatazz");
    expect(grant.mock.invocationCallOrder[0]).toBeLessThan(create.mock.invocationCallOrder[0]!);
    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ display_name: "Razzmatazz", relation: "owner" }),
    );
  });

  it("skips the grant for an account that already is one", async () => {
    auth.state = { user: { id: "u1" }, role: "pro" };
    await fillAndSubmit();
    expect(grant).not.toHaveBeenCalled();
    expect(create).toHaveBeenCalledTimes(1);
  });

  it("founds nothing when the grant fails", async () => {
    grant.mockRejectedValue(new Error("no"));
    await fillAndSubmit();
    expect(create).not.toHaveBeenCalled();
  });
});
