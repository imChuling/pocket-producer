"""Rescue Score calculator — pure Python, no LLM calls.

Implements the formula from skills/rescue-scoring/SKILL.md v1.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any


def compute_rescue_score(
    fragments: list[dict[str, Any]],
    project_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute rescue score for a project given its fragments.

    Returns the schema defined in rescue-scoring/SKILL.md.
    """
    if now is None:
        now = datetime.now(UTC)

    if len(fragments) < 2:
        return {
            "project_id": project_id,
            "rescue_score": None,
            "components": None,
            "tier": "new",
            "explanation": ("Single-fragment project — needs at least one more idea to evaluate."),
        }

    richness = _richness(fragments)
    structure = _structure_completeness(fragments)
    coherence = _emotional_coherence(fragments)
    freshness = _freshness(fragments, now)

    score = richness + structure + coherence + freshness
    tier = _tier(score)
    explanation = _explanation(score, tier, richness, structure, coherence, freshness, fragments)

    return {
        "project_id": project_id,
        "rescue_score": score,
        "components": {
            "richness": richness,
            "structure_completeness": structure,
            "emotional_coherence": coherence,
            "freshness": freshness,
        },
        "tier": tier,
        "explanation": explanation,
    }


def _richness(fragments: list[dict]) -> int:
    fragment_count = len(fragments)
    total_text_length = sum(
        len(f.get("raw_input", "") or f.get("raw_text", "") or "") for f in fragments
    )
    return min(30, int(fragment_count * 4 + total_text_length / 100))


def _structure_completeness(fragments: list[dict]) -> int:
    section_types: set[str] = set()
    for f in fragments:
        tags = f.get("tags") or {}
        hint = tags.get("structure_hint", "")
        if hint:
            section_types.add(hint)

    if "near_complete_demo" in section_types:
        return 30

    score = 0
    if "verse_candidate" in section_types:
        score += 10
    if "chorus_candidate" in section_types:
        score += 10
    if "hook_candidate" in section_types:
        score += 5
    if "bridge_candidate" in section_types:
        score += 5
    return min(30, score)


def _emotional_coherence(fragments: list[dict]) -> int:
    all_emotions: list[str] = []
    for f in fragments:
        tags = f.get("tags") or {}
        emotions = tags.get("emotion", [])
        if isinstance(emotions, list):
            all_emotions.extend(emotions)
        elif isinstance(emotions, str):
            all_emotions.append(emotions)

    if not all_emotions:
        return 10

    counts = Counter(all_emotions)
    dominant_count = counts.most_common(1)[0][1]
    dominance_ratio = dominant_count / len(all_emotions)

    if dominance_ratio >= 0.6:
        return 20
    if dominance_ratio >= 0.4:
        return 15
    if dominance_ratio >= 0.25:
        return 10
    return 5


def _freshness(fragments: list[dict], now: datetime) -> int:
    dates = []
    for f in fragments:
        for field in ("updated_at", "created_at"):
            val = f.get(field)
            if val is None:
                continue
            if isinstance(val, datetime):
                dt = val if val.tzinfo else val.replace(tzinfo=UTC)
            elif isinstance(val, str):
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            else:
                continue
            dates.append(dt)
            break

    if not dates:
        return 0

    latest = max(dates)
    days = (now - latest).days

    if days <= 3:
        return 20
    if days <= 14:
        return 15
    if days <= 30:
        return 10
    if days <= 90:
        return 5
    return 0


def _tier(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _explanation(
    score: int,
    tier: str,
    richness: int,
    structure: int,
    coherence: int,
    freshness: int,
    fragments: list[dict],
) -> str:
    n = len(fragments)
    sections = set()
    for f in fragments:
        hint = (f.get("tags") or {}).get("structure_hint", "")
        if hint:
            sections.add(hint)
    section_names = [s.replace("_candidate", "").replace("_", " ") for s in sections if s]

    if tier == "high":
        msg = f"Strong project: {n} fragments"
        if section_names:
            msg += f" with {', '.join(section_names)} material"
        if freshness >= 15:
            msg += ", recently active"
        msg += " — good candidate for a finishing session."
    elif tier == "medium":
        msg = f"Moderate progress: {n} fragments"
        if "chorus_candidate" not in sections:
            msg += ", but no chorus candidate yet"
        if freshness <= 10:
            msg += " — activity has slowed"
        msg += ". A focused 30-minute session could move this forward."
    else:
        msg = f"Sparse so far: {n} fragments"
        if structure == 0:
            msg += " without clear structural sections"
        if freshness == 0:
            msg += ", dormant for months"
        msg += ". Expand with new material or consider archiving."

    return msg
