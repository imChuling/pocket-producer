"""recency-v1, text-only-v1 and mean-session-v1 baselines."""

import numpy as np
import pytest

from ranking.audio_cosine import InsufficientContextError
from ranking.mean_session import MeanSessionRanker
from ranking.recency import RecencyRanker
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint
from ranking.text_cosine import TextCosineRanker


def unit(*values: float) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    return list(array / np.linalg.norm(array))


def candidate(
    fragment_id: str,
    created: str = "2026-07-01T00:00:00Z",
    audio: list[float] | None = None,
    text: list[float] | None = None,
) -> FragmentCandidate:
    return FragmentCandidate(
        fragment_id=fragment_id,
        duration_seconds=4.0,
        created_at_iso=created,
        audio_url=f"/api/fragments/{fragment_id}/audio",
        audio_embedding=audio,
        text_embedding=text,
    )


def session(**overrides) -> SessionFingerprint:
    base = dict(
        project_id="p1",
        playhead_seconds=0,
        track_count=1,
        text_intent="dark bass",
    )
    base.update(overrides)
    return SessionFingerprint(**base)


def request(candidates, **session_overrides) -> RankRequest:
    return RankRequest(session=session(**session_overrides), candidates=candidates)


class TestRecencyRanker:
    def test_newest_fragment_ranks_first(self):
        old = candidate("old", created="2026-01-01T00:00:00Z")
        new = candidate("new", created="2026-07-30T00:00:00Z")
        response = RecencyRanker().rank(request([old, new]))
        assert response.candidates[0].fragment_id == "new"
        assert response.model_id == "recency-v1"

    def test_evidence_uses_recency_code(self):
        response = RecencyRanker().rank(
            request([candidate("a", created="2026-07-30T00:00:00Z")])
        )
        assert response.candidates[0].evidence[0].code == "recency"

    def test_ties_stable_by_id_and_limit_respected(self):
        same = "2026-07-30T00:00:00Z"
        response = RecencyRanker().rank(
            RankRequest(
                session=session(),
                candidates=[
                    candidate("b", created=same),
                    candidate("a", created=same),
                    candidate("c", created=same),
                ],
                limit=2,
            )
        )
        assert [c.fragment_id for c in response.candidates] == ["a", "b"]


class TestTextCosineRanker:
    def ranker(self) -> TextCosineRanker:
        return TextCosineRanker(text_encoder=lambda text: unit(1, 0, 0))

    def test_prefers_candidate_closest_to_intent_in_text_space(self):
        close = candidate("close", text=unit(0.9, 0.1, 0))
        far = candidate("far", text=unit(0, 0, 1))
        response = self.ranker().rank(request([far, close]))
        assert response.candidates[0].fragment_id == "close"
        assert response.model_id == "text-only-v1"

    def test_missing_text_embedding_scores_zero_without_evidence(self):
        bare = candidate("bare")
        embedded = candidate("embedded", text=unit(1, 0, 0))
        response = self.ranker().rank(request([bare, embedded]))
        assert response.candidates[-1].fragment_id == "bare"
        assert response.candidates[-1].evidence == []

    def test_empty_intent_raises(self):
        with pytest.raises(InsufficientContextError):
            self.ranker().rank(
                request([candidate("a", text=unit(1, 0, 0))], text_intent=" ")
            )


class TestMeanSessionRanker:
    def test_ranks_by_similarity_to_mean_of_region_embeddings(self):
        fits = candidate("fits", audio=unit(1, 1, 0))
        clashes = candidate("clashes", audio=unit(0, 0, 1))
        response = MeanSessionRanker().rank(
            request(
                [clashes, fits],
                region_audio_embeddings=[unit(1, 0, 0), unit(0, 1, 0)],
            )
        )
        assert response.candidates[0].fragment_id == "fits"
        assert response.model_id == "mean-session-v1"

    def test_without_region_embeddings_raises(self):
        with pytest.raises(InsufficientContextError):
            MeanSessionRanker().rank(request([candidate("a", audio=unit(1, 0, 0))]))

    def test_single_region_context_works(self):
        near = candidate("near", audio=unit(1, 0.1, 0))
        response = MeanSessionRanker().rank(
            request([near], region_audio_embeddings=[unit(1, 0, 0)])
        )
        assert response.candidates[0].score > 0.5
