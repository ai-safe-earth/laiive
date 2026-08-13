from neo4j import GraphDatabase
from config import settings


def seed(uri, user, password, database="neo4j"):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            # --- Genres ---
            for genre in [
                {"slug": "techno", "name": "Techno"},
                {"slug": "house", "name": "House"},
                {"slug": "indie-rock", "name": "Indie Rock"},
                {"slug": "jazz", "name": "Jazz"},
                {"slug": "electronic", "name": "Electronic"},
            ]:
                session.run(
                    """
                    MERGE (g:Genre {slug: $slug})
                    SET g.name = $name
                """,
                    **genre,
                )

            # --- Cities ---
            for city in [
                {"name": "Berlin", "country": "DE"},
                {"name": "Amsterdam", "country": "NL"},
                {"name": "London", "country": "GB"},
            ]:
                session.run(
                    """
                    MERGE (c:City {name: $name})
                    SET c.country = $country
                """,
                    **city,
                )

            # --- Venues ---
            venues = [
                {
                    "ra_id": "ra:venue:1",
                    "name": "Berghain",
                    "description": "Legendary Berlin techno club known for marathon sets and strict door policy",
                    "address": "Am Wriezener Bahnhof, 10243 Berlin",
                    "city": "Berlin",
                    "country": "DE",
                    "capacity": 1500,
                    "latitude": 52.5109,
                    "longitude": 13.4432,
                },
                {
                    "ra_id": "ra:venue:2",
                    "name": "Fabric",
                    "description": "Iconic London nightclub, home of drum and bass and techno since 1999",
                    "address": "77a Charterhouse St, London EC1M 6HJ",
                    "city": "London",
                    "country": "GB",
                    "capacity": 1800,
                    "latitude": 51.5204,
                    "longitude": -0.1019,
                },
                {
                    "ra_id": "ra:venue:3",
                    "name": "Shelter",
                    "description": "Underground Amsterdam club with a focus on house and techno",
                    "address": "Overhoeksplein 3, 1031 KS Amsterdam",
                    "city": "Amsterdam",
                    "country": "NL",
                    "capacity": 600,
                    "latitude": 52.3851,
                    "longitude": 4.9087,
                },
            ]

            for v in venues:
                session.run(
                    """
                    MERGE (v:Venue {ra_id: $ra_id})
                    SET v.name        = $name,
                        v.description = $description,
                        v.address     = $address,
                        v.city        = $city,
                        v.country     = $country,
                        v.capacity    = $capacity,
                        v.latitude    = $latitude,
                        v.longitude   = $longitude,
                        v.location    = point({latitude: $latitude, longitude: $longitude})
                """,
                    **v,
                )
                # Link to city
                session.run(
                    """
                    MATCH (v:Venue {ra_id: $ra_id}), (c:City {name: $city})
                    MERGE (v)-[:LOCATED_IN]->(c)
                """,
                    ra_id=v["ra_id"],
                    city=v["city"],
                )

            # --- Artists ---
            artists = [
                {
                    "ra_id": "ra:artist:1",
                    "spotify_id": "spotify:artist:amelielens",
                    "name": "Amelie Lens",
                    "description": "Belgian techno DJ and producer known for high-energy hypnotic sets",
                    "summary": "One of techno's most prominent figures since 2017",
                    "city": "Antwerp",
                    "country": "BE",
                    "genres": ["techno", "electronic"],
                },
                {
                    "ra_id": "ra:artist:2",
                    "spotify_id": "spotify:artist:bicep",
                    "name": "Bicep",
                    "description": "Belfast-born duo blending house, techno and euphoric rave sounds",
                    "summary": "Known for emotional, nostalgia-driven electronic music",
                    "city": "London",
                    "country": "GB",
                    "genres": ["house", "electronic"],
                },
                {
                    "ra_id": "ra:artist:3",
                    "spotify_id": "spotify:artist:objekt",
                    "name": "Objekt",
                    "description": "Berlin-based DJ and producer spanning techno, electro and breaks",
                    "summary": "Resident at Berghain, known for technically precise mixing",
                    "city": "Berlin",
                    "country": "DE",
                    "genres": ["techno", "electro"],
                },
            ]
            for a in artists:
                session.run(
                    """
                    MERGE (a:Artist {ra_id: $ra_id})
                    SET a.spotify_id  = $spotify_id,
                        a.name        = $name,
                        a.description = $description,
                        a.summary     = $summary,
                        a.city        = $city,
                        a.country     = $country,
                        a.genres      = $genres
                """,
                    **a,
                )
                # Link to genres
                for slug in a["genres"]:
                    session.run(
                        """
                        MATCH (a:Artist {ra_id: $ra_id}), (g:Genre {slug: $slug})
                        MERGE (a)-[:HAS_GENRE]->(g)
                    """,
                        ra_id=a["ra_id"],
                        slug=slug,
                    )

            # --- Events ---
            events = [
                {
                    "ra_id": "ra:event:1",
                    "name": "Amelie Lens at Berghain",
                    "description": "A night of pure hypnotic techno with Amelie Lens",
                    "start_at": "2026-04-01T23:00:00Z",
                    "end_at": "2026-04-02T10:00:00Z",
                    "price_min": 15.0,
                    "price_max": 20.0,
                    "price_currency": "EUR",
                    "ticket_url": "https://ra.co/events/1",
                    "status": "scheduled",
                    "artist_ra_id": "ra:artist:1",
                    "venue_ra_id": "ra:venue:1",
                    "genres": ["techno"],
                },
                {
                    "ra_id": "ra:event:2",
                    "name": "Bicep Live at Fabric",
                    "description": "Bicep bring their euphoric live show to fabric London",
                    "start_at": "2026-04-05T22:00:00Z",
                    "end_at": "2026-04-06T06:00:00Z",
                    "price_min": 20.0,
                    "price_max": 25.0,
                    "price_currency": "GBP",
                    "ticket_url": "https://ra.co/events/2",
                    "status": "scheduled",
                    "artist_ra_id": "ra:artist:2",
                    "venue_ra_id": "ra:venue:2",
                    "genres": ["house", "electronic"],
                },
                {
                    "ra_id": "ra:event:3",
                    "name": "Objekt at Shelter Amsterdam",
                    "description": "Objekt headlines Shelter for a night of electro and techno",
                    "start_at": "2026-04-10T23:00:00Z",
                    "end_at": "2026-04-11T08:00:00Z",
                    "price_min": 12.0,
                    "price_max": 15.0,
                    "price_currency": "EUR",
                    "ticket_url": "https://ra.co/events/3",
                    "status": "scheduled",
                    "artist_ra_id": "ra:artist:3",
                    "venue_ra_id": "ra:venue:3",
                    "genres": ["techno", "electro"],
                },
            ]
            for e in events:
                session.run(
                    """
                    MERGE (e:Event {ra_id: $ra_id})
                    SET e.name           = $name,
                        e.description    = $description,
                        e.start_at       = $start_at,
                        e.end_at         = $end_at,
                        e.price_min      = $price_min,
                        e.price_max      = $price_max,
                        e.price_currency = $price_currency,
                        e.ticket_url     = $ticket_url,
                        e.status         = $status
                """,
                    **{
                        k: v
                        for k, v in e.items()
                        if k not in ("artist_ra_id", "venue_ra_id", "genres")
                    },
                )

                # Link to artist
                session.run(
                    """
                    MATCH (e:Event {ra_id: $ra_id}), (a:Artist {ra_id: $artist_ra_id})
                    MERGE (a)-[:PERFORMS_AT]->(e)
                """,
                    ra_id=e["ra_id"],
                    artist_ra_id=e["artist_ra_id"],
                )

                # Link to venue
                session.run(
                    """
                    MATCH (e:Event {ra_id: $ra_id}), (v:Venue {ra_id: $venue_ra_id})
                    MERGE (e)-[:HOSTED_AT]->(v)
                """,
                    ra_id=e["ra_id"],
                    venue_ra_id=e["venue_ra_id"],
                )

                # Link to genres
                for slug in e["genres"]:
                    session.run(
                        """
                        MATCH (e:Event {ra_id: $ra_id}), (g:Genre {slug: $slug})
                        MERGE (e)-[:HAS_GENRE]->(g)
                    """,
                        ra_id=e["ra_id"],
                        slug=slug,
                    )

        print("✅ Seed data ready.")
    finally:
        driver.close()


if __name__ == "__main__":
    seed(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
