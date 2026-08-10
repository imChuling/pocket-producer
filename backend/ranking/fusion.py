"""Reciprocal Rank Fusion.

Different representation spaces are not score-comparable, so fusion uses
ranks only (Cormack et al., SIGIR 2009). Hard-filtered ids are excluded
before fusion so they can never resurface through another space.
"""

RRF_K = 60  # standard smoothing constant from the RRF paper


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]],
    exclude: set[str] | None = None,
    k: int = RRF_K,
) -> list[str]:
    excluded = exclude or set()
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for position, (item_id, _score) in enumerate(ranked):
            if item_id in excluded:
                continue
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + position + 1)
    return sorted(scores, key=lambda item_id: (-scores[item_id], item_id))
