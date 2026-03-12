import os
from openai import OpenAI

MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def embed_one(text: str) -> list[float]:
    resp = client.embeddings.create(model=MODEL, input=text)
    return resp.data[0].embedding


def upsert_event(session, event: dict):
    text = "\n".join([
        f"Event: {event.get('name','')}",
        f"Description: {event.get('description','')}",
        f"Start: {event.get('start_at','')}",
    ]).strip()

    vec = embed_one(text)

    session.run("""
        MERGE (e:Event {id: $id})
        SET e.name = $name,
            e.description = $description,
            e.start_at = $start_at,
            e.price_amount = $price_amount,
            e.price_currency = $price_currency,
            e.embedding = $embedding,
            e.embedding_model = $model,
            e.embedding_updated_at = datetime()
    """, **event, embedding=vec, model=MODEL)
