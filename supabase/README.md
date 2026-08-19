# Supabase setup (fresh project, D15)

One-time owner steps to bring the new project live:

1. Create the project at supabase.com (free tier). Note the project URL and
   the **service_role** key (Settings → API).
2. Link and push the migrations:
   ```sh
   npx supabase login
   npx supabase link --project-ref <project-ref>
   npx supabase db push
   ```
3. Register the access token hook (required — the gateway reads roles from
   the JWT): Dashboard → Authentication → Hooks → *Customize Access Token
   (JWT) Claims* → Postgres function → `public.custom_access_token_hook`.
4. Enable Google as an OAuth provider (D8, pro signup):
   Authentication → Providers → Google (client id/secret from Google Cloud
   Console, redirect URL shown in the dashboard).
5. Add to the root `.env`:
   ```
   SUPABASE_URL=https://<project-ref>.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=<service_role key>
   ```
   (the frontend will additionally need the anon/publishable key in Phase 4)

Notes:
- New projects sign JWTs with asymmetric keys (ES256); the gateway verifies
  against `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` — no JWT secret is
  ever copied out of Supabase.
- Roles are granted by updating `public.user_roles` with the service role
  (SQL editor or admin tooling); the change lands in the JWT on the next
  token refresh.
- The old project's schema is reference only; nothing here depends on it,
  and the old edge functions are intentionally not ported.
