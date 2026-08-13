"""Seed a small dev dataset into the laiive graph (docs/refactor/03-ontology.md).

Idempotent: MERGE on the identity keys (name_norm / name_norm+country_code /
slug), CREATE-once semantics via ON CREATE. Event dates are computed relative
to today so the dataset never goes stale. Embeddings (text-embedding-3-small,
1536-d) are written unless --no-embeddings is passed.

Run: cd services/retriever && uv run python -m agent.scripts.seed [--no-embeddings]
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from laiive_shared.neo4j_writer import backfill_embeddings
from laiive_shared.normalize import norm
from neo4j import GraphDatabase

from config import settings


CITIES: list[dict[str, Any]] = [
    {
        "name": "Madrid",
        "country_code": "ES",
        "country_name": "Spain",
        "lat": 40.4168,
        "lng": -3.7038,
    },
    {
        "name": "Barcelona",
        "country_code": "ES",
        "country_name": "Spain",
        "lat": 41.3874,
        "lng": 2.1686,
    },
    {
        "name": "Berlin",
        "country_code": "DE",
        "country_name": "Germany",
        "lat": 52.5200,
        "lng": 13.4050,
    },
]

GENRES: list[dict[str, str]] = [
    {"slug": "jazz", "name": "Jazz"},
    {"slug": "techno", "name": "Techno"},
    {"slug": "indie-rock", "name": "Indie Rock"},
    {"slug": "flamenco", "name": "Flamenco"},
    {"slug": "electronica", "name": "Electronica"},
]

VENUES: list[dict[str, Any]] = [
    {
        "name": "Café Central",
        "city": "Madrid",
        "venue_type": "club",
        "address": "Plaza del Ángel 10, Madrid",
        "lat": 40.4146,
        "lng": -3.7004,
        "capacity": 90,
        "description": "Historic, intimate jazz club near Plaza Santa Ana; nightly live sets since 1982.",
    },
    {
        "name": "Sala El Sol",
        "city": "Madrid",
        "venue_type": "club",
        "address": "Calle Jardines 3, Madrid",
        "lat": 40.4189,
        "lng": -3.7005,
        "capacity": 400,
        "description": "Legendary Movida-era basement club hosting indie and rock shows.",
    },
    {
        "name": "Razzmatazz",
        "city": "Barcelona",
        "venue_type": "club",
        "address": "Carrer dels Almogàvers 122, Barcelona",
        "lat": 41.3977,
        "lng": 2.1916,
        "capacity": 3000,
        "description": "Five-room warehouse club, the heart of Barcelona's electronic and indie scene.",
    },
    {
        "name": "Palau de la Música Catalana",
        "city": "Barcelona",
        "venue_type": "concert_hall",
        "address": "C/ Palau de la Música 4-6, Barcelona",
        "lat": 41.3875,
        "lng": 2.1753,
        "capacity": 2200,
        "description": "Modernist concert hall and UNESCO site with world-class acoustics.",
    },
    {
        "name": "Berghain",
        "city": "Berlin",
        "venue_type": "club",
        "address": "Am Wriezener Bahnhof, Berlin",
        "lat": 52.5111,
        "lng": 13.4433,
        "capacity": 1500,
        "description": "Techno institution in a former power plant; marathon weekend club nights.",
    },
    {
        "name": "Quasimodo",
        "city": "Berlin",
        "venue_type": "club",
        "address": "Kantstraße 12a, Berlin",
        "lat": 52.5058,
        "lng": 13.3230,
        "capacity": 300,
        "description": "Cellar jazz club under the Delphi theatre, running since 1975.",
    },
]

ARTISTS: list[dict[str, Any]] = [
    {
        "name": "Marta Sánchez Trio",
        "genres": ["jazz"],
        "city": "Madrid",
        "description": "Piano-led modern jazz trio blending Iberian folk motifs with post-bop.",
    },
    {
        "name": "Niña de las Dunas",
        "genres": ["flamenco"],
        "city": "Madrid",
        "description": "Young cantaora pushing flamenco into electronic textures.",
    },
    {
        "name": "Els Vermuts",
        "genres": ["indie-rock"],
        "city": "Barcelona",
        "description": "Jangly Catalan indie quartet with bittersweet Mediterranean choruses.",
    },
    {
        "name": "Laia Ferrer",
        "genres": ["electronica", "techno"],
        "city": "Barcelona",
        "description": "Live-hardware techno producer; melodic, dubby late-night sets.",
    },
    {
        "name": "Klangfeld",
        "genres": ["techno"],
        "city": "Berlin",
        "description": "Berlin duo of hypnotic, industrial-leaning techno.",
    },
    {
        "name": "Ana Beck Quartet",
        "genres": ["jazz"],
        "city": "Berlin",
        "description": "Saxophone quartet at the crossroads of European free jazz and groove.",
    },
    {
        "name": "Costa Norte",
        "genres": ["indie-rock"],
        "city": "Madrid",
        "description": "Shoegaze-tinted indie rock, walls of guitar and soft Spanish vocals.",
    },
    {
        "name": "DJ Petra",
        "genres": ["techno", "electronica"],
        "city": "Berlin",
        "description": "Selector of raw warehouse techno and Detroit electro.",
    },
]

# (name, artists, venue, genre, days_from_now, hour, price_min, price_max)
EVENTS: list[tuple[str, list[str], str, str, int, int, int, int]] = [
    (
        "Noche de Jazz: Marta Sánchez Trio",
        ["Marta Sánchez Trio"],
        "Café Central",
        "jazz",
        0,
        21,
        15,
        20,
    ),
    (
        "Flamenco Eléctrico",
        ["Niña de las Dunas"],
        "Sala El Sol",
        "flamenco",
        1,
        22,
        18,
        18,
    ),
    (
        "Els Vermuts + guests",
        ["Els Vermuts"],
        "Razzmatazz",
        "indie-rock",
        3,
        21,
        16,
        22,
    ),
    ("Laia Ferrer live A/V", ["Laia Ferrer"], "Razzmatazz", "techno", 5, 23, 20, 25),
    ("Klangfeld Nacht", ["Klangfeld", "DJ Petra"], "Berghain", "techno", 2, 23, 20, 20),
    ("Ana Beck Quartet", ["Ana Beck Quartet"], "Quasimodo", "jazz", 4, 20, 22, 28),
    (
        "Costa Norte en concierto",
        ["Costa Norte"],
        "Sala El Sol",
        "indie-rock",
        8,
        21,
        14,
        14,
    ),
    (
        "Jazz al Palau",
        ["Marta Sánchez Trio", "Ana Beck Quartet"],
        "Palau de la Música Catalana",
        "jazz",
        12,
        20,
        30,
        60,
    ),
    ("Techno Sunday", ["DJ Petra"], "Berghain", "techno", 6, 22, 18, 18),
    (
        "Vermut & Volume",
        ["Els Vermuts", "Costa Norte"],
        "Sala El Sol",
        "indie-rock",
        15,
        20,
        15,
        20,
    ),
    (
        "Dunas: cante y máquinas",
        ["Niña de las Dunas"],
        "Palau de la Música Catalana",
        "flamenco",
        21,
        20,
        25,
        45,
    ),
    (
        "Ferrer x Klangfeld",
        ["Laia Ferrer", "Klangfeld"],
        "Razzmatazz",
        "techno",
        30,
        23,
        22,
        30,
    ),
]


def embed_texts(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(model=settings.embeddings_model, input=texts)
    return [d.embedding for d in resp.data]


def seed(with_embeddings: bool = True) -> None:
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    now = datetime.now(timezone.utc)

    with driver.session(database=settings.neo4j_database) as s:
        print("Cities...")
        for c in CITIES:
            s.run(
                """
                MERGE (c:City {name_norm: $name_norm, country_code: $country_code})
                ON CREATE SET c.name = $name, c.country_name = $country_name,
                              c.location = point({latitude: $lat, longitude: $lng})
                """,
                name_norm=norm(c["name"]),
                **c,
            )

        print("Genres...")
        for g in GENRES:
            s.run("MERGE (g:Genre {slug: $slug}) ON CREATE SET g.name = $name", **g)

        print("Venues...")
        for v in VENUES:
            s.run(
                """
                MATCH (c:City {name_norm: $city_norm})
                MERGE (v:Venue {name_norm: $name_norm})
                ON CREATE SET v.uid = $uid, v.name = $name, v.venue_type = $venue_type,
                              v.address = $address, v.capacity = $capacity,
                              v.description = $description,
                              v.location = point({latitude: $lat, longitude: $lng}),
                              v.source = 'seed', v.created_at = datetime()
                MERGE (v)-[:LOCATED_IN]->(c)
                """,
                name_norm=norm(v["name"]),
                city_norm=norm(v["city"]),
                uid=str(uuid.uuid4()),
                **v,
            )

        print("Artists...")
        for a in ARTISTS:
            s.run(
                """
                MATCH (c:City {name_norm: $city_norm})
                MERGE (a:Artist {name_norm: $name_norm})
                ON CREATE SET a.uid = $uid, a.name = $name,
                              a.description = $description,
                              a.source = 'seed', a.created_at = datetime()
                MERGE (a)-[:BASED_IN]->(c)
                WITH a
                UNWIND $genres AS slug
                MATCH (g:Genre {slug: slug})
                MERGE (a)-[:HAS_GENRE]->(g)
                """,
                name_norm=norm(a["name"]),
                city_norm=norm(a["city"]),
                uid=str(uuid.uuid4()),
                **a,
            )

        print("Events...")
        for name, artists, venue, genre, days, hour, pmin, pmax in EVENTS:
            start_at = (now + timedelta(days=days)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            s.run(
                """
                MATCH (v:Venue {name_norm: $venue_norm})
                MERGE (e:Event {name_norm: $name_norm, start_at: datetime($start_at)})
                ON CREATE SET e.uid = $uid, e.name = $name,
                              e.description = $description,
                              e.price_min = $pmin, e.price_max = $pmax,
                              e.price_currency = 'EUR',
                              e.status = 'scheduled', e.source = 'seed',
                              e.created_at = datetime()
                MERGE (e)-[:HOSTED_AT]->(v)
                WITH e
                MATCH (g:Genre {slug: $genre})
                MERGE (e)-[:HAS_GENRE]->(g)
                WITH e
                UNWIND $artists AS artist_norm
                MATCH (a:Artist {name_norm: artist_norm})
                MERGE (a)-[:PERFORMS_AT]->(e)
                """,
                name_norm=norm(name),
                venue_norm=norm(venue),
                artists=[norm(a) for a in artists],
                uid=str(uuid.uuid4()),
                name=name,
                genre=genre,
                start_at=start_at.isoformat(),
                pmin=float(pmin),
                pmax=float(pmax),
                description=f"{', '.join(artists)} live at {venue}.",
            )

        if with_embeddings:
            print("Embeddings...")
            count = backfill_embeddings(s, embed_texts, settings.embeddings_model)
            print(f"  {count} nodes embedded")

    driver.close()
    print("\nSeed complete.")


if __name__ == "__main__":
    seed(with_embeddings="--no-embeddings" not in sys.argv)
