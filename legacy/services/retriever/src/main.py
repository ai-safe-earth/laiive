from src.config import settings
from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic
from llama_index.llms.ollama import Ollama
from llama_index.llms.gemini import Gemini
from llama_index.core.llms import LLM
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime
from loguru import logger
import time
from contextlib import contextmanager


today = date.today()

engine = create_async_engine(settings.postgres_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def llm_factory() -> LLM:
    logger.info(f"Initializing LLM provider: {settings.llm_provider}")

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        return OpenAI(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )

    elif settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when using Anthropic provider"
            )
        return Anthropic(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,  # e.g., "claude-3-5-sonnet-20241022"
            temperature=settings.llm_temperature,
        )

    elif settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider")
        return Gemini(
            api_key=settings.gemini_api_key,
            model=settings.llm_model,  # e.g., "gemini-1.5-pro", "gemini-1.5-flash"
            temperature=settings.llm_temperature,
        )

    elif settings.llm_provider == "ollama":
        logger.info(
            f"Using Ollama with model: {settings.llm_model}, base_url: {settings.ollama_base_url}, temperature: {settings.llm_temperature}"
        )
        return Ollama(
            model=settings.llm_model,  # e.g., "llama2", "mistral"
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
            timeout=120.0,
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


llm = llm_factory()


@contextmanager
def log_timing(description: str):
    start = time.perf_counter()
    logger.info(f"⏱️  Starting: {description}")
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(
            f"✓ Completed: {description} in {elapsed:.3f}s ({elapsed*1000:.1f}ms)"
        )


async def get_response(message, filters_info) -> str:
    request_start = time.perf_counter()

    logger.info("=" * 80)
    logger.info("NEW REQUEST")
    logger.info(f"User message: {message}")
    logger.info(f"Filters received: {filters_info}")

    def build_query(filters) -> tuple[str, dict]:
        with log_timing("Query building"):
            base_query = """
            WITH event_artist_ids AS (
            SELECT
                e.id AS event_id,
                UNNEST(ARRAY[
                e.artist1_id, e.artist2_id, e.artist3_id, e.artist4_id, e.artist5_id,
                e.artist6_id, e.artist7_id, e.artist8_id, e.artist9_id, e.artist10_id
                ]) AS artist_id
            FROM events e
            )
            SELECT
            -- all event fields
            e.*,
            -- venue fields (prefixed to avoid name collisions)
            v.id          AS venue_id,
            v.name        AS venue_name,
            v.description AS venue_description,
            v.address     AS venue_address,
            v.city        AS venue_city,
            v.country     AS venue_country,
            v.capacity    AS venue_capacity,
            v.latitude    AS venue_latitude,
            v.longitude   AS venue_longitude,
            v.link        AS venue_link,
            v.image       AS venue_image,
            -- artists:
            -- 1) human-friendly list of names
            STRING_AGG(DISTINCT a.name, ', ' ORDER BY a.name) AS artist_names,
            -- 2) full JSON objects
            JSONB_AGG(
                DISTINCT JSONB_BUILD_OBJECT(
                'id', a.id,
                'name', a.name,
                'description', a.description,
                'genres', a.genres,
                'link', a.link,
                'image', a.image,
                'country', a.country,
                'city', a.city
                )
            ) FILTER (WHERE a.id IS NOT NULL) AS artists_json
            FROM events e
            JOIN venues v ON v.id = e.venue_id
            LEFT JOIN event_artist_ids ea ON ea.event_id = e.id
            LEFT JOIN artists a ON a.id = ea.artist_id
            """

            conditions = []
            params = {}

            if filters.place:
                conditions.append("v.city = :city")
                params["city"] = filters.place
                logger.info(f"Filter: City = {filters.place}")

            if filters.dates:
                logger.info(f"Filter: Processing {len(filters.dates)} dates")
                logger.info(f"Date range: {filters.dates[0]} to {filters.dates[-1]}")

                date_conditions = []
                for idx, date_str in enumerate(filters.dates):
                    date_param = f"date_{idx}"
                    date_conditions.append(
                        f"(e.start_date <= :{date_param} AND COALESCE(e.end_date, e.start_date) >= :{date_param})"
                    )
                    params[date_param] = datetime.strptime(date_str, "%Y-%m-%d").date()

                if date_conditions:
                    conditions.append(f"({' OR '.join(date_conditions)})")
                    logger.info(f"Generated {len(date_conditions)} date conditions")

            if conditions:
                query = f"{base_query}\nWHERE {' AND '.join(conditions)}"
            else:
                query = base_query

            query += (
                "\nGROUP BY e.id, v.id\nORDER BY e.start_date, e.start_time NULLS LAST"
            )

            logger.debug(f"Full SQL query:\n{query}")
            logger.info(f"Query params count: {len(params)}")
            return query, params

    async def execute_query(query: str, params: dict) -> str:
        try:
            logger.info("-" * 80)
            logger.info("EXECUTING DATABASE QUERY")

            with log_timing("Database query execution"):
                async with AsyncSessionLocal() as session:
                    db_start = time.perf_counter()
                    result = await session.execute(sqlalchemy.text(query), params)
                    db_elapsed = time.perf_counter() - db_start
                    logger.info(f"  → SQL execution: {db_elapsed:.3f}s")

                    fetch_start = time.perf_counter()
                    rows = result.fetchall()
                    fetch_elapsed = time.perf_counter() - fetch_start
                    logger.info(f"  → Fetch rows: {fetch_elapsed:.3f}s")

                    logger.info(f"✓ Query returned {len(rows)} events")

                    if rows:
                        sample_event = dict(rows[0]._mapping)
                        logger.debug(f"Sample event keys: {list(sample_event.keys())}")
                        logger.debug(f"Sample event: {sample_event}")

                    process_start = time.perf_counter()
                    events_list = [dict(row._mapping) for row in rows]
                    events_str = str(events_list)
                    process_elapsed = time.perf_counter() - process_start
                    logger.info(f"  → Process results: {process_elapsed:.3f}s")
                    logger.info(f"Events data size: {len(events_str)} characters")

                    return events_str
        except Exception as e:
            logger.error(f"✗ Database error: {e}", exc_info=True)
            return f"Error querying database: {str(e)}"

    try:
        query, params = build_query(filters_info)
    except Exception as e:
        logger.error(f"✗ Query building error: {e}", exc_info=True)
        return f"Sorry, I encountered an error processing your filters: {str(e)}"

    filtered_events = await execute_query(query, params)

    with log_timing("Prompt construction"):
        prompt = f"""
        You are a helpful assistant that can answer questions about musical life events.
        You will be given the location and date range of dates that the user is interested in.
        You will be given a list of filtered events from the events database.
        You need to answer to the user given information in the message.

        Today is {today}
        The user message is: {message}
        The filters are: {filters_info}
        The filtered events are: {filtered_events}

        IMPORTANT: return a list of maximum 5 events selected from the filtered events, that have better fit with the user message.
        The answer should be short and include: date, artists, price, link, venue name, link and a very short description of the event.

        The answer should be in the same language as the user message.
        """

    logger.info("-" * 80)
    logger.info("CALLING LLM")
    logger.info(f"Prompt length: {len(prompt)} characters")
    logger.info(f"Prompt preview (first 500 chars):\n{prompt[:500]}...")

    logger.debug(f"Full prompt:\n{prompt}")

    try:
        with log_timing(f"LLM call ({settings.llm_provider})"):
            response = llm.complete(prompt)

        logger.info(f"✓ LLM response received, length: {len(response.text)} characters")
        logger.debug(f"Full LLM response:\n{response.text}")

        # Total request time
        total_elapsed = time.perf_counter() - request_start
        logger.info("=" * 80)
        logger.info(
            f"🏁 TOTAL REQUEST TIME: {total_elapsed:.3f}s ({total_elapsed*1000:.1f}ms)"
        )
        logger.info("=" * 80)

        return response.text
    except Exception as e:
        logger.error(f"✗ LLM error: {e}", exc_info=True)
        total_elapsed = time.perf_counter() - request_start
        logger.info(f"🏁 REQUEST FAILED after {total_elapsed:.3f}s")
        logger.info("=" * 80)
        return f"Sorry, I encountered an error: {str(e)}"
