"""Metrics must match label semantics — wrong pairings fail loudly."""

import math

import pytest

from ranking.metrics import (
    MetricEligibilityError,
    log_loss,
    mrr,
    ndcg_at_k,
    pairwise_accuracy,
)


class TestPairwiseAccuracy:
    def test_counts_correct_orderings(self):
        outcomes = [
            {"preferred_score": 0.9, "rejected_score": 0.1},
            {"preferred_score": 0.2, "rejected_score": 0.8},
        ]
        assert pairwise_accuracy(outcomes) == 0.5

    def test_tie_counts_as_half(self):
        outcomes = [{"preferred_score": 0.5, "rejected_score": 0.5}]
        assert pairwise_accuracy(outcomes) == 0.5

    def test_empty_rejected(self):
        with pytest.raises(MetricEligibilityError):
            pairwise_accuracy([])


class TestLogLoss:
    def test_perfect_probabilities_near_zero(self):
        assert log_loss([0.999, 0.999]) < 0.01

    def test_probability_bounds_enforced(self):
        with pytest.raises(MetricEligibilityError):
            log_loss([1.5])

    def test_uniform_probability_is_log2(self):
        assert math.isclose(log_loss([0.5]), math.log(2), rel_tol=1e-9)


class TestNdcgEligibility:
    def test_graded_labels_required(self):
        with pytest.raises(MetricEligibilityError, match="graded"):
            ndcg_at_k([{"type": "pairwise"}], k=3)

    def test_graded_labels_compute(self):
        ranking = [
            {"type": "graded", "grades_in_rank_order": [3, 0, 1], "all_grades": [3, 1, 0]}
        ]
        value = ndcg_at_k(ranking, k=3)
        assert 0.0 < value <= 1.0

    def test_perfect_order_is_one(self):
        ranking = [
            {"type": "graded", "grades_in_rank_order": [3, 1, 0], "all_grades": [3, 1, 0]}
        ]
        assert math.isclose(ndcg_at_k(ranking, k=3), 1.0, rel_tol=1e-9)


class TestMrrEligibility:
    def test_requires_single_positive(self):
        with pytest.raises(MetricEligibilityError, match="single-positive"):
            mrr([{"type": "pairwise"}])

    def test_single_positive_computes(self):
        queries = [
            {"type": "single_positive", "positive_rank": 1},
            {"type": "single_positive", "positive_rank": 2},
        ]
        assert math.isclose(mrr(queries), (1.0 + 0.5) / 2, rel_tol=1e-9)
