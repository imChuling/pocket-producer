"""Unit tests for Rescue Score calculator — no API calls needed.

Run: .venv/bin/python -m pytest tests/test_rescue_score.py -v
"""

import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from tools.rescue_score import compute_rescue_score

NOW = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)


def _frag(raw_input="test", emotion=None, structure_hint="", days_ago=0, **kw):
    """Helper to build a fragment dict."""
    from datetime import timedelta

    created = NOW - timedelta(days=days_ago)
    tags = {
        "emotion": emotion or [],
        "structure_hint": structure_hint,
    }
    return {"raw_input": raw_input, "tags": tags, "created_at": created, **kw}


def test_single_fragment_returns_new():
    result = compute_rescue_score([_frag()], "p1", now=NOW)
    assert result["tier"] == "new"
    assert result["rescue_score"] is None


def test_high_score_project():
    frags = [
        _frag(
            "Verse about walking in the rain on empty streets at night",
            ["melancholy", "nostalgia"],
            "verse_candidate",
            days_ago=1,
        ),
        _frag(
            "Chorus melody: let the rain wash it all away, wash away",
            ["melancholy", "hope"],
            "chorus_candidate",
            days_ago=1,
        ),
        _frag(
            "Bridge section: but maybe tomorrow the sun comes out again",
            ["melancholy", "hope"],
            "bridge_candidate",
            days_ago=2,
        ),
        _frag(
            "Hook riff: da da da da daaaa, catchy descending pattern",
            ["melancholy"],
            "hook_candidate",
            days_ago=2,
        ),
        _frag(
            "Second verse about finding shelter under a bookshop awning",
            ["melancholy", "nostalgia"],
            "verse_candidate",
            days_ago=3,
        ),
    ]
    result = compute_rescue_score(frags, "rain_song", now=NOW)
    assert result["tier"] == "high"
    assert result["rescue_score"] >= 70
    assert result["components"]["structure_completeness"] == 30
    assert result["components"]["freshness"] == 20
    print(f"High score: {result['rescue_score']}, components: {result['components']}")
    print(f"Explanation: {result['explanation']}")


def test_medium_score_project():
    frags = [
        _frag(
            "Feeling anxious about everything changing",
            ["anxiety", "melancholy"],
            "verse_candidate",
            days_ago=20,
        ),
        _frag("Short lyric idea: walls closing in", ["anxiety"], "lyric_fragment", days_ago=22),
        _frag(
            "Another verse attempt about uncertainty",
            ["anxiety", "vulnerability"],
            "verse_candidate",
            days_ago=25,
        ),
    ]
    result = compute_rescue_score(frags, "anxiety_song", now=NOW)
    assert result["tier"] == "medium"
    assert 40 <= result["rescue_score"] < 70
    assert result["components"]["structure_completeness"] == 10
    print(f"Medium score: {result['rescue_score']}, components: {result['components']}")
    print(f"Explanation: {result['explanation']}")


def test_low_score_project():
    frags = [
        _frag("sad", ["sadness"], "lyric_fragment", days_ago=120),
        _frag("hmm", ["melancholy"], "melodic_motif", days_ago=130),
    ]
    result = compute_rescue_score(frags, "old_idea", now=NOW)
    assert result["tier"] == "low"
    assert result["rescue_score"] < 40
    assert result["components"]["freshness"] == 0
    print(f"Low score: {result['rescue_score']}, components: {result['components']}")
    print(f"Explanation: {result['explanation']}")


def test_no_emotion_tags():
    frags = [
        _frag("instrumental riff A", [], "verse_candidate", days_ago=5),
        _frag("instrumental riff B", [], "chorus_candidate", days_ago=5),
    ]
    result = compute_rescue_score(frags, "instrumental", now=NOW)
    assert result["components"]["emotional_coherence"] == 10
    print(f"No-emotion score: {result['rescue_score']}")


def test_near_complete_demo():
    frags = [
        _frag(
            "Full demo recording of the song",
            ["joy", "nostalgia"],
            "near_complete_demo",
            days_ago=1,
        ),
        _frag("Alternate bridge idea", ["joy"], "bridge_candidate", days_ago=2),
    ]
    result = compute_rescue_score(frags, "demo_project", now=NOW)
    assert result["components"]["structure_completeness"] == 30
    print(f"Near-complete demo score: {result['rescue_score']}")


def test_sample_calculation_a():
    """Verify against Example A from SKILL.md.

    Target: 14 emotion mentions, 8 melancholy (ratio 0.57 → coherence 15).
    """
    frags = [
        _frag("x" * 120, ["melancholy", "melancholy"], "verse_candidate", days_ago=5),
        _frag("x" * 120, ["melancholy", "acceptance", "nostalgia"], "chorus_candidate", days_ago=5),
        _frag("x" * 120, ["melancholy", "melancholy", "acceptance"], "lyric_fragment", days_ago=5),
        _frag(
            "x" * 120,
            ["melancholy", "melancholy", "acceptance", "nostalgia"],
            "verse_candidate",
            days_ago=5,
        ),
        _frag("x" * 120, ["melancholy", "acceptance"], "lyric_fragment", days_ago=5),
    ]
    result = compute_rescue_score(frags, "example_a", now=NOW)
    c = result["components"]
    assert c["richness"] == 26
    assert c["structure_completeness"] == 20
    assert c["freshness"] == 15
    assert c["emotional_coherence"] == 15
    assert result["rescue_score"] == 76
    assert result["tier"] == "high"
    print(f"Example A verified: {result['rescue_score']}")


if __name__ == "__main__":
    tests = [
        test_single_fragment_returns_new,
        test_high_score_project,
        test_medium_score_project,
        test_low_score_project,
        test_no_emotion_tags,
        test_near_complete_demo,
        test_sample_calculation_a,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__} — {e}")
    print(f"\n{passed}/{len(tests)} passed")
