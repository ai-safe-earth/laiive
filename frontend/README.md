# laiive frontend

Vite + React 18 + TypeScript (strict) SPA. Talks to **one** backend: the gateway
on :8000 (`/api/chat/*`, `/api/push/*`) — the FastAPI services are not reachable
from the browser.

## Run

```sh
npm install
npm run dev      # http://localhost:8081  (8080 is taken by EnterpriseDB here)
```

Needs the stack up: gateway :8000, retriever :8002, pusher :8003
(`make start-gateway`, and `uv run uvicorn agent.api:app --port 800{2,3}` from
inside each service directory).

```sh
npm run typecheck   # both tsconfig projects — plain `tsc --noEmit` is a no-op here
npm test            # vitest + jsdom, one run;  npm run test:watch to stay open
npm run build       # typecheck + vite build
npm run lint
```

Specs live beside what they cover (`src/**/*.test.ts?(x)`). `vitest.config.ts`
inherits the app's aliases and supplies fake `VITE_*` values, and every spec
that reaches Supabase mocks the client — a test run never dials out.

## Environment

Copy `.env.example` to `.env`. `src/env.ts` validates the three keys at startup
and throws with a readable message rather than rendering a blank page.

## Contracts

Protocol types come from `../services/shared/ts/protocol.ts` through the
`@shared` alias — the same file `services/shared/tests/test_ts_contract.py`
diffs against the pydantic models, so the wire format cannot drift. Never
redeclare `EventCard` or the frame payloads locally.

`src/api/sse.ts` parses the **named-event** v2 protocol (`event: message.delta`
…), not the legacy OpenAI-shaped frames.

## Layout

```
src/api/        gateway client (auth header, ApiError) + SSE parser + chat turn
src/auth/       supabase client, AuthProvider, role from the user_role claim
src/components/ EventCardView (+ Leaflet map), Markdown, UserMenu, ui primitives
src/i18n/       translations (en/es/it/ca), language context, language detection
src/pages/      Chat, Auth, NotFound
```
