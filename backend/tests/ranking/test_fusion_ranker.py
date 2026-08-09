"""fusion-5sig-v1 deployed fusion ranker."""

import numpy as np
import pytest

from ranking.audio_cosine import InsufficientContextError
from ranking.fusion_ranker import SIGNAL_NAMES, FusionRanker, load_weights
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint


def unit(*values: float) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    return list(array / np.linalg.norm(array))


WEIGHTS = {
    "weights": [1.0, 0.5, 1.0, 1.0, 1.0],
    "trained_on": "test",
    "representation_model": "test-space",
}


def candidate(fragment_id: str, **overrides) -> FragmentCandidate:
    base = dict(
        fragment_id=fragment_id,
        duration_seconds=4.0,
        created_at_iso="2026-07-01T00:00:00Z",
        audio_url=f"/api/fragments/{fragment_id}/audio",
    )
    base.update(overrides)
    return FragmentCandidate(**base)


def request(candidates, **session_overrides) -> RankRequest:
    base = dict(
        project_id="p1",
        playhead_seconds=0,
        track_count=1,
        region_audio_embeddings=[unit(1, 0, 0)],
    )
    base.update(session_overrides)
    return RankRequest(
        session=SessionFingerprint(**base), candidates=candidates
    )


class TestFusionRanker:
    def test_refuses_without_region_audio(self):
        ranker = FusionRanker(WEIGHTS)
        with pytest.raises(InsufficientContextError):
            ranker.rank(request([candidate("f1")], region_audio_embeddings=None))

    def test_closer_audio_ranks_first(self):
        ranker = FusionRanker(WEIGHTS)
        response = ranker.rank(
            request([
                candidate("far", audio_embedding=unit(0, 1, 0)),
                candidate("near", audio_embedding=unit(1, 0.1, 0)),
            ])
        )
        assert [c.fragment_id for c in response.candidates] == ["near", "far"]

    def test_tempo_match_breaks_audio_tie(self):
        ranker = FusionRanker(WEIGHTS)
        response = ranker.rank(
            request(
                [
                    candidate("offbeat", audio_embedding=unit(1, 0, 0), bpm=170.0),
                    candidate("onbeat", audio_embedding=unit(1, 0, 0), bpm=120.0),
                ],
                bpm=120.0,
            )
        )
        assert response.candidates[0].fragment_id == "onbeat"
        assert response.candidates[0].score > response.candidates[1].score

    def test_key_signal_zero_when_session_key_none(self):
        # Audiotool sessions never carry a key; the key term must not
        # differentiate candidates.
        ranker = FusionRanker(WEIGHTS)
        response = ranker.rank(
            request(
                [
                    candidate("keyed", audio_embedding=unit(1, 0, 0), key="C major"),
                    candidate("keyless", audio_embedding=unit(1, 0, 0)),
                ],
            )
        )
        assert response.candidates[0].score == response.candidates[1].score

    def test_tag_overlap_uses_context_tags(self):
        ranker = FusionRanker(WEIGHTS)
        response = ranker.rank(
            request(
                [
                    candidate("plain", audio_embedding=unit(1, 0, 0)),
                    candidate(
                        "tagged", audio_embedding=unit(1, 0, 0), tags=["techno"]
                    ),
                ],
                context_tags=["techno"],
            )
        )
        assert response.candidates[0].fragment_id == "tagged"

    def test_candidate_without_embedding_scores_zero(self):
        ranker = FusionRanker(WEIGHTS)
        response = ranker.rank(
            request([
                candidate("noaudio", bpm=120.0),
                candidate("audio", audio_embedding=unit(1, 0, 0)),
            ])
        )
        by_id = {c.fragment_id: c for c in response.candidates}
        assert by_id["noaudio"].score == 0.0
        assert by_id["noaudio"].evidence == []

    def test_evidence_contributions_present(self):
        ranker = FusionRanker(WEIGHTS)
        response = ranker.rank(
            request(
                [candidate("f1", audio_embedding=unit(1, 0, 0), bpm=120.0)],
                bpm=120.0,
            )
        )
        codes = [e.code for e in response.candidates[0].evidence]
        assert "tempo_match" in codes
        assert "key_match" in codes
        assert "model_signal" in codes

    def test_load_weights_rejects_wrong_arity(self, tmp_path):
        path = tmp_path / "weights.json"
        path.write_text('{"weights": [1.0, 2.0]}')
        with pytest.raises(ValueError):
            load_weights(path)

    def test_load_weights_roundtrip(self, tmp_path):
        import json

        path = tmp_path / "weights.json"
        path.write_text(json.dumps(WEIGHTS))
        data = load_weights(path)
        assert len(data["weights"]) == len(SIGNAL_NAMES)
        FusionRanker(data)
