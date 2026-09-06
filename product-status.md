# product-status.md — laiive (ai safe earth)

Record of non-code progress: branding, product strategy, docs and artwork.
Lives in the repo root next to `handoff.md`; read by the project tracker.
Engineering progress stays in `handoff.md`.

## Description

laiive is a global cultural agenda that connects people with live music events,
answering "what can I do tonight?" instead of returning a list to scroll. It
serves two sides: people who want to get out of the house and into a real room,
and the small promoters, venues and artists who need those people to know their
event exists.

## Strategy

Win the small and community-scale end of live culture that the big ticketing
platforms ignore, city by city, using an agent stack over a Neo4j knowledge
graph (Retriever for zero-click answers, Pusher for multimodal event ingestion
with guardrails and human-in-the-loop validation). The bet: promoter-published
supply, densified per city, produces answers good enough that laiive becomes the
default way to decide a night out — and that an explicitly AI-safe, anti-feed
position is a durable differentiator rather than a niche one.

## Log

| Date | Track | Title | Note |
|---|---|---|---|
| 2026-08-16 | ops | product-status.md created | Baseline captured from the public repo README. Everything below this line is progress recorded going forward. |
| 2026-08-16 | strategy | Baseline positioning recorded | Ethical AI / anti-feed cultural agenda; small and community-scale events, explicitly not stadium-scale; two-sided (public + promoters/artists). |
| 2026-08-16 | strategy | Architecture bet recorded | Retriever Agent (orchestrator over Neo4j, session-based queries), Pusher Agent (multimodal ingestion, router + extraction + guardrails + HITL), internet search demoted to complementary feed pending per-city supply density. |
| 2026-08-16 | branding | Identity baseline recorded | Lowercase `laiive`, 🫦 mark, direct second-person voice; laiive.com live as the public domain. |
| 2026-08-16 | docs | Project split defined | Claude Code owns the repo and implementation; this Claude project owns strategy, design, marketing and go-to-market. |
| 2026-08-29 | branding | Type scale replaced in brand-rules.md | The v1 scale (answers 15px, card meta 12.5px, pills 11px) was drawn on a 360px static mock and read as unusably small on a real phone — the app's natural environment. Replaced by one rem scale, ten named tokens from 11 to 28px, with every input at 16px so iOS stops zooming on focus. The rules now forbid hard-coded px sizes outright: px ignores the phone's own text-size setting. |

## Open questions

- Which city is the first real launch target, and what is the named supply source there (promoter network, venue list, scene contact)?
- Success metric for the current phase — events ingested, promoters onboarded, or answers accepted by users?
- Monetisation direction: promoter-side paid visibility, ticketing affiliate, public subscription, or none yet on purpose?
- How far do we lead with the political framing (community resilience, resistance to authoritarianism) in consumer-facing copy, versus keeping it in manifesto and org-level material?
- Which AI-safety claims are we willing to make publicly today, and what evidence backs each one?
- Is there a formal brand asset set (palette, type, logo lockups) or only the README artwork?

<!-- pmctl:product v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "updated": "2026-08-29",
  "description": "laiive is a global cultural agenda that connects people with live music events, answering 'what can I do tonight?' instead of returning a list to scroll. It serves people who want to get out of the house and into a real room, and the small promoters, venues and artists who need those people to know their event exists.",
  "strategy": "Win the small, community-scale end of live culture that big ticketing platforms ignore, city by city, using an agent stack over a Neo4j knowledge graph. The bet: promoter-published supply densified per city makes the answers good enough to become the default way to decide a night out, with an AI-safe, anti-feed position as the differentiator.",
  "productStatus": [
    { "date": "2026-08-16", "track": "ops", "title": "product-status.md created", "note": "Baseline captured from the public repo README" },
    { "date": "2026-08-16", "track": "strategy", "title": "Baseline positioning recorded", "note": "Ethical AI, anti-feed, small and community-scale events, two-sided public and promoter" },
    { "date": "2026-08-16", "track": "strategy", "title": "Architecture bet recorded", "note": "Retriever and Pusher agents over Neo4j, HITL validation, internet search as complementary feed only" },
    { "date": "2026-08-16", "track": "branding", "title": "Identity baseline recorded", "note": "Lowercase wordmark, lips mark, direct second-person voice, laiive.com" },
    { "date": "2026-08-16", "track": "docs", "title": "Project split defined", "note": "Claude Code owns implementation; Claude project owns strategy, design, marketing, GTM" },
    { "date": "2026-08-29", "track": "branding", "title": "Type scale replaced in brand-rules.md", "note": "The v1 scale was drawn on a 360px static mock and read as unusably small on a real phone. One rem scale, ten tokens from 11 to 28px, inputs at 16px; hard-coded px sizes now forbidden" }
  ]
}
```
