# HANDOFF - laiive (updated 2026-08-21)

State only. Rules and machine gotchas: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`;
refactor history `docs/refactor/` (closed).

## Where things stand

**laiive is live at https://laiive.com**, tagged `v0.1.0` - Cloudflare Pages (production branch
`main`, previews from `develop`; `laiive.pages.dev` still serves as fallback); gateway
https://laiive-gateway.fly.dev, five Fly apps in `fra`, retriever/pusher/search on no public IPs.

**`main` is production, `develop` the trunk and default branch**; work branches PR into
`develop`, `main` takes a release PR only and is protected. Ship with `make release`; model in
`CONTRIBUTING.md`. Archives, never build on: `legacy/pre-refactor`, `experiment/k3s`.

**Brand v1 is shipped and serving**; `brand-guide.pdf` is still missing, so the decisions it may
overrule stay under "Restyle" in the machine block - reverting is a token swap. **`develop` is
four commits ahead of `main` and unreleased**: the promoter door, the sign-up hardening, the
frontend test suite. PR #57 (deploy docs) is open on top.

## The promoter door - finished, unclicked

`?kind=pro` is one form now: the organisation is a field on sign-up, `20260820000012` grants the
role by trigger, the token is re-minted before `/pro` opens. OAuth returns to `/auth/callback`, a
waiting room, so `/pro` never renders against a pre-grant token; a confirmation mail is survived
by a `localStorage` intent keyed to the address (24 h). The frontend has tests now too - vitest +
jsdom, 33 specs, run by CI. **Nobody has walked any of it in a browser.**

## Open

- **The Supabase redirect allow-list is unverified** and gates Google sign-in in production: it
  needs `<origin>/**`, not bare origins, now the return leg is `/auth/callback`. It cannot be
  probed from outside - read it (`DEPLOY.md` section 5 step 2).
- `origin/feat/promoter-onboarding-and-surface` is stale - a push recreated it after #56 merged
  and deleted it; remote branch deletion is refused from here.
- The **OG card** is `og-base-1200x630.png` bare; the composed version is still to make.
- Google sign-in shows the Supabase project id rather than laiive - `DEPLOY.md` section 5b.
- Never clicked: Google sign-in for real, the pro walk in es/ca, the new artist repeater.
- Smaller: `lucide-react` unused in `package.json`; `20260819000011` applied but unwritten-to;
  `.claude` deny rules unverified after restart; `main_protection` redundant; ingestion items in
  `01-program.md` section 7.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-08-21",
  "deadline": null,
  "people": [
    "oscar"
  ],
  "plans": [
    {
      "name": "refactor",
      "path": "docs/refactor/",
      "status": "done"
    },
    {
      "name": "roadmap",
      "path": "docs/roadmap/",
      "status": "active"
    }
  ],
  "phases": [
    {
      "name": "Phase 0 - hygiene",
      "status": "done",
      "start": null,
      "end": "2026-08-12",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-12",
          "text": "D4 keys rotated, ports unified on 8002/8003, LICENSE proprietary"
        }
      ]
    },
    {
      "name": "Phase 1 - graph schema + seed",
      "status": "done",
      "start": null,
      "end": "2026-08-12",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-12",
          "text": "setup_schema.py is the DDL source of truth for Aura 2099d44c"
        }
      ]
    },
    {
      "name": "Phase 2 - backend contracts + redesign",
      "status": "done",
      "start": null,
      "end": "2026-08-13",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-13",
          "text": "D10 services/shared as the laiive-shared package, typed SSE protocol with a TS mirror"
        },
        {
          "date": "2026-08-13",
          "text": "ReAct orchestrator deleted for classifier -> router -> executor -> composer"
        },
        {
          "date": "2026-08-13",
          "text": "Pusher state is client-carried, no TTL session store"
        }
      ]
    },
    {
      "name": "Phase 3 - gateway + auth + ownership",
      "status": "done",
      "start": null,
      "end": "2026-08-13",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-13",
          "text": "D7 anonymous chat allowed, role travels in the JWT via a custom access token hook"
        },
        {
          "date": "2026-08-13",
          "text": "D15 fresh Supabase project pjlcfdyheyubsemwlzzv, conversation logging is request-side only"
        }
      ]
    },
    {
      "name": "Phase 4 - frontend, multimodal, walk",
      "status": "done",
      "start": null,
      "end": "2026-08-14",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-14",
          "text": "D1 fresh Vite + React app on the v2 protocol, D9 Leaflet maps"
        },
        {
          "date": "2026-08-14",
          "text": "A spreadsheet is a longer conversation, not a batch screen - CSV fast lane deleted"
        },
        {
          "date": "2026-08-14",
          "text": "Multi-event walk cursor lives client-side (option A)"
        },
        {
          "date": "2026-08-14",
          "text": "Profile data goes direct to Supabase under RLS, not through the gateway"
        }
      ]
    },
    {
      "name": "Phase 5 - SEARCH service + scheduling",
      "status": "done",
      "start": "2026-08-14",
      "end": "2026-08-17",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-14",
          "text": "D13 revised: Tavily instead of Brave, it returns cleaned page content"
        },
        {
          "date": "2026-08-14",
          "text": "Write gate relaxed for admin_search: name + start_at + venue + city only"
        },
        {
          "date": "2026-08-14",
          "text": "Sweeps stay dry-run, a human approve is required before any graph write"
        },
        {
          "date": "2026-08-14",
          "text": "D17 Prefect Cloud managed pool, flows are thin HTTP clients of the public gateway"
        },
        {
          "date": "2026-08-14",
          "text": "54 of 88 swept candidates approved into the graph"
        },
        {
          "date": "2026-08-17",
          "text": "A managed pool cannot reach a localhost gateway; recommended shape is Prefect Cloud as scheduler and UI only, with flows executing locally via serve() - owner approval pending, nothing implemented"
        },
        {
          "date": "2026-08-17",
          "text": "Cloudflare quick tunnel rejected: its 100 s origin-silence cap would 524 the 2-6 min synchronous sweep and misattribute the failure to Prefect; ngrok has no such cap"
        },
        {
          "date": "2026-08-17",
          "text": "Scheduling implemented as flows/serve.py (Prefect 3 serve()): both cron deployments registered in Prefect Cloud, executed locally against the gateway - verified live end to end, a Cloud-triggered backfill run completed in ~7s"
        }
      ]
    },
    {
      "name": "Phase 6 - CI/CD + deploy",
      "status": "done",
      "start": "2026-08-17",
      "end": "2026-08-19",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-14",
          "text": "D18 frontend host is Cloudflare Pages; services on Railway/Fly per R2"
        },
        {
          "date": "2026-08-17",
          "text": "CORS between the gateway and the services was rejected as a security control: it is browser-enforced and the gateway is not a browser, so it would change nothing about who can reach 8002/8003"
        },
        {
          "date": "2026-08-17",
          "text": "D19 (k3s on one Hetzner CX32) was decided and withdrawn the same day after pricing the trade-off; R1 and R2 reinstated - compose now, Railway/Fly at deploy time. The full k8s work is parked on branch experiment/k3s (99c92d4)"
        },
        {
          "date": "2026-08-17",
          "text": "The gateway-services boundary is a shared INTERNAL_API_KEY the gateway injects and each service verifies, working identically under compose; an unset key is a no-op for local runs"
        },
        {
          "date": "2026-08-17",
          "text": "Distributed state (gateway rate limit, geocoder cache and 1 req/s gate) goes to one Redis in compose when REDIS_URL is set; unset keeps the old per-process behaviour"
        },
        {
          "date": "2026-08-17",
          "text": "Images hardened: multi-stage, non-root uid 10001, no dev deps, venv uvicorn, verified read-only rootfs; compose gained Redis, healthchecks and restart policies - first verified compose build since Phase 3"
        },
        {
          "date": "2026-08-18",
          "text": "CI green for the first time: gitignore lib/ anchored so frontend/src/lib/cn.ts is tracked, ruff==0.4.9 pinned in every dev group, dummy env keys on the pytest step, python jobs pinned to 3.13 via UV_PYTHON"
        },
        {
          "date": "2026-08-18",
          "text": "Repo hygiene: product-status.md tracked, supabase/.temp ignored, Aura creds file moved to ../laiive-data, CLAUDE.md rewritten to the post-refactor stack, Makefile pruned to CI-mirroring targets"
        },
        {
          "date": "2026-08-18",
          "text": "Owner chose Fly.io over Railway (R2 second option) for the service deploy; deploy-prep landed code-only with no accounts: deploy/fly tomls, make fly-deploy targets, DEPLOY.md runbook"
        },
        {
          "date": "2026-08-18",
          "text": "202+poll implemented: sweep and backfill answer 202 with a running report row and finish in a BackgroundTasks worker; flows poll GET /reports/{id}; approve CAS unchanged so running/failed reports stay unapprovable. Migration 20260818000010 must be pushed before the new search code runs"
        },
        {
          "date": "2026-08-18",
          "text": "Python images bind :: for Fly 6PN (IPv6-only); no $PORT plumbing since internal_port targets the bound port; redis stays self-hosted because volatile-lru is load-bearing for the geocode cache"
        },
        {
          "date": "2026-08-18",
          "text": "Gateway eslint added and the CI node matrix lints both dirs; CI deploy workflow deferred as untestable without secrets"
        },
        {
          "date": "2026-08-19",
          "text": "The images could not talk to anything under compose and it took booting the stack to see it. A '::' bind is not dual-stack - asyncio sets IPV6_V6ONLY - so 127.0.0.1 was refused inside the container: every healthcheck failed forever, the gateway never started, and once the checks were fixed it got ECONNREFUSED from the services on the IPv4 compose network. Bind is now BIND_HOST defaulting to 0.0.0.0, exactly like the gateway's GATEWAY_HOST, with '::' set in the fly tomls where 6PN requires it"
        },
        {
          "date": "2026-08-19",
          "text": "Local 202+poll smoke passed against the real deployed shape: five containers healthy, /api/chat returned three Barcelona events, /api/chat/stream streamed 21 real deltas and answered 'hola' in Spanish, and the admin sweep returned 202 in 2.9s then polled running -> dry_run in 28s with 3 candidates - which also proves migration 20260818000010 is live"
        },
        {
          "date": "2026-08-19",
          "text": "BIND_HOST was the wrong fix and lasted an hour: the first Fly deploy came up started and permanently critical because Fly's machine checks arrive over IPv4 while 6PN needs IPv6, so one process has to answer both and uvicorn's --host takes one. laiive_shared.serve opens the socket with IPV6_V6ONLY off and execs uvicorn onto it via --fd, keeping uvicorn as PID 1 for the drain window"
        },
        {
          "date": "2026-08-19",
          "text": "Region is fra, not mad: Fly no longer offers Madrid ('region mad not found'). Owner chose Frankfurt over Paris because Supabase is eu-central-1, so JWKS, conversation logging and the search report writes all land next door"
        },
        {
          "date": "2026-08-19",
          "text": "Every make fly-deploy-* target was wrong and had never been run: flyctl resolves --config AND --dockerfile relative to the positional build-context directory, not the shell cwd, so repo-root paths gave 'missing an app name' and then services/services/retriever/Dockerfile. Targets now cd into services/ with both paths relative to it"
        },
        {
          "date": "2026-08-19",
          "text": "Deployed live: five apps in fra, checks passing, retriever/pusher/search with zero public IPs. Verified on https://laiive-gateway.fly.dev - healthz 200, /api/chat returned three Barcelona events, /api/chat/stream streamed 23 deltas through the Fly proxy, admin sweep 202 in 3.5s to dry_run with 2 candidates. Sections 4 and 5 (Pages, CORS, Supabase redirect URLs, GATEWAY_URL) still need the owner's accounts"
        },
        {
          "date": "2026-08-19",
          "text": "Frontend live on Cloudflare Pages at https://laiive.pages.dev, production branch main, previews from develop. Verified from that origin: CORS preflight allows laiive.pages.dev and develop.laiive.pages.dev and refuses anything else, the built bundle carries the gateway URL and the Supabase publishable key with no localhost left in it, /account deep-links through the SPA fallback, and a chat turn plus an SSE stream both answer"
        },
        {
          "date": "2026-08-19",
          "text": "flyctl secrets set replaces a key rather than appending, so setting CORS_ALLOW_ORIGINS twice locked out the production origin and left only the preview. Every origin has to go in one comma-separated value, and the check that catches it is a preflight, not the command output"
        },
        {
          "date": "2026-08-19",
          "text": "Ownership becomes organizations with members and roles, self-declared claims, and no restriction on listing at someone else's venue - so ownership governs who may EDIT a record, never who may create one. Migration 20260819000011 applied; nothing writes to the tables until org creation exists as a screen, which is deliberate because that is exactly how the unused public.ownerships table happened. Research with access dates in docs/references.md"
        },
        {
          "date": "2026-08-19",
          "text": "The artists field in the pro event form could not be typed into: it split on commas and trimmed on every keystroke, so a space was deleted as it was typed and a comma vanished with it. It held exactly one single-word artist while the label asked for commas. Replaced with one input per artist plus an add button"
        },
        {
          "date": "2026-08-19",
          "text": "Branching model chosen by the owner: main is production, develop is the trunk and the GitHub default. Work branches cut from develop and PR into it; main takes a release PR only. GitFlow's release and hotfix branches are not adopted - a hotfix is a branch off main merged back into develop the same day. The argument that carried it is Cloudflare Pages: production builds from main, so develop is what keeps every merge from shipping the frontend, and it gets a preview URL for free"
        },
        {
          "date": "2026-08-19",
          "text": "Classic branch protection is unavailable to this repo ('Branch protection has been disabled on this repository' on a free org, public repo), so protection is a repository ruleset instead: PR required with 0 approvals, all 11 status checks, no force-push, no deletion, admin bypass on per the owner. develop gets a lighter ruleset - no deletion, no force-push, direct pushes still allowed"
        },
        {
          "date": "2026-08-19",
          "text": "Releases are semver tags plus a generated CHANGELOG: .cz.toml gains version 0.1.0, update_changelog_on_bump and major_version_zero, and make release runs cz bump through uvx. --yes is not optional on this machine - prompt_toolkit raises NoConsoleScreenBufferError under Git Bash. CI push triggers narrowed to main and develop, since a work branch is already covered by its PR and both were running"
        },
        {
          "date": "2026-08-20",
          "text": "laiive.com is the live domain: Cloudflare nameservers, Pages custom domain for apex and www, og/twitter cards pointed at it. laiive.pages.dev keeps serving as the fallback"
        },
        {
          "date": "2026-08-21",
          "text": "The frontend has a test suite - vitest + jsdom, config merged from the app's vite config so aliases cannot drift, fake VITE_* env, every Supabase-touching spec mocks the client. 33 specs, and CI's frontend matrix row flips from test:false to test:true"
        },
        {
          "date": "2026-08-21",
          "text": "Supabase's redirect allow-list needs <origin>/** patterns now the OAuth return leg is /auth/callback: a bare origin matches no path and a single * stops at a separator. It cannot be probed from outside - /auth/v1/authorize echoes redirect_to unvalidated (https://example.com/ passes straight through), the check happens on the return leg - so read it with the Management API or watch the URL bar"
        },
        {
          "date": "2026-08-21",
          "text": "Gateway CORS is exact string equality (@fastify/cors over the split CORS_ALLOW_ORIGINS array), so per-deploy Pages preview hostnames can never reach it and develop.laiive.pages.dev is the only usable preview. Verified live: laiive.com, www, laiive.pages.dev and the develop alias are allowed, nothing else"
        }
      ]
    },
    {
      "name": "Phase 7 - geocoding and location quality",
      "status": "done",
      "start": "2026-08-18",
      "end": "2026-08-18",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-18",
          "text": "Nominatim kept, Photon rejected. Measured on the real corpus: the writer's joined query form resolved 0 of 9 venues and 'venue, city' resolved 8 of 9, so the query string was the bug, not the provider"
        },
        {
          "date": "2026-08-18",
          "text": "A wrong hit is worse than a miss: a miss warns and falls back to the city centroid, a wrong hit is written silently. VENUE_MAX_KM = 25 km rejects answers outside the stated city, measured from the distribution (every correct answer within 12.5 km, everything beyond wrong)"
        },
        {
          "date": "2026-08-18",
          "text": "Two Nominatim-only alternatives measured and rejected: structured amenity/city params tie the short form at 8/9 but run 1.8x slower and are worse on neighbourhoods; limit=5 nearest-plausible adds no recall over the guard"
        },
        {
          "date": "2026-08-18",
          "text": "D12 revised: Google is not actually available as the fallback. It caps lat/lng caching at 30 days and its indefinite exception requires per-end-user isolation, which a shared events graph cannot satisfy; Mapbox standard has the same problem"
        },
        {
          "date": "2026-08-18",
          "text": "address is required for promoter submissions but deliberately not for admin_search - only ~26% of swept listings state one, so requiring it there would reject most of discovery"
        },
        {
          "date": "2026-08-18",
          "text": "The coverage gap is missing address data, not missing geocoding, so it is closed with a Tavily address resolver in the search service rather than a second geocoding provider; injected as a callable so the pusher never needs Tavily"
        },
        {
          "date": "2026-08-18",
          "text": "v.geocode_precision and v.geocode_checked_at added; the backfill became a repair sweep that can finally see wrong locations (the old WHERE v.location IS NULL could not, since a wrong pin is not null). Failed attempts are stamped and skipped for 7 days so one unresolvable venue cannot starve the LIMIT"
        },
        {
          "date": "2026-08-18",
          "text": "Verified live: Oasys was pinned 627.5 km from Barcelona in Almeria; one repair run moved it to 1.08 km via the Tavily resolver, and zero venues now sit beyond the guard"
        },
        {
          "date": "2026-08-18",
          "text": ".claudeignore is read by nothing (anthropics/claude-code#56997); .claude/settings.json permissions.deny is the working mechanism, negated in .gitignore so it survives a clone. Not yet verified enforcing - settings load at startup"
        },
        {
          "date": "2026-08-18",
          "text": "The relaxed admin_search write gate was re-opened and stands, but the missing genre on swept events is not a nit: the genre predicate is a hard AND over HAS_GENRE, so every genre-pinned query silently excludes every discovered event. Fix recommended (infer genre at approve, or fall back on zero rows), not implemented, owner's call"
        },
        {
          "date": "2026-08-18",
          "text": "Router: a shared location becomes a filter only for browse-shaped asks. city, country_code, artist and venue win over it, since an artist question must not be cut to a 25 km circle"
        },
        {
          "date": "2026-08-18",
          "text": "Named-place search runs TEMPLATE first and geocodes to a bbox only on zero rows, so the happy path pays nothing. 60 km diagonal ceiling refuses region-sized boxes (Catalonia is 369 km, Berlin ~50)"
        },
        {
          "date": "2026-08-18",
          "text": "Place boxes are padded to a 2 km minimum span: 7 of the 22 measured places resolve to a point, since OSM answers with the square that carries the name. Cost accepted: a padded box reaches into the next barrio"
        },
        {
          "date": "2026-08-18",
          "text": "_from_cached filters unknown keys before hydrating GeocodeResult, so adding a cached field can no longer TypeError a process reading an entry a newer build wrote"
        },
        {
          "date": "2026-08-18",
          "text": "geocode_precision travels on the EventCard; a suspect pin loses its coordinates in rows_to_cards, because template and vector have no location predicate and that is the layer where the guarantee has to hold"
        },
        {
          "date": "2026-08-18",
          "text": "Found live: eight Barcelona venues share one pin, which is Nominatim's answer for 'barcelona', and six Madrid venues sit on its centroid. The 25 km guard, the precision flag and the c.location distance test all miss them (c.location is 888 m from the geocoder's current answer). Guards added at both ends: the sweep stamps city_centroid when the venue answer equals the city answer, and the bbox leg excludes a pin shared by two venues in the same city"
        },
        {
          "date": "2026-08-18",
          "text": "Repair sweep drained: run_backfill(max_venues=100) geocoded 27 venues, nine of them via the Tavily address resolver. All 35 venues now stamped 'venue' and the shared-pin collapse is gone - the Barcelona eight have eight distinct pins"
        },
        {
          "date": "2026-08-18",
          "text": "The drain exposed that a merely-plausible answer wins by being tried first: Sant Jordi Club landed 17.7 km out by name while its stored address resolves 3.1 km out. Preferring the address is not the fix (Sala El Sol is 0.3 km by name, 25 km by address). An answer beyond VENUE_OUTLIER_KM=12.5 no longer ends the search; the nearest plausible form wins. Dry replay over all 35 venues moves exactly one"
        },
        {
          "date": "2026-08-18",
          "text": "Correction: 43 of 57 admin_search events are already reachable by a genre query and 39 carry their own tag. 'admin_search events carry no genre' was true of the Phase 5a sweep only, and the earlier reading of it as the largest retrieval gap was wrong"
        },
        {
          "date": "2026-08-18",
          "text": "The genre predicate now matches a slug that is the asked genre or contains it as a hyphen-separated part, because extraction emits what the page says: 'pop-rock' answered neither 'rock' nor 'pop'. Measured: 'rock' 7 -> 10 events, nothing else changes"
        },
        {
          "date": "2026-08-18",
          "text": "The remaining genre gap is 13 untagged artists hiding 14 events, fixed by tagging the artist rather than the event so it reaches their future events too. genre_lookup asks one batched LLM call with abstention as the safe answer; the write goes through laiive_shared.tag_artist_genres so the Genre MERGE matches write_event's. Owner runs scripts/tag_artist_genres.py --write"
        },
        {
          "date": "2026-08-18",
          "text": "Artist tagging run: 12 artists tagged, genre reachability 43 -> 55 of 57 events, no duplicate Genre nodes. Corrected measurement: the token split takes 'rock' 7 -> 18 and 'pop' 16 -> 23, not 7 -> 10 with pop unchanged - the first pass was measured through max_results_limit=10, which caps every template answer at ten rows"
        },
        {
          "date": "2026-08-18",
          "text": "Genre vocabulary: genre_slug collapses a short alias list ('electronica'->'electronic', 'r-b'->'rnb') and rejects non-genres ('various', 'live'); genre_family expands a query to every spelling already stored. Matching is on hyphen boundaries rather than split() parts so a multi-part variant reaches a composite slug while 'rap' still does not answer 'trap'. Live: rnb 0 -> 4 events, electronic 4 -> 7"
        },
        {
          "date": "2026-08-18",
          "text": "30 of 57 discovered events showed a fabricated 00:00 start: the page gave a day, the parser defaulted the rest, and the card printed the default as a fact. start_time_known is decided from the listing text (a parsed midnight cannot be told from a defaulted one), extraction now emits a bare date when no time is stated, and formatWhen drops the hour"
        },
        {
          "date": "2026-08-18",
          "text": "Correction: there are no duplicate events - zero share a name and a day, and 'The Weeknd three times' was a real three-night run misread from a truncated smoke listing. The real duplication is four near-duplicate Venue nodes within 162 m of each other, two of which are a room inside a building and must not be merged"
        },
        {
          "date": "2026-08-18",
          "text": "An Outcome carries a retrieval note to the composer when the match was approximate. Five samples each way: neither overstated, but without the note the composer drops the neighbourhood and answers about the city instead, so the note buys an answer that addresses the question rather than preventing a lie"
        },
        {
          "date": "2026-08-18",
          "text": "48 of 57 discovered events were shown as free because entry_to_draft mapped an empty price string to 0.0 and the extraction prompt never said what to do when no price is stated. 34 of them sell tickets. Fixed at both ends; the existing rows are cleared by scripts/clear_default_prices.py rather than guessed at, since a stated 'gratis' and a defaulted empty string are indistinguishable now"
        },
        {
          "date": "2026-08-18",
          "text": "Sweep-quality list checked against data: no date poisoning (the heaviest day is 5 events at 5 venues, dates run to 2027-05 as tour announcements do) and no non-music events (name scan for theatre/comedy/expo/cinema/circus/ballet/market returns nothing). The type gate can wait for a sweep that actually pulls one in"
        },
        {
          "date": "2026-08-18",
          "text": "Maintenance scripts open a read-only Neo4j session unless --write is passed, so a dry run is enforced rather than promised - and it connects while the Aura free tier has dropped its WRITE server, which broke a dry run"
        },
        {
          "date": "2026-08-18",
          "text": "All three repair writes ran and were verified against the graph: 48 fake 'free' prices cleared (0 remain), 30 fabricated midnights marked date-only, Sant Jordi Club moved 17.7 km -> 3.1 km. Clearing the prices is the session's one lossy change - a genuinely free night has lost that fact until a sweep re-reads its page"
        }
      ]
    },
    {
      "name": "Close the refactor",
      "status": "done",
      "start": "2026-08-19",
      "end": "2026-08-19",
      "plan": "roadmap",
      "decisions": [
        {
          "date": "2026-08-19",
          "text": "The pre-refactor main is preserved as branch legacy/pre-refactor and tag pre-refactor-main, both at 542952f. main was not the untouched ancestor it looked like - it carried six commits the branch never saw, one of them the owner's March README revision - so origin/main was merged into the branch and the README resolved by hand (owner's marketing copy, branch's technical sections) before PR #29 could merge. The earlier tag legacy-main-2026-08-19 points six commits short and should be deleted"
        },
        {
          "date": "2026-08-19",
          "text": "The evals/ tree was documentation for a harness that never existed - five guides describing a config.py, runners/ and run_evals.py absent from the tree. Deleted, along with the utils sketches and the two datasets encoding the deleted ReAct vocabulary (expected_action QUERY_DB/NEEDS_INFO); the safety and query_generation sets survive because they map to code that exists"
        },
        {
          "date": "2026-08-19",
          "text": "Program order set with the owner: deploy, then a new visual direction (design canvas approved before any React), then evals + observability, then multi-provider model routing, then retrieval accuracy, then guardrails/cache/language/voice, then ingestion + self-improvement"
        },
        {
          "date": "2026-08-19",
          "text": "Speculative decoding is out of scope: it is not exposed by hosted model APIs and self-hosting was rejected. The latency levers are prompt caching, parallel sub-query execution and a semantic cache on the Redis that already exists"
        },
        {
          "date": "2026-08-19",
          "text": "Branch prune done: every stale branch deleted local and remote, including OscarArroyoVega-patch-1 (unmerged but from 2025-10-23, owner's call to delete). Only main, legacy/pre-refactor and experiment/k3s remain. Local main had been tracking laiive/main, the personal fork, and now tracks origin/main"
        },
        {
          "date": "2026-08-19",
          "text": "Section 2 of DEPLOY.md is scripted as deploy/fly/set-secrets.sh (make fly-secrets / fly-secrets-check): 35 pairs across four apps typed by hand is where INTERNAL_API_KEY stops being identical everywhere. Key names only are ever printed; --stage because the apps have no machines yet at that point. Checked against the real .env - every required key present"
        }
      ]
    },
    {
      "name": "Restyle - new visual direction",
      "status": "active",
      "start": "2026-08-19",
      "end": null,
      "plan": "roadmap",
      "decisions": [
        {
          "date": "2026-08-19",
          "text": "The design-canvas step is superseded: the owner delivered a finished brand pack from the design project as assets/brand - enforceable rules, a drop-in token block, 17 icons, static reference screens, the mark in 14 recolourings, and an eight-step order of work for the frontend. Committed as received and unapplied. brand-guide.pdf is named normative and is missing from the folder, so ambiguities are questions for the owner, not judgement calls"
        },
        {
          "date": "2026-08-19",
          "text": "Adopting it is a full visual pass rather than a token swap: warm black replaces pure black, cream replaces white for answers, amber replaces electric yellow, Bebas Neue and DM Sans replace Montserrat and IBM Plex Sans, gradients and glows are deleted outright, and the language switcher moves from the header into the account menu"
        },
        {
          "date": "2026-08-19",
          "text": "brand-guide.pdf is still missing and the owner chose to proceed on brand-rules.md as the spec rather than wait for it. Every ambiguity below was therefore an owner decision, not a judgement call, and the PDF may still overrule them"
        },
        {
          "date": "2026-08-19",
          "text": "The composer is one amber circle - mic when the field is empty, send once there is something to send, stop while streaming - and there is no '+'. reference-screens.html draws a '+' beside the mic, but the rule says the '+' opens voice and nothing else, which makes it a sheet holding a single item"
        },
        {
          "date": "2026-08-19",
          "text": "Card actions ship as map and tickets only. The artwork draws a 'save' pill, but saving has no feature behind it and a dead pill on every card breaks the promise once per card rather than once per screen. The header 'saved' icon still ships inert so the bar is final"
        },
        {
          "date": "2026-08-19",
          "text": "Where brand-rules.md and reference-screens.html disagree on size the rules win: every touch target is 44px, against the mock's 36px composer and 30px pills. Card action pills keep the mock's look and reach 44px through an :after hit area instead of growing"
        },
        {
          "date": "2026-08-19",
          "text": "The empty chat is the LAIIVE wordmark as a 5%-opacity watermark and nothing else - the old welcome line used 'discover', an exclamation and onboarding copy, all three banned. The promoter link leaves the header for the account menu, alongside settings, so the header holds exactly the four allowed elements"
        },
        {
          "date": "2026-08-19",
          "text": "/auth?kind=pro is the promoter's door: it starts on sign-up and lands on /pro afterwards. It creates an ordinary account because the pro role is still granted by hand, so the gate copy no longer says 'contact us' - there is no contact channel in the app to honour it with"
        },
        {
          "date": "2026-08-19",
          "text": "Icons are referenced from assets/brand/icons.svg copied unmodified to public/brand and used via <use>, so the artwork stays the file the brand owner ships and a fix there needs no code. lucide-react is no longer imported by any component and the dependency can be dropped"
        },
        {
          "date": "2026-08-19",
          "text": "Applied end to end on feat/brand-v1 (efe6a10): tokens, tailwind, index.html, Chat, EventCardView, UserMenu, ProSubmit, EventForm, Auth, Account, NotFound, Button, Input, MicButton, and the four language blocks. Typecheck, lint and build pass; chat with cards, auth, the pro gate and the pro form were checked in a browser at 390px and 1280px"
        },
        {
          "date": "2026-08-20",
          "text": "brand v1 is shipped: merged through develop into main and serving on laiive.com. The brand-guide.pdf caveats above stand - the PDF may still overrule them, and reverting the palette is a token swap"
        },
        {
          "date": "2026-08-21",
          "text": "The promoter door finishes the job in one form: the organisation is a field on the ?kind=pro sign-up, migration 20260820000012 grants the role by trigger, and the token is re-minted before /pro opens. This supersedes the 2026-08-19 decision that the door creates an ordinary account"
        },
        {
          "date": "2026-08-21",
          "text": "OAuth returns to /auth/callback, a waiting room that renders nothing role-gated, so /pro is never reached with a token minted before the grant and no promoter is shown a refusal that then flips under them"
        },
        {
          "date": "2026-08-21",
          "text": "A promoter's organisation survives a confirmation mail in localStorage keyed to the address it was typed for, 24 h TTL - sessionStorage cannot cross a mail client, and an intent with no lifetime or no owner ambushes whoever signs in next"
        },
        {
          "date": "2026-08-21",
          "text": "A refreshSession that fails after the promoter row landed is its own failure (PromoterRefreshError) and routes to /account: the account is a promoter, only the token in that browser disagrees, so /pro would refuse it"
        },
        {
          "date": "2026-08-21",
          "text": "The promoter surface uses the pro.* palette brand-tokens.css already shipped, contradicting a comment in that same file. Owner chose the palette; the PDF may overrule it"
        }
      ]
    },
    {
      "name": "Evals + observability",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap",
      "decisions": []
    },
    {
      "name": "Multi-provider model routing",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap",
      "decisions": []
    },
    {
      "name": "Retrieval accuracy",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap",
      "decisions": []
    },
    {
      "name": "Guardrails, cache, language, voice",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap",
      "decisions": []
    },
    {
      "name": "Ingestion + self-improvement",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap",
      "decisions": []
    }
  ],
  "blockers": [
    {
      "text": "Google sign-in is wired and enabled but the real click-through has never been exercised",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-14"
    },
    {
      "text": "The Aura free instance auto-pauses and its DNS record disappears while paused; on resume reads work but writes fail with 'No write service currently available'. Cost three aborted repair runs before it settled",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-18"
    },
    {
      "text": "prefect.yaml git-clones main of ai-safe-earth/laiive at run time and needs a github-laiive-pat Secret block; moot under the local serve() shape, relevant again only when the managed pool is revived after the deploy",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-14"
    },
    {
      "text": "The Supabase redirect allow-list is unverified and gates Google sign-in in production: with bare origins rather than <origin>/** patterns the return to /auth/callback is silently dropped for the Site URL. Read it with GET /v1/projects/<ref>/config/auth",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-08-21"
    }
  ],
  "nextSteps": [
    {
      "title": "Compose the OG card on og-base-1200x630.png - public/og-image.png is the bare ground today, with og:title and og:description carrying the words",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    },
    {
      "title": "Drop lucide-react from frontend/package.json - no component imports it since the brand icon set landed",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    },
    {
      "title": "Click through Google sign-in once with a real account, and walk the 4d multi-event walk in a browser including the es/ca strings",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    },
    {
      "title": "Eval harness: suites for classifier, routing, Cypher, retrieval recall, answer quality and safety, per-model reports, a deterministic CI tier; plus Langfuse across all three Python services and response-side capture in the gateway",
      "est": 5,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "laiive_shared.llm: one call surface over OpenAI, Anthropic and OpenRouter with role to model resolution, fallback chain, cost accounting and preserved token streaming",
      "est": 3,
      "owner": "oscar",
      "phase": "Multi-provider model routing",
      "plan": "roadmap"
    },
    {
      "title": "Parallel sub-queries with rank fusion, several legs per sub-query, a Neo4j full-text index, an EXPLAIN-validated Cypher builder with one repair attempt, and a measured empty-result ladder",
      "est": 5,
      "owner": "oscar",
      "phase": "Retrieval accuracy",
      "plan": "roadmap"
    },
    {
      "title": "Genre on newly swept events: infer genre at approve time, or fall back to unfiltered-plus-rank on zero rows. 55 of 57 existing events are reachable after the artist tagging, but a new sweep still arrives untagged",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Extraction optimizer: JSON-LD schema.org/Event before the LLM, chunking instead of truncation, schema-enforced output, per-domain adapters, and a frozen-page eval set with precision/recall",
      "est": 4,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "'Shakira Stadium' is a listing-page artefact, not a venue: 9.5 km from Madrid's centre, no address. Extraction quality, not geocoding",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Venue near-duplicates: four pairs within 162 m (Palacio Vistalegre/Arena, Estadi Olimpic/Lluis Companys, Razzmatazz/Sala Razzmatazz 1, Kulturbrauerei/Frannz Club). Detect by name containment within a city plus distance, but never auto-merge - two of the four are a room inside a building",
      "est": 2,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Confirm the .claude/settings.json deny rules actually enforce after a restart; if .history/ is still readable, fall back to a PreToolUse hook",
      "est": 1,
      "owner": "oscar",
      "phase": "Close the refactor",
      "plan": "roadmap"
    },
    {
      "title": "Optional: containerize flows/serve.py as a compose flows service (needs its own Dockerfile stage since the hardened search runtime has no uv, plus PREFECT_API_KEY/PREFECT_API_URL in root .env)",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Verify the Supabase redirect allow-list carries <origin>/** for laiive.com, www, laiive.pages.dev and the develop alias, and that Site URL is https://laiive.com - read it, do not infer it (DEPLOY.md section 5 step 2)",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    },
    {
      "title": "Release PR develop -> main: the promoter door, the sign-up hardening and the frontend test suite are unreleased. Then make release, deploy, and merge main back into develop so the tag is not stranded",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    },
    {
      "title": "Delete origin/feat/promoter-onboarding-and-surface - recreated by a push after PR #56 merged and deleted it, and remote branch deletion is refused from this machine",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {
      "date": "2026-08-13",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-14",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-17",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-17",
      "model": "fable-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-17",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "fable-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "fable-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-19",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-19",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-21",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    }
  ]
}
```
