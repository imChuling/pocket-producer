"""Contract tests for the deterministic rules baseline (rules-v1)."""

import pytest
from pydantic import ValidationError

from ranking.baselines import RulesRanker
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint


def session(**overrides) -> SessionFingerprint:
    base = dict(
        project_id="p1",
        bpm=120.0,
        key="A minor",
        playhead_seconds=18.0,
        track_count=2,
        active_track_types=["drums"],
        recent_entity_ids=[],
        text_intent="dark bass",
    )
    base.update(overrides)
    return SessionFingerprint(**base)


def candidate(fragment_id: str, **overrides) -> FragmentCandidate:
    base = dict(
        fragment_id=fragment_id,
        duration_seconds=8.0,
        bpm=None,
        key=None,
        tags=[],
        created_at_iso="2026-07-01T00:00:00Z",
        audio_url=f"/api/fragments/{fragment_id}/audio",
    )
    base.update(overrides)
    return FragmentCandidate(**base)


def test_rules_ranker_prefers_actionable_match():
    matching = candidate("match", bpm=121, key="A minor", tags=["dark", "bass"])
    unrelated = candidate("other", bpm=88, key="C major", tags=["bright", "vocal"])

    result = RulesRanker().rank(
        RankRequest(session=session(), candidates=[unrelated, matching])
    )

    assert result.candidates[0].fragment_id == "match"
    assert {e.code for e in result.candidates[0].evidence} >= {
        "tempo_match",
        "key_match",
        "intent_match",
    }


def test_empty_candidates_returns_empty_response():
    result = RulesRanker().rank(RankRequest(session=session(), candidates=[]))
    assert result.candidates == []
    assert result.model_id == "rules-v1"
    assert result.fallback_used is False


def test_missing_bpm_and_key_scores_zero_for_those_features():
    bare = candidate("bare")
    result = RulesRanker().rank(
        RankRequest(session=session(bpm=None, key=None), candidates=[bare])
    )
    codes = {e.code for e in result.candidates[0].evidence}
    assert "tempo_match" not in codes
    assert "key_match" not in codes


def test_equal_scores_sort_stable_by_fragment_id():
    twins = [candidate("b"), candidate("a"), candidate("c")]
    result = RulesRanker().rank(
        RankRequest(session=session(), candidates=twins, limit=10)
    )
    assert [c.fragment_id for c in result.candidates] == ["a", "b", "c"]


def test_limit_truncates_results():
    many = [candidate(f"f{i}") for i in range(6)]
    result = RulesRanker().rank(
        RankRequest(session=session(), candidates=many, limit=3)
    )
    assert len(result.candidates) == 3


def test_invalid_duration_rejected_by_schema():
    with pytest.raises(ValidationError):
        candidate("bad", duration_seconds=0)


def test_evidence_contributions_are_bounded():
    rich = candidate(
        "rich", bpm=120, key="A minor", tags=["dark", "bass"],
        created_at_iso="2026-07-29T00:00:00Z",
    )
    result = RulesRanker().rank(RankRequest(session=session(), candidates=[rich]))
    top = result.candidates[0]
    assert 0.0 <= top.score <= 1.0
    for e in top.evidence:
        assert 0.0 <= e.contribution <= 1.0
        assert e.label
