---
status: todo
step: ownership
next: admin verify/revoke route on the gateway
---
# Ownership E3: verification and edit forms

Model decided 2026-08-19 (`supabase/migrations/20260819000011_organizations.sql`):
organizations with members (owner/admin/member), invitations by hashed token,
`entity_ownership` with basis `created` or `claimed`. Ownership governs who may edit a
record, never who may create one. Claims are self-declared, `verified = false`.
Orgs, claims, publish-records-ownership and the claimed-card tick UI are merged.

## Steps
- [ ] `POST /api/admin/claims/:id/verify|revoke`: Supabase row first, then an idempotent graph
      stamp with one retry. The claimed-card tick goes live.
- [ ] Venue and artist edit forms on `/pro/org`. Routes, writer whitelists and lookup
      fields exist; only the UI is missing.
