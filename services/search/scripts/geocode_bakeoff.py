"""Geocoder bake-off - compare providers on laiive's real query corpus (D12 revisit).

Deliberately bypasses NominatimGeocoder: a cache hit would mask a live miss and
the shared 1 req/s gate would make this crawl. Each provider is called directly
behind its own documented rate limit. This is a one-off measurement run on a
single machine, which is what Nominatim's usage policy allows for bulk tasks.

Run:  cd services/search && uv run --no-sync python scripts/geocode_bakeoff.py
"""

import argparse
import json
import math
import os
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[3]
CACHES = [
    REPO / "services/pusher/.geocode_cache.json",
    REPO / "services/search/.geocode_cache.json",
]

# Part 2 of the plan depends on these resolving; nothing in the cached corpus
# exercises a sub-city area or a landmark.
PLACES = [
    "Kreuzberg, Berlin",
    "Neukolln, Berlin",
    "Prenzlauer Berg, Berlin",
    "Friedrichshain, Berlin",
    "Mitte, Berlin",
    "Wedding, Berlin",
    "Malasana, Madrid",
    "Lavapies, Madrid",
    "Chueca, Madrid",
    "La Latina, Madrid",
    "Chamberi, Madrid",
    "Salamanca, Madrid",
    "Gracia, Barcelona",
    "El Raval, Barcelona",
    "Poblenou, Barcelona",
    "Gotico, Barcelona",
    "Sant Antoni, Barcelona",
    "Barceloneta, Barcelona",
    "Sagrada Familia, Barcelona",
    "Puerta del Sol, Madrid",
    "Alexanderplatz, Berlin",
    "Parc Guell, Barcelona",
]

UA = "laiive/0.2 (geocoder bake-off; contact: arroscar@gmail.com)"

# An answer further than this from the centroid of the city the query names is
# scored WRONG rather than a hit. Generous on purpose -- it only catches answers
# in the wrong metro area, not merely imprecise ones.
PLAUSIBLE_KM = 25


# -- providers ---------------------------------------------------------------
# Each returns dict(lat, lng, country_code, display_name, bbox) or None.
# bbox is (south, north, west, east) or None.


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _parse_nominatim_hit(h):
    bb = h.get("boundingbox")
    return {
        "lat": float(h["lat"]),
        "lng": float(h["lon"]),
        "country_code": (h.get("address", {}).get("country_code") or "").upper(),
        "display_name": h.get("display_name", ""),
        "bbox": tuple(float(x) for x in bb) if bb and len(bb) == 4 else None,
    }


def p_nominatim(q, client):
    r = client.get(
        NOMINATIM_URL,
        params={"q": q, "format": "jsonv2", "addressdetails": 1, "limit": 1},
        headers={"User-Agent": UA},
        timeout=20,
    )
    r.raise_for_status()
    hits = r.json()
    return _parse_nominatim_hit(hits[0]) if hits else None


_CENTROIDS: dict = {}


def _centroid(city, client):
    """City centroid, fetched once per city. Reference for 'is this plausible'."""
    if city not in _CENTROIDS:
        _CENTROIDS[city] = p_nominatim(city, client)
    return _CENTROIDS[city]


