"""recency-v1: most recent fragments first — the simplest honest baseline."""

import uuid

from ranking.features import recency
from ranking.schemas import (
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)


class RecencyRanker:
    model_id = "recency-v1"
    model_card = {
        "id": "recency-v1",
        "task": "session-conditioned fragment ranking",
        "type": "most-recent-first heuristic",
        "limitations": ["ignores session context entirely"],
    }

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        newest = max(
            (c.created_at_iso for c in request.candidates), default=""
        )
        ranked = [
            RankedCandidate(
                fragment_id=candidate.fragment_id,
                score=round(recency(candidate.created_at_iso, newest), 6),
                evidence=[
                    RankEvidence(
                        code="recency",
                        label="Recently captured fragment",
                        contribution=round(
                            recency(candidate.created_at_iso, newest), 6
                        ),
                    )
                ],
            )
            for candidate in request.candidates
        ]
        ranked.sort(key=lambda c: (-c.score, c.fragment_id))
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=ranked[: request.limit],
        )
