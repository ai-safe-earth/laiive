"""Name the genre an artist plays, so their events answer a genre query.

The retriever matches a genre through the event's own tag *or* through its
artists, and 13 of 43 artists in the graph carry neither. Every event by an
untagged artist is unreachable by the most common query shape in the product
("techno in Madrid"), even when the artist is a household name -- Placebo,
Aitana, Yandel, Vetusta Morla. Tagging the artist fixes every event they play,
past and future, which is why this works on artists and not on events.

No web search: unlike a small venue's street address, a touring artist's genre
is something the model already knows. What it must not do is guess -- a wrong
genre is a silent miscategorisation, exactly like a wrong pin, and it is worse
than no tag because no tag at least leaves the event findable every other way.

Tests patch `_client` (see tests/conftest.py).
"""

import json

from laiive_shared.drafts import strip_fences
from laiive_shared.normalize import genre_slug
from loguru import logger
from openai import OpenAI

from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

# One call for the whole batch: the model needs no context per artist, and the
# backlog is bounded by how many untagged artists exist at all.
BATCH = 25

GENRE_PROMPT = """For each musical artist below, name the single genre they are best known for.

Return ONLY JSON: {{"artists": [{{"name": "<exactly as given>", "genre": "<slug>"}}]}}

Rules:
- The genre is a lowercase-hyphenated slug: "indie-rock", "reggaeton", "jazz".
- ONE genre, the primary one. Not a list, not a fusion of everything they did.
- Use the plain, widely used name for the style. Not a regional scene label, not
  a decade, not a nationality.
- If you do not recognise the artist with confidence, set genre to null. A wrong
  genre is worse than none. Do not infer a genre from the name's language.

Artists:
{artists}"""


def resolve_genres(names: list[str]) -> dict[str, str]:
    """Artist name -> genre slug, omitting every artist the model did not know.

    Never raises: this enriches a graph that is already usable without it.
    """
    resolved: dict[str, str] = {}
    for start in range(0, len(names), BATCH):
        batch = names[start : start + BATCH]
        try:
            response = _client.chat.completions.create(
                model=settings.extraction_model,
                messages=[
                    {
                        "role": "user",
                        "content": GENRE_PROMPT.format(
                            artists="\n".join(f"- {name}" for name in batch)
                        ),
                    }
                ],
                temperature=0,
            )
            data = json.loads(strip_fences(response.choices[0].message.content or ""))
        except Exception as e:
            logger.warning(f"Genre lookup failed for {len(batch)} artists: {e}")
            continue

        asked = {name: name for name in batch}
        for row in data.get("artists") or []:
            name, genre = row.get("name"), row.get("genre")
            # Only names we asked about: the model occasionally helpfully
            # invents a support act.
            if not genre or name not in asked:
                continue
            slug = genre_slug(str(genre))
            if slug:
                resolved[asked[name]] = slug
    return resolved
