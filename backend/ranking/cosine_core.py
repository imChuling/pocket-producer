"""Shared cosine-ranking core for embedding baselines.

Candidates missing the required embedding score zero with no fabricated
evidence; scores map cosine [-1, 1] to [0, 1]; ties break on fragment id.
"""

import uuid
from collections.abc import Callable

import numpy as np

from ranking.schemas import (
    FragmentCandidate,
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)


def rank_by_cosine(
    request: RankRequest,
    query_vector: list[float],
    get_embedding: Callable[[FragmentCandidate], list[float] | None],
    model_id: str,
    evidence_label: str,
) -> RankResponse:
    query = np.asarray(query_vector, dtype=np.float64)
    query = query / np.linalg.norm(query)

    ranked: list[RankedCandidate] = []
    for candidate in request.candidates:
        embedding = get_embedding(candidate)
        if not embedding:
            ranked.append(
                RankedCandidate(
                    fragment_id=candidate.fragment_id, score=0.0, evidence=[]
                )
            )
            continue
        vector = np.asarray(embedding, dtype=np.float64)
        cosine = float(vector @ query / np.linalg.norm(vector))
        score = round((cosine + 1.0) / 2.0, 6)
        ranked.append(
            RankedCandidate(
                fragment_id=candidate.fragment_id,
                score=score,
                evidence=[
                    RankEvidence(
                        code="model_signal",
                        label=evidence_label,
                        contribution=score,
                    )
                ],
            )
        )
    ranked.sort(key=lambda c: (-c.score, c.fragment_id))
    return RankResponse(
        request_id=str(uuid.uuid4()),
        model_id=model_id,
        fallback_used=False,
        candidates=ranked[: request.limit],
    )