def p_nominatim_struct(q, client):
    """Same API, structured params instead of free text.

    Nominatim documents `amenity`/`city`/`country` as the intended way to ask
    for a named POI in a place, rather than concatenating everything into `q`.
    """
    parts = [p.strip() for p in q.split(",") if p.strip()]
    params = {"format": "jsonv2", "addressdetails": 1, "limit": 1}
    if len(parts) == 1:
        params["city"] = parts[0]
    else:
        params["amenity"], params["city"] = parts[0], parts[-1]
    r = client.get(NOMINATIM_URL, params=params, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    hits = r.json()
    return _parse_nominatim_hit(hits[0]) if hits else None


def p_nominatim_top5(q, client):
    """Same API, but pick the nearest plausible candidate instead of hits[0].

    The confidently-wrong answers all came from blindly trusting rank 1 --
    'oasys, barcelona' resolves to a theme park 627 km away. If a candidate in
    the right metro area exists further down the list, prefer it.
    """
    r = client.get(
        NOMINATIM_URL,
        params={"q": q, "format": "jsonv2", "addressdetails": 1, "limit": 5},
        headers={"User-Agent": UA},
        timeout=20,
    )
    r.raise_for_status()
    hits = [_parse_nominatim_hit(h) for h in r.json()]
    if not hits:
        return None
    city = q.split(",")[-1].strip()
    ref = _centroid(city, client) if len(q.split(",")) > 1 else None
    if not ref:
        return hits[0]
    scored = sorted(
        (haversine_m((h["lat"], h["lng"]), (ref["lat"], ref["lng"])), h) for h in hits
    )
    best_km, best = scored[0][0] / 1000, scored[0][1]
    return best if best_km <= PLAUSIBLE_KM else None


def p_photon(q, client):
    r = client.get(
        "https://photon.komoot.io/api",
        params={"q": q, "limit": 1},
        headers={"User-Agent": UA},
        timeout=20,
    )
    r.raise_for_status()
    feats = r.json().get("features") or []
    if not feats:
        return None
    f = feats[0]
    lon, lat = f["geometry"]["coordinates"]
    pr = f.get("properties", {})
    ext = pr.get("extent")  # [west, north, east, south]
    name = ", ".join(
        str(pr[k]) for k in ("name", "street", "city", "country") if pr.get(k)
    )
    return {
        "lat": lat,
        "lng": lon,
        "country_code": (pr.get("countrycode") or "").upper(),
        "display_name": name,
        "bbox": (ext[3], ext[1], ext[0], ext[2]) if ext and len(ext) == 4 else None,
    }


def p_locationiq(q, client):
    r = client.get(
        "https://us1.locationiq.com/v1/search",
        params={
            "key": os.environ.get("LOCATIONIQ_API_KEY", ""),
            "q": q,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
        },
        headers={"User-Agent": UA},
        timeout=20,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    hits = r.json()
    if not hits:
        return None
    h = hits[0]
    bb = h.get("boundingbox")
    return {
        "lat": float(h["lat"]),
        "lng": float(h["lon"]),
        "country_code": (h.get("address", {}).get("country_code") or "").upper(),
        "display_name": h.get("display_name", ""),
        "bbox": tuple(float(x) for x in bb) if bb and len(bb) == 4 else None,
    }


def p_geoapify(q, client):
    r = client.get(
        "https://api.geoapify.com/v1/geocode/search",
        params={
            "text": q,
            "apiKey": os.environ.get("GEOAPIFY_API_KEY", ""),
            "limit": 1,
        },
        timeout=20,
    )
    r.raise_for_status()
    feats = r.json().get("features") or []
    if not feats:
        return None
    pr = feats[0].get("properties", {})
    bb = pr.get("bbox") or {}
    return {
        "lat": pr["lat"],
        "lng": pr["lon"],
        "country_code": (pr.get("country_code") or "").upper(),
        "display_name": pr.get("formatted", ""),
        "bbox": (bb["lat1"], bb["lat2"], bb["lon1"], bb["lon2"]) if bb else None,
    }


PROVIDERS = {
    "nominatim": (p_nominatim, 1.1, None),
    "nom_struct": (p_nominatim_struct, 1.1, None),
    "nom_top5": (p_nominatim_top5, 1.1, None),
    "photon": (p_photon, 1.1, None),
    "locationiq": (p_locationiq, 0.55, "LOCATIONIQ_API_KEY"),
    "geoapify": (p_geoapify, 0.25, "GEOAPIFY_API_KEY"),
}


# -- corpus ------------------------------------------------------------------


def short_form(q):
    """'venue, street, 08038 barcelona, spain, barcelona' -> 'venue, barcelona'."""
    parts = [p.strip() for p in q.split(",") if p.strip()]
    if len(parts) <= 2:
        return None
    return f"{parts[0]}, {parts[-1]}"


def build_corpus():
    cached = {}
    for path in CACHES:
        if path.exists():
            cached.update(json.loads(path.read_text(encoding="utf-8")))
    cities = {k for k in cached if "," not in k}
    rows = []
    for q, v in cached.items():
        if q in cities:
            rows.append(
                {
                    "query": q,
                    "kind": "city",
                    "form": "bare",
                    "nominatim_cached": v is not None,
                }
            )
            continue
        sf = short_form(q)
        rows.append(
            {
                "query": q,
                "kind": "venue",
                "form": "long" if sf else "short",
                "nominatim_cached": v is not None,
            }
        )
        if sf:
            rows.append(
                {
                    "query": sf,
                    "kind": "venue",
                    "form": "derived_short",
                    "nominatim_cached": cached.get(sf.lower(), "absent") is not None
                    if sf.lower() in cached
                    else None,
                }
            )
    for p in PLACES:
        rows.append(
            {"query": p, "kind": "place", "form": "short", "nominatim_cached": None}
        )
    seen, out = set(), []
    for r in rows:
        k = r["query"].lower()
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


# -- metrics -----------------------------------------------------------------


def haversine_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371000 * math.asin(math.sqrt(h))


def bbox_diag_km(bb):
    if not bb:
        return None
    s, n, w, e = bb
    return haversine_m((s, w), (n, e)) / 1000


def pct(n, d):
    return f"{100 * n / d:5.1f}%" if d else "    - "


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def p90(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * 0.9))] if xs else None


