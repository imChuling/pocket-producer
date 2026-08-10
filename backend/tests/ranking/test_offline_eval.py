"""Offline evaluator: honest skips, per-participant grouping, fixed models."""

import json
from dataclasses import asdict

import numpy as np
import pytest
from safetensors.torch import save_file

from ranking.context_model import LadderConfig, PocketRankContext
from ranking.deepsets_ranker import DeepSetsRanker
from ranking.linear_ranker import LinearRanker
from ranking.offline_eval import (
    LADDER_MODEL_IDS,
    SCORERS,
    evaluate_examples,
    ladder_scorers,
    load_ladder_adapters,
)


def unit(*values: float) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    return list(array / np.linalg.norm(array))


def candidate(fragment_id: str, **overrides) -> dict:
    base = dict(
        fragment_id=fragment_id,
        duration_seconds=4.0,
        bpm=None,
        key=None,
        tags=[],
        created_at_iso="2026-07-01T00:00:00Z",
        audio_url=f"/api/fragments/{fragment_id}/audio",
    )
    base.update(overrides)
    return base


def example(participant: str = "p1", **overrides) -> dict:
    base = dict(
        participant_hash=participant,
        session=dict(
            project_id="p1",
            bpm=120,
            playhead_seconds=0,
            track_count=1,
            active_track_types=["drums"],
            text_intent="dark bass",
        ),
        candidates=[
            candidate(
                "good",
                bpm=120,
                tags=["dark", "bass"],
                audio_embedding=unit(1, 0, 0),
            ),
            candidate(
                "bad",
                bpm=70,
                tags=["bright"],
                audio_embedding=unit(0, 0, 1),
            ),
        ],
        label={"type": "pairwise", "preferred_id": "good", "rejected_id": "bad"},
        intent_audio_embedding=unit(1, 0, 0),
    )
    base.update(overrides)
    return base


class TestEvaluateExamples:
    def test_rules_scores_constructed_example_correctly(self):
        report = evaluate_examples([example()], ["rules-v1"])
        assert report["models"]["rules-v1"]["pairwise_accuracy"] == 1.0
        assert report["models"]["rules-v1"]["evaluated"] == 1

    def test_audio_cosine_uses_precomputed_intent_embedding(self):
        report = evaluate_examples([example()], ["audio-cosine-v1"])
        assert report["models"]["audio-cosine-v1"]["pairwise_accuracy"] == 1.0

    def test_missing_intent_embedding_is_a_reported_skip(self):
        no_intent = example()
        no_intent.pop("intent_audio_embedding")
        report = evaluate_examples([no_intent], ["audio-cosine-v1"])
        entry = report["models"]["audio-cosine-v1"]
        assert entry["evaluated"] == 0
        assert entry["skipped"] == 1
        assert entry["pairwise_accuracy"] is None

    def test_per_participant_grouping(self):
        report = evaluate_examples(
            [example(participant="p1"), example(participant="p2")],
            ["rules-v1"],
        )
        per = report["models"]["rules-v1"]["per_participant"]
        assert set(per) == {"p1", "p2"}
        assert per["p1"]["n"] == 1

    def test_unknown_model_rejected(self):
        with pytest.raises(ValueError, match="unknown models"):
            evaluate_examples([example()], ["sota-magic-v9"])

    def test_non_pairwise_labels_rejected(self):
        bad = example()
        bad["label"] = {"type": "graded"}
        with pytest.raises(ValueError, match="pairwise"):
            evaluate_examples([bad], ["rules-v1"])

    def test_mean_session_skips_without_region_embeddings(self):
        report = evaluate_examples([example()], ["mean-session-v1"])
        assert report["models"]["mean-session-v1"]["skipped"] == 1

    def test_mean_session_scores_with_region_embeddings(self):
        with_context = example()
        with_context["session"]["region_audio_embeddings"] = [unit(1, 0.2, 0)]
        report = evaluate_examples([with_context], ["mean-session-v1"])
        assert report["models"]["mean-session-v1"]["pairwise_accuracy"] == 1.0


LADDER_CONFIG = LadderConfig(
    input_dim=3,
    d_model=8,
    structured_dim=0,
    max_tokens=4,
    nhead=2,
    dim_feedforward=16,
    num_layers=1,
    low_rank=4,
)

LADDER_CLASSES = {
    "linear-v1": LinearRanker,
    "deepsets-v1": DeepSetsRanker,
    "pocketrank-context-v1": PocketRankContext,
}


@pytest.fixture
def ladder_dir(tmp_path):
    for model_id, cls in LADDER_CLASSES.items():
        directory = tmp_path / model_id
        directory.mkdir()
        save_file(cls(LADDER_CONFIG).state_dict(), str(directory / "model.safetensors"))
        (directory / "config.json").write_text(json.dumps(asdict(LADDER_CONFIG)))
    return tmp_path


class TestLadderScorers:
    def test_all_preregistered_comparison_models_are_scorable(self, ladder_dir):
        """The full comparison set — baselines plus every learned model —
        must evaluate on one dataset without unknown-model errors."""
        adapters = load_ladder_adapters(ladder_dir)
        assert set(adapters) == set(LADDER_MODEL_IDS)
        with_context = example()
        with_context["session"]["region_audio_embeddings"] = [unit(1, 0.2, 0)]
        all_models = sorted(SCORERS) + sorted(LADDER_MODEL_IDS)
        report = evaluate_examples(
            [with_context], all_models, ladder_scorers(adapters)
        )
        for model_id in LADDER_MODEL_IDS:
            entry = report["models"][model_id]
            assert entry["evaluated"] == 1
            assert entry["pairwise_accuracy"] in (0.0, 1.0)

    def test_learned_models_skip_without_session_context(self, ladder_dir):
        adapters = load_ladder_adapters(ladder_dir)
        report = evaluate_examples(
            [example()], list(LADDER_MODEL_IDS), ladder_scorers(adapters)
        )
        for model_id in LADDER_MODEL_IDS:
            assert report["models"][model_id]["skipped"] == 1

    def test_learned_models_skip_partial_candidate_embeddings(self, ladder_dir):
        """A pairwise example with one unscorable side must be a skip, not a
        comparison against the 0.0 default."""
        partial = example()
        partial["session"]["region_audio_embeddings"] = [unit(1, 0.2, 0)]
        partial["candidates"][1].pop("audio_embedding")
        adapters = load_ladder_adapters(ladder_dir)
        report = evaluate_examples(
            [partial], ["pocketrank-context-v1"], ladder_scorers(adapters)
        )
        assert report["models"]["pocketrank-context-v1"]["skipped"] == 1

    def test_ladder_ids_without_scorers_still_rejected(self):
        with pytest.raises(ValueError, match="unknown models"):
            evaluate_examples([example()], ["pocketrank-context-v1"])
