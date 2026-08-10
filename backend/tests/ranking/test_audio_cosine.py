"""audio-cosine-v1: CLAP text-intent vector vs candidate audio vectors."""

import numpy as np
import pytest

from ranking.audio_cosine import AudioCosineRanker, InsufficientContextError
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint


def unit(*values: float) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    return list(array / np.linalg.norm(array))


INTENT_VECTORS = {
    "dark bass": unit(1, 0, 0),
}


def fake_text_encoder(text: str) -> list[float]:
    return INTENT_VECTORS[text]


def candidate(fragment_id: str, embedding: list[float] | None) -> FragmentCandidate:
    return FragmentCandidate(
        fragment_id=fragment_id,
        duration_seconds=4.0,
        created_at_iso="2026-07-01T00:00:00Z",
        audio_url=f"/api/fragments/{fragment_id}/audio",
        audio_embedding=embedding,
    )


def request(candidates, intent="dark bass", limit=3) -> RankRequest:
    return RankRequest(
        session=SessionFingerprint(
            project_id="p1",
            playhead_seconds=0,
            track_count=1,
            text_intent=intent,
        ),
        candidates=candidates,
        model_id="audio-cosine-v1",
        limit=limit,
    )


def ranker() -> AudioCosineRanker:
    return AudioCosineRanker(text_encoder=fake_text_encoder)


class TestAudioCosineRanker:
    def test_prefers_candidate_closest_to_intent(self):
        close = candidate("close", unit(0.9, 0.1, 0))
        far = candidate("far", unit(0, 0, 1))
        response = ranker().rank(request([far, close]))
        assert response.candidates[0].fragment_id == "close"
        assert response.model_id == "audio-cosine-v1"

    def test_intent_evidence_is_attached(self):
        close = candidate("close", unit(1, 0, 0))
        response = ranker().rank(request([close]))
        evidence = response.candidates[0].evidence
        assert evidence and evidence[0].code == "model_signal"
        assert "dark bass" in evidence[0].label

    def test_candidates_without_embedding_rank_last_without_fake_evidence(self):
        embedded = candidate("embedded", unit(0, 1, 0))
        bare = candidate("bare", None)
        response = ranker().rank(request([bare, embedded]))
        assert response.candidates[-1].fragment_id == "bare"
        assert response.candidates[-1].evidence == []
        assert response.candidates[-1].score == 0.0

    def test_empty_intent_raises_insufficient_context(self):
        with pytest.raises(InsufficientContextError):
            ranker().rank(request([candidate("a", unit(1, 0, 0))], intent="  "))

    def test_scores_bounded_and_sorted(self):
        response = ranker().rank(
            request(
                [
                    candidate("a", unit(1, 0, 0)),
                    candidate("b", unit(0, 1, 0)),
                    candidate("c", unit(-1, 0, 0)),
                ]
            )
        )
        scores = [c.score for c in response.candidates]
        assert scores == sorted(scores, reverse=True)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_limit_respected_and_ties_stable(self):
        same = unit(1, 0, 0)
        response = ranker().rank(
            request(
                [candidate("b", same), candidate("a", same), candidate("c", same)],
                limit=2,
            )
        )
        assert [c.fragment_id for c in response.candidates] == ["a", "b"]