# -- main --------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--limit", type=int, default=0, help="cap corpus size for a smoke run"
    )
    ap.add_argument("--providers", default="", help="comma-separated subset")
    args = ap.parse_args()

    corpus = build_corpus()
    if args.limit:
        corpus = corpus[: args.limit]

    wanted = [p.strip() for p in args.providers.split(",") if p.strip()] or list(
        PROVIDERS
    )
    active, skipped = [], []
    for name in wanted:
        _fn, _delay, env = PROVIDERS[name]
        if env and not os.environ.get(env):
            skipped.append(f"{name} (no {env})")
        else:
            active.append(name)

    kinds = {
        k: sum(1 for r in corpus if r["kind"] == k) for k in ("venue", "place", "city")
    }
    print(
        f"corpus: {len(corpus)} queries "
        f"({kinds['venue']} venue, {kinds['place']} place, {kinds['city']} city)"
    )
    print(f"providers: {', '.join(active)}")
    if skipped:
        print(f"SKIPPED:   {', '.join(skipped)}")
    print()

    results = {}
    with httpx.Client(follow_redirects=True) as client:
        for name in active:
            fn, delay, _ = PROVIDERS[name]
            rows, t0 = [], time.time()
            for i, r in enumerate(corpus, 1):
                try:
                    got, err = fn(r["query"], client), None
                except Exception as e:
                    got, err = None, f"{type(e).__name__}: {e}"
                rows.append({**r, "result": got, "error": err})
                print(f"\r  {name}: {i}/{len(corpus)}", end="", flush=True)
                time.sleep(delay)
            results[name] = {"rows": rows, "wall_s": round(time.time() - t0, 1)}
            print(
                f"\r  {name}: {len(corpus)}/{len(corpus)}  ({results[name]['wall_s']}s)"
            )
    print()

    centroids = {
        name: {
            r["query"]: (r["result"]["lat"], r["result"]["lng"])
            for r in data["rows"]
            if r["kind"] == "city" and r["result"]
        }
        for name, data in results.items()
    }
    base = {
        r["query"]: r["result"]
        for r in results.get("nominatim", {}).get("rows", [])
        if r["result"]
    }

    def city_of(q):
        return q.split(",")[-1].strip().lower()

    def verdict(name, row):
        """hit / WRONG / miss.

        A raw hit is not a correct answer: neither provider exposes a
        confidence score, and both will happily answer 'queen's, barcelona'
        with a street in the Philippines. Anything further than PLAUSIBLE_KM
        from the centroid of the city the query itself names is counted
        WRONG, because it is strictly worse than a miss -- a miss triggers
        the writer's city-centroid fallback and a warning, while a wrong hit
        is written to the graph silently.
        """
        r = row["result"]
        if not r:
            return "miss"
        c = centroids[name].get(city_of(row["query"]))
        if not c:
            return "hit"
        if haversine_m((r["lat"], r["lng"]), c) / 1000 > PLAUSIBLE_KM:
            return "WRONG"
        return "hit"

    print("=" * 78)
    print("HIT RATE by query kind and form   (hit% / wrong / miss)")
    print("=" * 78)
    groups = [
        (
            "venue long-form (as the writer builds it)",
            lambda r: r["kind"] == "venue" and r["form"] == "long",
        ),
        (
            "venue short-form 'venue, city'",
            lambda r: r["kind"] == "venue" and r["form"] in ("short", "derived_short"),
        ),
        (
            "venue: NOMINATIM MISSED in prod",
            lambda r: r["kind"] == "venue" and r["nominatim_cached"] is False,
        ),
        ("neighbourhoods & landmarks", lambda r: r["kind"] == "place"),
        ("bare city", lambda r: r["kind"] == "city"),
    ]
    hdr = f"{'group':<42}" + "".join(f"{n:>22}" for n in active)
    print(hdr)
    print("-" * len(hdr))
    for label, pred in groups:
        line = f"{label:<42}"
        for name in active:
            rows = [r for r in results[name]["rows"] if pred(r)]
            v = [verdict(name, r) for r in rows]
            cell = f"{pct(v.count('hit'), len(rows))} {v.count('WRONG'):>3}w {v.count('miss'):>3}m"
            line += f"{cell:>22}"
        print(line)

    print()
    print("CONFIDENTLY WRONG - written to the graph with no warning:")
    any_wrong = False
    for name in active:
        for r in results[name]["rows"]:
            if verdict(name, r) == "WRONG":
                any_wrong = True
                c = centroids[name][city_of(r["query"])]
                off = haversine_m((r["result"]["lat"], r["result"]["lng"]), c) / 1000
                print(
                    f"  {name:<10} {r['query'][:40]:<42} -> "
                    f"{r['result']['display_name'][:40]:<42} {off:8.0f} km off"
                )
    if not any_wrong:
        print("  (none)")

    print()
    print("=" * 78)
    print("QUALITY")
    print("=" * 78)
    for name in active:
        rows = results[name]["rows"]
        hits = [r for r in rows if r["result"]]
        collapsed = 0
        for r in hits:
            c = centroids[name].get(city_of(r["query"]))
            if (
                c
                and r["kind"] == "venue"
                and haversine_m((r["result"]["lat"], r["result"]["lng"]), c) < 100
            ):
                collapsed += 1
        drifts = []
        if name != "nominatim":
            for r in hits:
                b = base.get(r["query"])
                if b:
                    drifts.append(
                        haversine_m(
                            (r["result"]["lat"], r["result"]["lng"]),
                            (b["lat"], b["lng"]),
                        )
                    )
        withbb = [r for r in hits if r["result"]["bbox"]]
        placebb = [
            bbox_diag_km(r["result"]["bbox"])
            for r in hits
            if r["kind"] == "place" and r["result"]["bbox"]
        ]
        cc_bad = sum(1 for r in hits if not r["result"]["country_code"])
        print(f"\n  {name}")
        print(
            f"    overall hit rate     {pct(len(hits), len(rows))}  ({len(hits)}/{len(rows)})"
        )
        print(
            f"    centroid-collapse    {pct(collapsed, len(hits))}  (venue answer <100m from its city centroid)"
        )
        print(f"    bbox returned        {pct(len(withbb), len(hits))}")
        if placebb:
            print(
                f"    neighbourhood bbox   median diagonal {median(placebb):.1f} km  (p90 {p90(placebb):.1f} km)"
            )
        print(
            f"    empty country_code   {pct(cc_bad, len(hits))}  (feeds the City MERGE key)"
        )
        if drifts:
            print(
                f"    drift vs nominatim   median {median(drifts):.0f} m  p90 {p90(drifts):.0f} m  (n={len(drifts)})"
            )
        print(f"    wall clock           {results[name]['wall_s']}s")

    print()
    print("=" * 78)
    print("WHAT EACH PROVIDER RECOVERS THAT NOMINATIM MISSED IN PRODUCTION")
    print("=" * 78)
    for q in [
        r["query"]
        for r in corpus
        if r["kind"] == "venue" and r["nominatim_cached"] is False
    ]:
        line = f"  {q[:52]:<54}"
        for name in active:
            got = next(
                (r["result"] for r in results[name]["rows"] if r["query"] == q), None
            )
            line += f"{('HIT' if got else '-'):>12}"
        print(line)

    out = Path(os.environ.get("CLAUDE_JOB_DIR", ".")) / "tmp" / "geocode_bakeoff.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"\nraw results -> {out}")


if __name__ == "__main__":
    main()
