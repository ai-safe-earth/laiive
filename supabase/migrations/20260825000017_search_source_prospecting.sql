-- Source prospecting: find the sites worth sweeping, instead of hardcoding them.
--
-- Numbering note: 20260825000016 is reserved for phase D (orgs + claims), which
-- is designed but unshipped. This is 17; phase G's review-signal columns move
-- to 18.
--
-- Until now the only vouched sources were `SEED_SOURCES` in
-- services/search/agent/learning.py -- a Python dict, so adding one was a code
-- edit and a deploy. Prospecting produces them from a dry-run report a human
-- approves, exactly like a sweep produces events, so they have to live here.
--
-- The measurement that shaped this (277 stored sweep candidates, by domain):
-- completeness is a property of the source, not of the prompt. Aggregators
-- return index pages -- songkick 13% artists / 0% genre / 0% description,
-- eventbrite.it 5/0/5 -- while local agendas return the whole night:
-- mitosettembremusica 94/94/65, ecodibergamo 78/78/100, esmadrid 83/100/100.
-- The extraction prompt asks for every one of those fields on every page. So
-- ranking a source by `candidates_new` alone puts songkick's 24 bare listings
-- above ecodibergamo's 9 complete ones, and `fields_filled` below is what
-- stops it.

alter table public.search_sources
-- Localities this source covers. A province-wide agenda lists every town in
-- the province, which is what lets one weekly extract serve all of them
-- instead of one sweep per town (five queries x twenty towns would be 100
-- credits a week against a ~435/month budget).
add column cities text[] not null default '{}',  -- noqa: LT01
-- Pages fetched with Tavily /extract rather than found by search. Search
-- answers 106-156 characters for these; extract answers 18k-102k. Empty for a
-- domain that search reads perfectly well -- that one only needs `status`.
add column agenda_urls text[] not null default '{}',  -- noqa: LT01
-- How many distinct venues this domain has been seen listing. The aggregator
-- signal, and the one that needs no LLM: a domain returning for many venues of
-- one province is that province's agenda. Structural, so recomputed per
-- prospect run rather than decayed.
add column venues_covered real not null default 0,
-- Decayed like the counters beside it: the SUM of optional fields filled
-- across this domain's candidates, never the rate. A rate cannot be folded
-- through `(previous * decay) + observed` and stay a rate; the rate is
-- fields_filled / (candidates_new * fields_counted), computed at read time.
add column fields_filled real not null default 0,
-- Vouched for by a person, through the prospect review queue. Carries the same
-- weight as being in SEED_SOURCES: exempt from auto-blocking, and never
-- dropped from the focused search slot on a quiet fortnight. A source that
-- stops yielding is an extraction problem to look at, not a verdict.
add column vouched_by uuid,
add column vouched_at timestamptz;

-- The agenda read: every source vouched for a city being swept. Array
-- containment, so it wants GIN.
create index search_sources_cities_idx on public.search_sources using gin (cities);

-- Prospect runs are reports like any other: dry_run, reviewed by a human,
-- approved or dismissed. Reusing the queue rather than building a second one
-- also means the credit spend shows up in the same place the sweep's does.
--
-- The service must gate on `kind` at both approve paths -- a prospect report
-- approved through the event path would build an EventDraft out of a source
-- candidate and write nonsense.
alter table public.search_reports drop constraint search_reports_kind_check;

alter table public.search_reports add constraint search_reports_kind_check
check (kind in ('sweep', 'backfill', 'prospect'));
