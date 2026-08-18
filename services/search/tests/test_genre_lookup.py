"""Naming an artist's genre — and refusing to invent one.

The retriever reaches a genre through the event or through its artists, so an
untagged artist hides every event they play. The failure mode worth testing is
not the miss but the confident wrong answer: an artist the model does not know
must come back absent, never guessed.
"""

import json

from agent import genre_lookup


def reply(client, payload):
    client.chat.completions.create.return_value.choices[0].message.content = json.dumps(
        payload
    )


def test_genres_come_back_as_slugs(mock_genre_lookup):
    reply(
        mock_genre_lookup,
        {
            "artists": [
                {"name": "Vetusta Morla", "genre": "Indie Rock"},
                {"name": "Yandel", "genre": "reggaeton"},
            ]
        },
    )
    assert genre_lookup.resolve_genres(["Vetusta Morla", "Yandel"]) == {
        "Vetusta Morla": "indie-rock",
        "Yandel": "reggaeton",
    }


def test_an_unrecognised_artist_is_omitted_not_guessed(mock_genre_lookup):
    reply(
        mock_genre_lookup,
        {
            "artists": [
                {"name": "Placebo", "genre": "alternative-rock"},
                {"name": "Local Support Act", "genre": None},
            ]
        },
    )
    resolved = genre_lookup.resolve_genres(["Placebo", "Local Support Act"])
    assert resolved == {"Placebo": "alternative-rock"}


def test_an_artist_we_did_not_ask_about_is_ignored(mock_genre_lookup):
    """The model occasionally volunteers a name of its own."""
    reply(
        mock_genre_lookup,
        {
            "artists": [
                {"name": "Aitana", "genre": "pop"},
                {"name": "Somebody Else", "genre": "jazz"},
            ]
        },
    )
    assert genre_lookup.resolve_genres(["Aitana"]) == {"Aitana": "pop"}


def test_a_broken_reply_costs_nothing(mock_genre_lookup):
    mock_genre_lookup.chat.completions.create.side_effect = RuntimeError("502")
    assert genre_lookup.resolve_genres(["Aitana"]) == {}


def test_the_batch_is_split(mock_genre_lookup):
    reply(mock_genre_lookup, {"artists": []})
    genre_lookup.resolve_genres([f"Artist {i}" for i in range(genre_lookup.BATCH + 1)])
    assert mock_genre_lookup.chat.completions.create.call_count == 2
