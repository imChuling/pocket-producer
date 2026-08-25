"""LLM intent layer: parse vague creative intent into ranker-native fields.

Two halves, deliberately separated:

- parse_intent(): one Gemini call that turns free text ("darker, more
  cinematic, but not too heavy") into ParsedIntent. Called only from the
  dedicated /api/ranking/intent endpoint, never from the rank path, so
  ranking latency is untouched.
- apply_parsed_intent(): a pure function that enriches a RankRequest with a
  ParsedIntent the client echoed back. Live session values always win; the
  LLM only fills blanks and widens the intent token set. Every ranker that
  reads text_intent (rules, text-cosine, audio-cosine) benefits without any
  weight change.
"""

import json
import logging
import os
import threading

from ranking.features import ROLE_TAGS, _intent_tokens, _parse_key, normalize_key
from ranking.schemas import ParsedIntent, RankRequest

logger = logging.getLogger(__name__)

MAX_TAGS = 8
MIN_BPM, MAX_BPM = 40.0, 220.0
_CACHE_MAX = 256

_genai_client = None
_cache: dict[str, ParsedIntent] = {}
_cache_lock = threading.Lock()


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        from google import genai

        _genai_client = genai.Client(vertexai=True)
    return _genai_client


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {"type": "array", "items": {"type": "string"}},
        "roles": {"type": "array", "items": {"type": "string"}},
        "bpm": {"type": "number"},
        "key": {"type": "string"},
    },
    "required": ["tags", "roles"],
}

_PROMPT = """\
You translate a music creator's vague intent into search terms for a loop
recommendation system. The intent may be in any language.

Intent: {text}

Output JSON:
- "tags": 3-8 lowercase English music tags a loop library would use —
  moods, genres, textures, instruments (e.g. "dark", "cinematic",
  "strings", "lofi"). Capture what the creator wants, including softened
  negations ("not too heavy" -> "mellow", not "heavy").
- "roles": track roles the creator seems to want, ONLY from:
  drums, bass, harmony, melody, vocal, fx, chords, percussion. Empty if
  none implied.
- "bpm": a single target tempo, ONLY if the intent clearly implies one
  ("slow ballad" -> 70). Omit when unsure.
- "key": tonic + mode like "a minor", ONLY if explicitly stated. Omit
  when unsure.

Never invent specifics the intent does not support. Vague intent means
tags only.
"""


def _normalize(raw: dict) -> ParsedIntent | None:
    tags = [
        " ".join(str(t).lower().split())
        for t in raw.get("tags", [])
        if str(t).strip()
    ]
    seen: set[str] = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))][:MAX_TAGS]

    roles = sorted(
        {str(r).lower().strip() for r in raw.get("roles", [])} & ROLE_TAGS
    )

    bpm = raw.get("bpm")
    if not isinstance(bpm, (int, float)) or not MIN_BPM <= float(bpm) <= MAX_BPM:
        bpm = None

    key = normalize_key(raw.get("key")) if isinstance(raw.get("key"), str) else None
    if key is not None and _parse_key(key) is None:
        key = None

    if not tags and not roles and bpm is None and key is None:
        return None
    return ParsedIntent(tags=tags, roles=roles, bpm=bpm, key=key)


def parse_intent(text: str) -> ParsedIntent | None:
    """One structured Gemini call; None on any failure (caller degrades)."""
    text = " ".join(text.strip().split())
    if not text:
        return None
    cache_key = text.lower()
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key]

    from google.genai import types as genai_types

    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model=os.environ.get("INTENT_MODEL", "gemini-3-flash-preview"),
            contents=_PROMPT.format(text=text),
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
            ),
        )
        raw = json.loads(response.text)
        parsed = _normalize(raw)
    except Exception:
        logger.warning("intent parse failed", exc_info=True)
        return None

    if parsed is not None:
        with _cache_lock:
            if len(_cache) >= _CACHE_MAX:
                _cache.pop(next(iter(_cache)))
            _cache[cache_key] = parsed
    return parsed


def apply_parsed_intent(request: RankRequest) -> RankRequest:
    """Enrich a RankRequest with its session's parsed_intent. Pure, no I/O.

    - text_intent gains the parsed tags/roles as extra tokens, so
      intent_match, novelty, and both cosine rankers see the expanded
      vocabulary instead of only the literal words typed.
    - bpm/key are filled ONLY when the live session did not provide them:
      the DAW's truth always outranks the LLM's guess.
    """
    session = request.session
    parsed = session.parsed_intent
    if parsed is None:
        return request

    known = _intent_tokens(session.text_intent)
    extra = [t for t in parsed.tags + parsed.roles if t and t not in known]

    updates: dict = {}
    if extra:
        updates["text_intent"] = " ".join(
            part for part in [session.text_intent.strip(), *extra] if part
        )
    if session.bpm is None and parsed.bpm is not None:
        updates["bpm"] = parsed.bpm
    if session.key is None and parsed.key is not None:
        updates["key"] = parsed.key
    if not updates:
        return request
    return request.model_copy(update={"session": session.model_copy(update=updates)})
