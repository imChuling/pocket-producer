"""Deterministic ranking features, all normalized to [0, 1].

Every feature must be computable without network access and must return 0.0
rather than raising when its inputs are missing — missing data is never
evidence for a recommendation.
"""

from datetime import datetime

ROLE_TAGS = frozenset(
    {"drums", "bass", "harmony", "melody", "vocal", "fx", "chords", "percussion"}
)

# Tempo differences beyond 25% of the session tempo score zero.
_TEMPO_TOLERANCE = 0.25

# Recency decays with a 30-day half-life relative to the newest candidate.
_RECENCY_HALF_LIFE_DAYS = 30.0


def tempo_match(session_bpm: float | None, fragment_bpm: float | None) -> float:
    if session_bpm is None or fragment_bpm is None:
        return 0.0
    ratio = abs(session_bpm - fragment_bpm) / max(session_bpm, 1.0)
    return max(0.0, 1.0 - ratio / _TEMPO_TOLERANCE)


def normalize_key(key: str | None) -> str | None:
    if key is None:
        return None
    normalized = " ".join(key.strip().lower().split())
    normalized = normalized.replace(" maj", " major").replace(" min", " minor")
    return normalized or None


def key_match(session_key: str | None, fragment_key: str | None) -> float:
    left, right = normalize_key(session_key), normalize_key(fragment_key)
    if left is None or right is None:
        return 0.0
    return 1.0 if left == right else 0.0


def track_gap(active_track_types: list[str], tags: list[str]) -> float:
    candidate_roles = {t.lower() for t in tags} & ROLE_TAGS
    if not candidate_roles:
        return 0.0
    active = {t.lower() for t in active_track_types}
    return 1.0 if candidate_roles - active else 0.0


def intent_match(text_intent: str, tags: list[str]) -> float:
    intent_tokens = {t for t in text_intent.lower().split() if t}
    if not intent_tokens:
        return 0.0
    tag_tokens = {t.lower() for t in tags}
    return len(intent_tokens & tag_tokens) / len(intent_tokens)


def novelty(tags: list[str], active_track_types: list[str], text_intent: str) -> float:
    tag_tokens = {t.lower() for t in tags}
    if not tag_tokens:
        return 0.0
    known = {t.lower() for t in active_track_types} | set(text_intent.lower().split())
    return len(tag_tokens - known) / len(tag_tokens)


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def recency(created_at_iso: str, newest_iso: str) -> float:
    created = _parse_iso(created_at_iso)
    newest = _parse_iso(newest_iso)
    if created is None or newest is None:
        return 0.0
    age_days = max(0.0, (newest - created).total_seconds() / 86400.0)
    return 1.0 / (1.0 + age_days / _RECENCY_HALF_LIFE_DAYS)
