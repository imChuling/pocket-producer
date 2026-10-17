"""Exact cosine retrieval over a user's fragment vectors.

Personal libraries are small; exact search is the default until a measured
Recall@K–latency curve on representative library sizes justifies ANN
(evidence audit F2). user/deleted are hard permission filters applied before
scoring — they can never be outranked.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class IndexedVector:
    fragment_id: str
    user_id: str
    vector: list[float] = field(default_factory=list)
    deleted: bool = False


class ExactIndex:
    def __init__(self, entries: list[IndexedVector]):
        self._entries = entries

    def search(
        self, query: list[float], user_id: str, k: int
    ) -> list[tuple[str, float]]:
        eligible = [
            entry
            for entry in self._entries
            if entry.user_id == user_id and not entry.deleted
        ]
        if not eligible:
            return []
        matrix = np.asarray([entry.vector for entry in eligible], dtype=np.float64)
        query_vector = np.asarray(query, dtype=np.float64)
        if matrix.shape[1] != query_vector.shape[0]:
            raise ValueError(
                f"query dimension {query_vector.shape[0]} does not match "
                f"index dimension {matrix.shape[1]}"
            )
        matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
        query_vector = query_vector / np.linalg.norm(query_vector)
        cosines = matrix @ query_vector
        order = np.argsort(-cosines)[:k]
        return [
            (eligible[index].fragment_id, float(cosines[index]))
            for index in order
        ]
