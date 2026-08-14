"""Which language the assistant answers in.

Both services already carried a prompt rule saying "reply in the language the
user writes in", and both ignored it: an English "jazz in Madrid" came back as
"Tres noches de jazz te esperan en Madrid", and an English flyer for a Spanish
venue got a Spanish handoff line. The rule sat near the top of a long system
prompt with a wall of Spanish proper nouns after it — and proper nouns are
exactly what a model reads as evidence of language.

So the language stops being a judgement the reply model makes in passing. It is
decided once per turn, from the user's own words, and handed to the reply
prompt as a fact. The retriever gets it free from the classifier (one more
field in a call it already makes); the pusher has no classifier, so
`detect_language` makes the one cheap call.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"

# Enough to name the language in a prompt instead of only its code — a model
# follows "Spanish (es)" more reliably than "es". Anything outside this map
# still works; the code goes through on its own.
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "it": "Italian",
    "ca": "Catalan",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "gl": "Galician",
    "eu": "Basque",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "ar": "Arabic",
}

_NAME_TO_CODE = {name.lower(): code for code, name in LANGUAGE_NAMES.items()}

# The one sentence that makes detection work. Shared by every prompt that has
# to decide a language, because the failure mode is always the same one.
DETECTION_RULE = (
    "Judge the language by the user's own words — their function words, "
    "grammar and spelling. Proper nouns are NOT evidence: city, venue, artist "
    "and event names keep their original spelling in every language, so "
    '"jazz in Madrid" is English and "concierto in Berlin" is Spanish.'
)

_DETECT_PROMPT = f"""Identify the language of the message below.

{DETECTION_RULE}

Event listings are the hard case: they are mostly names, and the handful of
ordinary words is the whole signal. Weigh those words, and nothing else.
  "Marta Sanchez Trio plays Sala Clamores, Madrid, tickets 18 euros" → en
    (plays / tickets are English; every other word is a name)
  "Els Vermuts live at Razzmatazz, Barcelona, Friday, free entry" → en
    (at / Friday / free entry are English; the band and venue are Catalan)
  "Concerto di Ana Beck al Palau de la Musica, Barcellona, 12 ottobre" → it
    (di / al / ottobre are Italian)
  "Klangfeld Nacht im Berghain, Berlin, 3. Oktober" → de

Answer with the ISO 639-1 two-letter code only — no punctuation, no explanation.

Message:
{{text}}"""

# Long inputs are pasted flyers and spreadsheets, not the promoter's own voice.
# The opening words decide, and they keep the detection call cheap.
_DETECT_MAX_CHARS = 600


def normalize_language(value: Optional[str]) -> str:
    """Any model's idea of a language → an ISO 639-1 code we can put in a prompt.

    Tolerates 'ES', 'en-US', 'Spanish', a trailing period. Anything else —
    including a model that ignored the question and returned JSON — falls back
    to the default rather than poisoning the reply prompt.
    """
    if not value:
        return DEFAULT_LANGUAGE
    cleaned = value.strip().strip(".\"'").lower()
    if cleaned in _NAME_TO_CODE:
        return _NAME_TO_CODE[cleaned]
    code = cleaned.split("-")[0].split("_")[0]
    if len(code) == 2 and code.isalpha():
        return code
    return DEFAULT_LANGUAGE


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def reply_language_instruction(code: str) -> str:
    """The line a reply prompt ends with, naming the decided language.

    Stated as a decision already taken, and placed last so it is the final
    thing the model reads before it writes — the content it just read is what
    used to win.
    """
    code = normalize_language(code)
    return (
        f"Write your reply in {language_name(code)} ({code}). This is decided: "
        "the language of the event names, venues and cities is irrelevant to it."
    )


def detect_language(client, model: str, text: str) -> str:
    """One cheap call: the language of the user's own words.

    Never raises — a failed detection answers in the default rather than
    failing the turn, which is the right trade for a cosmetic property.
    """
    snippet = (text or "").strip()[:_DETECT_MAX_CHARS]
    if not snippet:
        return DEFAULT_LANGUAGE
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _DETECT_PROMPT.format(text=snippet)}],
            temperature=0.0,
            max_tokens=5,
        )
        return normalize_language(response.choices[0].message.content)
    except Exception as e:
        logger.warning(
            "Language detection failed, answering in %s: %s", DEFAULT_LANGUAGE, e
        )
        return DEFAULT_LANGUAGE
