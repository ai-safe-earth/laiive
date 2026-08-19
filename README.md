<img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" />

# Laiive.com

#### what is 🫦Laiive?
laiive is what will save you from being at home scrolling for the rest of your life.
laiive is where you find the perfect life event for you, and if you are an artist or a promoter is the way to make people know you are doing something.
If you want to do something now, friday evening, saturday morning... Just ask, Laiive will help you to find what you are looking for outside of the screen.

![mockup](https://github.com/user-attachments/assets/4f94c5df-6b66-42b8-9925-1314b9987c48)

#### why is 🫦laiive needed?
laiive links the broken connection between events and public[^*]

![mission](https://github.com/user-attachments/assets/569506fc-6adb-4762-8b60-2f2e0bb69866)

#### 🫦laiive look for all, not just for the big ones

laiive was born to connect small events with people close to them, laiive does not focus on big musical events as many platforms are, laiive works on the human and community scale where small music events live.

#### 🫦laiive uses AI to balance our digital-physical culture.

laiive was born as an AI cultural agenda, with the AI hype and AI competition without the AI Safety layer laiive has become a subversive way of using AI, it tries to steal attention from the main digital platforms and bring it back to real world social meetings. laiive positions itself as an ethical AI app helping to develop a balanced digital-physical culture before the intermediate layer in our digital comunication becomes too powerful.

#### 🫦laiive has abitious positive outcomes

laiive is a catalyst of a worldwide demand that is actually unattended. laiive connects thousands of daily live events and millions of people are not going to them because they don't know they exist. Solving this gap may have a direct positive outcome, and many indirect ones, the most interesting one for our point of view, and because of the times that we are facing, is that laiive can enhance community strengths around physical cultural events, historically relevant focal points of resistance to authoritarianism.

---

## Services
<img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  />

Four services and one shared contract package. Only the gateway is ever published; the three
Python services are reachable on the internal network alone.

### Frontend (`frontend/`)
Vite + React + Tailwind. A zero-click UI: you ask in your own words and get an answer with
event cards and a map next to it, not a list to scroll. Four languages (en/es/it/ca), voice
input, and a promoter side that publishes an event by talking about it — including a flyer
photo or a spreadsheet, one event per turn. Talks to the gateway only.

### Gateway (`services/gateway`, Fastify + TypeScript, port 8000)
The only published surface. Supabase JWT auth with the role in the token, rate limits per
role, and proxying: `/api/chat/*` → retriever, `/api/push/*` → pusher (pro and up),
`/api/admin/search/*` → search (admin). It injects a verified user id and role plus an
internal key that the Python services check, so nothing reaches them unmediated.

### Retriever (`services/retriever`, FastAPI, port 8002)
Reads the knowledge graph. One turn is classifier → router → executor → composer: a cheap
structured call resolves the full constraint state and splits multi-intent asks into atomic
sub-queries; routing is deterministic code; execution is parameterized Cypher templates for
the common shapes, `point.distance` with a widening radius for "near me", vector kNN for vibe
asks, a bounding box for neighbourhoods that are not cities, and LLM-generated read-only
Cypher for the long tail. The composer streams real tokens and never lists events — the cards
do that.

### Pusher (`services/pusher`, FastAPI, port 8003)
Multimodal ingestion for promoters: text, images and audio become an event draft through
extraction, guardrails and a human confirmation. Chat is stateless — the client carries the
history — and a listing with many events becomes a walk, one event per turn. A spreadsheet is
a longer conversation, not a batch screen.

### Search (`services/search`, FastAPI, port 8004)
Sweeps the web for events in a city (Tavily), extracts drafts, dedups them against the graph
and reports them as a **dry run**. Nothing is written until an admin approves. Sweeps and
backfills run on a schedule through Prefect.

### Shared (`services/shared`, the `laiive-shared` package)
The contract: the typed SSE protocol with its TypeScript mirror, the card and draft models,
geocoding, language detection, and `neo4j_writer.py` — the single write path into the graph,
MERGE-by-identity with duplicate detection.

### Data
A Neo4j (Aura) knowledge graph of events, artists, venues, cities and genres. laiive deals
with ephemeral data, data that still doesn't exist: it grows in inertia when users ask and
promoters publish, and the graph is what makes "jazz near me on Friday, under 15 euros" one
query instead of five filters.

---

## License

Proprietary software - Copyright (c) 2026 Oscar Arroyo Vega. All rights reserved. See [LICENSE](LICENSE).

---

## Running it

Every Python service is its own `uv` project — there is no root `pyproject.toml`, and every
command runs from inside a service directory. All of them load the single root `.env`
(template: `.example.env`), resolved relative to the working directory.

### The whole stack, in Docker

```bash
make up-dev        # build + run gateway, retriever, pusher, search, redis
make down
```

### Service by service, for development

```bash
make start-gateway     # :8000, the only surface the frontend uses
make start-retriever   # :8002
make start-pusher      # :8003
make start-search      # :8004

cd frontend && npm install && npm run dev   # Vite
```

### Tests

```bash
make test-all          # mirrors CI: ruff + pytest per service, vitest for the gateway
```

Integration tests need a live graph and real keys; they are deselected by default.

### Deploy

Fly.io for the services, Cloudflare Pages for the SPA — see [DEPLOY.md](DEPLOY.md).

[^*]: laiive is a project of [ai safe earth](https://github.com/ai-safe-earth).
