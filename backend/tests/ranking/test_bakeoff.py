"""Bake-off probe unit tests on constructed geometry."""

import numpy as np

from ranking.bakeoff import same_source_recall_at_k, zero_shot_label_accuracy


def unit(*values: float) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    return list(array / np.linalg.norm(array))


class TestSameSourceRecall:
    def test_clustered_sources_reach_full_recall(self):
        items = [
            {"source_id": "a", "embedding": unit(1, 0.01, 0)},
            {"source_id": "a", "embedding": unit(1, -0.01, 0)},
            {"source_id": "b", "embedding": unit(0, 1, 0.01)},
            {"source_id": "b", "embedding": unit(0, 1, -0.01)},
        ]
        result = same_source_recall_at_k(items, k=1)
        assert result["recall_at_k"] == 1.0
        assert result["queries"] == 4

    def test_scrambled_sources_score_low(self):
        items = [
            {"source_id": "a", "embedding": unit(1, 0, 0)},
            {"source_id": "b", "embedding": unit(1, 0.01, 0)},
            {"source_id": "a", "embedding": unit(0, 1, 0)},
            {"source_id": "b", "embedding": unit(0.01, 1, 0)},
        ]
        result = same_source_recall_at_k(items, k=1)
        assert result["recall_at_k"] == 0.0

    def test_singleton_sources_are_excluded(self):
        items = [
            {"source_id": "solo", "embedding": unit(1, 0, 0)},
            {"source_id": "a", "embedding": unit(0, 1, 0)},
            {"source_id": "a", "embedding": unit(0, 1, 0.01)},
        ]
        result = same_source_recall_at_k(items, k=1)
        assert result["queries"] == 2

    def test_empty_returns_none(self):
        assert same_source_recall_at_k([], k=5)["recall_at_k"] is None


class TestZeroShotAccuracy:
    def test_aligned_prompts_score_perfectly(self):
        embeddings = np.asarray([unit(1, 0), unit(0, 1)])
        prompts = np.asarray([unit(1, 0), unit(0, 1)])
        result = zero_shot_label_accuracy(
            embeddings, [["rock"], ["jazz"]], ["rock", "jazz"], prompts
        )
        assert result["accuracy"] == 1.0
        assert result["evaluated"] == 2

    def test_hit_counts_when_prediction_in_multilabel_set(self):
        embeddings = np.asarray([unit(1, 0)])
        prompts = np.asarray([unit(1, 0), unit(0, 1)])
        result = zero_shot_label_accuracy(
            embeddings, [["jazz", "rock"]], ["rock", "jazz"], prompts
        )
        assert result["accuracy"] == 1.0

    def test_unlabeled_items_are_excluded_not_missed(self):
        embeddings = np.asarray([unit(1, 0), unit(0, 1)])
        prompts = np.asarray([unit(1, 0), unit(0, 1)])
        result = zero_shot_label_accuracy(
            embeddings, [["rock"], []], ["rock", "jazz"], prompts
        )
        assert result["evaluated"] == 1
        assert result["accuracy"] == 1.0
