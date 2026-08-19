# 02 — Who owns a venue, an artist, an event

Decided with the owner on 2026-08-19, after looking at how Eventbrite, Bandsintown
and the promoter-vetting literature handle the same problem.

## The problem

A pro account owned things personally: `owner_id` on the Neo4j node, stamped
`ON CREATE`, first writer wins. Three consequences, all wrong:

- A venue with three staff cannot exist. Whoever typed its name first owns it forever,
  and there is no way to add the second person or remove the one who left.
- The two places that *look* like ownership are fiction. `public.ownerships` was read
  and written by no code and held zero rows; `promoter_profiles.managed_venues` is a
  free-text list a user types, connected to no graph uid.
- Nothing is enforced anywhere, because there is nothing to enforce: the pusher is
  create-only.

## What other platforms do

**Teams are organizations, not people.** Eventbrite's unit is an organization; members
are invited by email, keep their own credentials, and hold roles. The stated reason is
the one that matters here: it is what stops a venue sharing one login.

**Entities exist before anyone owns them, and are claimed.** On Bandsintown you search
for your venue, find the page that already exists, and claim it. Verification is tiered
by cost — social sign-in or an SMS to the venue's *publicly listed* number resolves in
seconds; anything else is a manual request with evidence, answered in a few days. An
unresolved claim shows as "Pending verification" rather than blocking the account.

**Vetting a promoter is evidence, not paperwork.** A website, active socials, past
events, no history of cancellations. Things a reviewer can check in five minutes.

## The decisions

| decision | choice |
| --- | --- |
| Ownership unit | **Organizations with members** — kind `venue` / `artist` / `promoter`, roles `owner` / `admin` / `member`, invitations by email |
| Claiming | **Self-declared now.** A claim on an existing entity succeeds immediately with `verified = false`. Review comes later; supply density matters more than gatekeeping today |
| Listing at someone else's venue | **Unrestricted.** Anyone with a pro account publishes anywhere; the venue is an address, not a permission |
| Sequencing | Data model now, screens after |

The third decision is the one that shapes everything else: **ownership governs who may
edit a record, never who may create one.** No confirmation flow, no dispute arbitration,
no venue veto. That is a large amount of machinery not built.

## The model

`supabase/migrations/20260819000011_organizations.sql`.

- **`organizations`** — kind, display name, website, phone, contact email. The last three
  double as the evidence a reviewer checks when claims start being verified.
- **`organization_members`** — `(org_id, user_id, role)`. `owner` and `admin` may change
  the organization and remove people; `member` may not.
- **`organization_invitations`** — email, role, `token_hash`, expiry. The table stores a
  hash, never the token: the token exists only inside the link that was emailed, so a
  leaked row cannot be redeemed.
- **`entity_ownership`** — `(org_id, entity_type, entity_uid, basis, verified)`. `basis`
  is `created` (you published it — verified by definition, enforced by a check
  constraint) or `claimed` (a statement about something that already existed). Not unique
  per entity: a venue and its resident promoter can both hold a claim on the same room.

RLS throughout. Membership checks go through two `SECURITY DEFINER` helpers because a
policy on `organization_members` that queries `organization_members` recurses; the
definer reads without re-entering RLS. `EXECUTE` is revoked from `anon`/`authenticated`,
matching the hardening migration.

One policy is worth naming: **"founder takes the owner seat"** lets a user insert exactly
one membership row — their own, as `owner`, and only while the organization has no members
at all. Without it the person who just created an organization could never join it, and
with anything looser they could promote themselves into someone else's.

`public.ownerships` is dropped (zero rows, no readers). `promoter_profiles` survives
because the account page still reads it, and goes when the pro screens are rebuilt.

## What this does not do yet

The write side is missing on purpose. Recording "org X owns event Y" at publish time
needs the publisher to *have* an org, and creating one is a screen that does not exist.
Building the write path first would produce exactly what `ownerships` was — DDL nothing
writes.

So the order is: **org creation and the team screen → publish records ownership → edit and
delete endpoints guarded by membership → claiming a venue → verification review.**

## Pro onboarding — the fields to collect

Common practice is minimal and progressive: enough to identify and reach the account,
nothing that only matters once money moves.

At the point of becoming a pro:

- **What you are** — venue, artist/group, or promoter. Decides the organization's kind.
- **Organization display name** — the public one.
- **Your role in it** — owner, manager, booker, member. Free text is fine; it is context
  for a future reviewer, not a permission.
- **Contact email** — pre-filled from the Google account, must be reachable. Private.
- **Phone** — optional now, and the thing that makes SMS verification possible later.
- **Website or social profile** — optional now, and the single most useful piece of
  evidence when claims start being reviewed.

Deliberately not collected: tax or legal identity. It has no use until laiive handles
money, and holding it is a liability under GDPR. Keep the public profile (name, website,
socials) separate from the private contact details (email, phone) from the start, because
separating them later means migrating consent as well as data.
