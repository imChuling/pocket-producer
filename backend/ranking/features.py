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
    # Replace abbreviations only when they are not already the full word.
    # " min" inside " minor" must not expand to " minoror".
    if normalized.endswith(" maj"):
        normalized = normalized[:-4] + " major"
    elif normalized.endswith(" min"):
        normalized = normalized[:-4] + " minor"
    return normalized or None


def _parse_key(normalized: str) -> tuple[int, str] | None:
    """Return (pitch_class 0-11, mode) from a normalized key string."""
    parts = normalized.split()
    if len(parts) != 2:
        return None
    name_map = {
        "c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3,
        "e": 4, "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8,
        "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11,
    }
    pc = name_map.get(parts[0])
    if pc is None:
        return None
    mode = parts[1] if parts[1] in ("major", "minor") else None
    if mode is None:
        return None
    return pc, mode


def key_match(
    session_key: str | None,
    fragment_key: str | None,
    mode: str = "exact",
) -> float:
    """Score key compatibility.

    mode (protocol-key-audit-v1):
      exact:    1.0 iff same tonic+mode (current default)
      relative: + 1.0 for relative major/minor (e.g. C major = A minor)
      fifth:    + relative, and 0.5 for tonic a perfect fifth apart
                with the same mode (Camelot-adjacent)
    """
    left, right = normalize_key(session_key), normalize_key(fragment_key)
    if left is None or right is None:
        return 0.0
    if left == right:
        return 1.0
    if mode == "exact":
        return 0.0

    lp, rp = _parse_key(left), _parse_key(right)
    if lp is None or rp is None:
        return 0.0
    l_pc, l_mode = lp
    r_pc, r_mode = rp

    # relative major/minor: C major (0, major) <-> A minor (9, minor)
    # offset = 3 semitones down from major to its relative minor
    if l_mode != r_mode:
        if l_mode == "major" and (l_pc - 3) % 12 == r_pc:
            return 1.0
        if r_mode == "major" and (r_pc - 3) % 12 == l_pc:
            return 1.0

    if mode == "relative":
        return 0.0

    # fifth neighbors (same mode, tonic a P5 apart)
    interval = abs(l_pc - r_pc) % 12
    if l_mode == r_mode and interval in (5, 7):
        return 0.5

    return 0.0


def track_gap(active_track_types: list[str], tags: list[str]) -> float:
    candidate_roles = {t.lower() for t in tags} & ROLE_TAGS
    if not candidate_roles:
        return 0.0
    active = {t.lower() for t in active_track_types}
    return 1.0 if candidate_roles - active else 0.0


def _intent_tokens(text_intent: str) -> set[str]:
    # Punctuation must not glue itself to tokens: "dark bass, slower
    # bridge" has to yield {"dark", "bass", "slower", "bridge"} so the
    # token "bass" can meet the tag "bass".
    cleaned = "".join(c if c.isalnum() or c in "-_" else " " for c in text_intent.lower())
    return {t for t in cleaned.split() if t}


def intent_match(text_intent: str, tags: list[str]) -> float:
    intent_tokens = _intent_tokens(text_intent)
    if not intent_tokens:
        return 0.0
    tag_tokens = {t.lower() for t in tags}
    return len(intent_tokens & tag_tokens) / len(intent_tokens)


def novelty(tags: list[str], active_track_types: list[str], text_intent: str) -> float:
    tag_tokens = {t.lower() for t in tags}
    if not tag_tokens:
        return 0.0
    known = {t.lower() for t in active_track_types} | _intent_tokens(text_intent)
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
