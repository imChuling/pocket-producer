"""Tests for fusion-score-based grouping in the Memory Agent.

Covers:
- Signal parity with FusionRanker on synthetic vectors
- No-CLAP ceiling
- Relative classification boundaries
- Weights loaded from artifact file (not hardcoded)
"""

import numpy as np
import pytest

# Needs PYTHONPATH=backend
from agents.memory import (
    _compute_pairwise_signals,
    _fusion_weights,
    classify_fusion_relationship,
)
from ranking.fusion_ranker import SIGNAL_NAMES, FusionRanker, load_weights
from ranking.schemas import (
    FragmentCandidate,
    RankRequest,
    SessionFingerprint,
)


@pytest.fixture()
def weights():
    return _fusion_weights()


def _make_fragment(
    *,
    bpm=None,
    key=None,
    tags=None,
    vector=None,
):
    frag = {}
    if bpm is not None:
        frag["bpm"] = bpm
    if key is not None:
        frag["key"] = key
    if tags is not None:
        frag["tags"] = tags
    if vector is not None:
        frag["representations"] = {
            "audio_semantic": {"vector": vector},
        }
    return frag


class TestWeightsLoading:
    def test_weights_match_artifact(self):
        artifact = load_weights("artifacts/fusion-deploy/weights.json")
        agent_w = _fusion_weights()
        assert agent_w == artifact["weights"]

    def test_five_weights(self):
        assert len(_fusion_weights()) == len(SIGNAL_NAMES)


class TestSignalParity:
    """Agent's per-signal phi must match FusionRanker.rank on the same pair."""

    def test_signals_match_ranker(self, weights):
        dim = 512
        rng = np.random.default_rng(42)
        vec_a = rng.standard_normal(dim).tolist()
        vec_b = rng.standard_normal(dim).tolist()

        src = _make_fragment(bpm=120, key="C major", tags=["rock", "guitar"], vector=vec_a)
        nbr = _make_fragment(bpm=118, key="C major", tags=["rock", "bass"], vector=vec_b)

        agent_signals = _compute_pairwise_signals(src, nbr)

        ranker = FusionRanker(load_weights("artifacts/fusion-deploy/weights.json"))
        request = RankRequest(
            session=SessionFingerprint(
                project_id="test",
                bpm=120,
                key="C major",
                playhead_seconds=0,
                track_count=1,
                context_tags=["rock", "guitar"],
                region_audio_embeddings=[vec_a],
            ),
            candidates=[
                FragmentCandidate(
                    fragment_id="nbr1",
                    duration_seconds=10.0,
                    bpm=118,
                    key="C major",
                    tags=["rock", "bass"],
                    created_at_iso="2026-01-01T00:00:00Z",
                    audio_url="http://test/audio.wav",
                    audio_embedding=vec_b,
                ),
            ],
            model_id="fusion-5sig-v1",
        )
        response = ranker.rank(request)
        ranker_signals = response.candidates[0].signals
        assert ranker_signals is not None

        # Agent phi: [audio_cos, audio_cos, tempo, key, tag_jac]
        # Ranker phi: [audio_cos_mean, audio_cos_max, tempo, key, tag_jaccard]
        # With one region embedding, mean == max == pairwise cosine.
        agent_phi = [
            agent_signals["audio_cosine"],
            agent_signals["audio_cosine"],
            agent_signals["tempo_match"],
            agent_signals["key_match_exact"],
            agent_signals["tag_overlap"],
        ]
        for i, (a_val, r_val) in enumerate(zip(agent_phi, ranker_signals)):
            assert abs(a_val - r_val) < 0.001, (
                f"signal {SIGNAL_NAMES[i]}: agent={a_val}, ranker={r_val}"
            )

    def test_identical_fragments(self, weights):
        vec = [1.0] * 512
        src = _make_fragment(bpm=120, key="A minor", tags=["ambient"], vector=vec)
        nbr = _make_fragment(bpm=120, key="A minor", tags=["ambient"], vector=vec)

        signals = _compute_pairwise_signals(src, nbr)
        expected_max = sum(weights)
        assert abs(signals["fusion_score"] - round(expected_max, 3)) < 0.001


class TestNoCLAPCeiling:
    def test_ceiling_without_clap(self, weights):
        src = _make_fragment(bpm=120, key="C major", tags=["rock", "guitar"])
        nbr = _make_fragment(bpm=120, key="C major", tags=["rock", "guitar"])

        signals = _compute_pairwise_signals(src, nbr)
        assert signals["audio_cosine"] == 0.0

        non_audio_weights = weights[2:]  # tempo, key, tag_jaccard
        ceiling = sum(non_audio_weights)
        assert signals["fusion_score"] == pytest.approx(ceiling, abs=0.01)


class TestRelativeClassification:
    def test_top_scorer_is_same_song(self):
        scores = [3.0, 4.0, 5.0, 6.0, 15.0]
        label = classify_fusion_relationship(
            15.0, scores, audio_cosine=0.8, tempo=0.9, key=1.0, tag_jac=0.5,
        )
        assert label == "same_song_candidate"

    def test_same_song_requires_non_audio_signal(self):
        scores = [3.0, 4.0, 5.0, 6.0, 15.0]
        label = classify_fusion_relationship(
            15.0, scores, audio_cosine=0.9, tempo=0.0, key=0.0, tag_jac=0.0,
        )
        assert label != "same_song_candidate"

    def test_median_scorer_not_same_song(self):
        scores = [3.0, 4.0, 5.0, 6.0, 15.0]
        label = classify_fusion_relationship(
            5.0, scores, audio_cosine=0.5, tempo=0.5, key=1.0, tag_jac=0.3,
        )
        assert label in ("similar_emotion", "unrelated")

    def test_bottom_scorer_is_unrelated(self):
        scores = [3.0, 4.0, 5.0, 6.0, 15.0]
        label = classify_fusion_relationship(
            3.0, scores, audio_cosine=0.2, tempo=0.0, key=0.0, tag_jac=0.0,
        )
        assert label == "unrelated"

    def test_all_identical_scores(self):
        scores = [5.0, 5.0, 5.0]
        label = classify_fusion_relationship(
            5.0, scores, audio_cosine=0.3, tempo=0.5, key=0.0, tag_jac=0.0,
        )
        assert label in ("similar_emotion", "unrelated")

    def test_empty_neighbors(self):
        label = classify_fusion_relationship(
            5.0, [], audio_cosine=0.5, tempo=0.5, key=1.0, tag_jac=0.3,
        )
        assert label == "unrelated"
