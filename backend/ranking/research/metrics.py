"""Label-compatible metrics (evidence audit J2/J3/J4).

Each metric declares the label semantics it needs and refuses anything else:
pairwise choices yield accuracy/log loss; nDCG needs graded relevance; MRR
needs a single known positive. Small formative samples report raw counts —
population-level significance is out of scope here.
"""

import math


class MetricEligibilityError(ValueError):
    """The provided labels do not support the requested metric."""


def pairwise_accuracy(outcomes: list[dict]) -> float:
    """outcomes: [{"preferred_score": float, "rejected_score": float}, ...]"""
    if not outcomes:
        raise MetricEligibilityError("pairwise accuracy needs at least one pair")
    total = 0.0
    for outcome in outcomes:
        preferred = outcome["preferred_score"]
        rejected = outcome["rejected_score"]
        if preferred > rejected:
            total += 1.0
        elif preferred == rejected:
            total += 0.5
    return total / len(outcomes)


def log_loss(preferred_probabilities: list[float]) -> float:
    """Mean negative log-likelihood of the preferred item winning."""
    if not preferred_probabilities:
        raise MetricEligibilityError("log loss needs at least one probability")
    for probability in preferred_probabilities:
        if not 0.0 < probability < 1.0:
            raise MetricEligibilityError(
                f"probability {probability} outside (0, 1); "
                "calibrate scores before using log loss"
            )
    return -sum(math.log(p) for p in preferred_probabilities) / len(
        preferred_probabilities
    )


def _dcg(grades: list[int], k: int) -> float:
    return sum(
        (2**grade - 1) / math.log2(position + 2)
        for position, grade in enumerate(grades[:k])
    )


def ndcg_at_k(rankings: list[dict], k: int) -> float:
    """rankings: [{"type": "graded", "grades_in_rank_order": [...],
    "all_grades": [...]}, ...] — refuses non-graded labels."""
    if not rankings:
        raise MetricEligibilityError("nDCG needs at least one ranking")
    values = []
    for ranking in rankings:
        if ranking.get("type") != "graded":
            raise MetricEligibilityError(
                "nDCG requires graded relevance labels; "
                f"got {ranking.get('type')!r} — use pairwise accuracy instead"
            )
        ideal = _dcg(sorted(ranking["all_grades"], reverse=True), k)
        if ideal == 0:
            continue
        values.append(_dcg(ranking["grades_in_rank_order"], k) / ideal)
    if not values:
        raise MetricEligibilityError("no ranking had a positive ideal DCG")
    return sum(values) / len(values)


def mrr(queries: list[dict]) -> float:
    """queries: [{"type": "single_positive", "positive_rank": int>=1}, ...]"""
    if not queries:
        raise MetricEligibilityError("MRR needs at least one query")
    reciprocal_ranks = []
    for query in queries:
        if query.get("type") != "single_positive":
            raise MetricEligibilityError(
                "MRR requires single-positive labels; "
                f"got {query.get('type')!r}"
            )
        reciprocal_ranks.append(1.0 / query["positive_rank"])
    return sum(reciprocal_ranks) / len(reciprocal_ranks)
