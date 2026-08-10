"""Exact cosine retrieval with hard permission/validity filters."""

import numpy as np
import pytest

from ranking.retrieval import ExactIndex, IndexedVector


def vec(*values: float) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    return list(array / np.linalg.norm(array))


def build_index() -> ExactIndex:
    return ExactIndex(
        [
            IndexedVector(fragment_id="f1", user_id="u1", vector=vec(1, 0, 0)),
            IndexedVector(fragment_id="f2", user_id="u1", vector=vec(0.9, 0.1, 0)),
            IndexedVector(fragment_id="f3", user_id="u1", vector=vec(0, 1, 0), deleted=True),
            IndexedVector(fragment_id="g1", user_id="u2", vector=vec(1, 0, 0)),
        ]
    )


class TestExactIndex:
    def test_returns_ranked_matches_for_owner_only(self):
        results = build_index().search(vec(1, 0, 0), user_id="u1", k=10)
        ids = [fragment_id for fragment_id, _ in results]
        assert ids[0] == "f1"
        assert "g1" not in ids

    def test_deleted_fragments_are_hard_filtered(self):
        results = build_index().search(vec(0, 1, 0), user_id="u1", k=10)
        assert all(fragment_id != "f3" for fragment_id, _ in results)

    def test_k_truncates(self):
        results = build_index().search(vec(1, 0, 0), user_id="u1", k=1)
        assert len(results) == 1

    def test_empty_library_returns_empty(self):
        assert ExactIndex([]).search(vec(1, 0, 0), user_id="u1", k=5) == []

    def test_dimension_mismatch_raises(self):
        with pytest.raises(ValueError, match="dimension"):
            build_index().search(vec(1, 0), user_id="u1", k=5)

    def test_scores_are_cosines_descending(self):
        results = build_index().search(vec(1, 0, 0), user_id="u1", k=10)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)
        assert all(-1.0 <= score <= 1.0 for score in scores)
