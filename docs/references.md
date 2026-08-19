# References

External sources consulted before a decision, kept for the next person and for any
question later about *why* something was built this way. Dated, because a vendor's
documentation changes under the same URL and "what it said in August 2026" is the part
that matters afterwards.

Add a row when research informs a decision. Link the decision, not just the topic.

## Ownership, teams and claiming (2026-08-19)

Informed `docs/roadmap/02-ownership.md` and migration `20260819000011_organizations.sql`.

| source | what it settled | accessed |
| --- | --- | --- |
| [Eventbrite — Manage roles and permissions](https://www.eventbrite.com/help/en-us/articles/509534/how-to-manage-roles-and-permissions/) | The unit is an *organization*, not a person; members are invited by email, keep their own credentials, and hold roles. Their stated reason — it is what stops a team sharing one login — is the reason laiive adopted it. | 2026-08-19 |
| [Eventbrite — Organization settings](https://www.eventbrite.com/help/en-us/articles/103302/how-to-manage-your-organization-settings/) | An organization can hold several organizer profiles; team management sits at organization level. | 2026-08-19 |
| [Bandsintown — Claiming and adding venue pages](https://help.venues.bandsintown.com/en/articles/8486862-claiming-adding-venue-pages) | Entities exist *before* anyone owns them and are claimed afterwards. Verification is tiered by cost: social sign-in or SMS to the venue's publicly listed number is instant, manual review takes 3–5 business days. | 2026-08-19 |
| [Bandsintown — Claim an existing artist page](https://help.artists.bandsintown.com/en/articles/7039351-claim-an-existing-artist-page) | The same claim-then-verify flow for artists, and the "Pending verification" state that does not block the account meanwhile. | 2026-08-19 |
| [Ticket Fairy — Vetting promoters and event clients](https://www.ticketfairy.com/blog/trust-but-verify-vetting-promoters-event-clients-to-protect-your-venue-in-2026) | What a reviewer actually checks in a promoter: website, active socials, past events, no history of cancellations. Evidence, not paperwork — which is why laiive collects website and phone and not tax identity. | 2026-08-19 |

## Auth branding on the Google consent screen (2026-08-19)

Informed `DEPLOY.md` §5 (auth branding).

| source | what it settled | accessed |
| --- | --- | --- |
| [Supabase — Login with Google](https://supabase.com/docs/guides/auth/social-login/auth-google) | Google shows the root domain of the callback URL, so an unbranded Supabase project shows `<project-id>.supabase.co`. Supabase's own words: it "does not inspire trust and can make your application more susceptible to successful phishing attempts". Two fixes: a custom domain, and brand verification of the app name and logo, which is not automatic and takes a few business days. | 2026-08-19 |
| [Supabase — Custom domains](https://supabase.com/docs/guides/platform/custom-domains) | A paid add-on on a paid plan. Needs a CNAME to the project domain plus a TXT at `_acme-challenge.<domain>`. Both the old and the new callback URL must be registered with each OAuth provider *before* activation, or sign-in breaks at the switch. | 2026-08-19 |
| [supabase/supabase#33387](https://github.com/supabase/supabase/issues/33387) | The same complaint filed as a bug: the consent screen shows the project URL rather than the configured app name. Confirms it is behaviour, not misconfiguration. | 2026-08-19 |

## A note on using these

They are vendor documentation and vendor-adjacent blogs, not legal advice. Where a
decision has a legal dimension — what personal data is collected at pro signup, how long
it is kept, what is shown publicly — the sources above informed the *shape*, and the
GDPR judgement was made separately and deliberately: collect only what has a use now,
keep public profile and private contact separable from the start.
