"""mean-session-v1: cosine against the mean embedding of active regions.

Context vectors arrive via session.region_audio_embeddings, populated only
when the session's sample audio is legitimately accessible. Without them
this ranker refuses (and the service falls back) instead of guessing.
"""

import numpy as np

from ranking.audio_cosine import InsufficientContextError
from ranking.cosine_core import rank_by_cosine
from ranking.schemas import RankRequest, RankResponse


class MeanSessionRanker:
    model_id = "mean-session-v1"
    model_card = {
        "id": "mean-session-v1",
        "task": "session-conditioned fragment ranking",
        "type": "cosine to the mean audio embedding of active session regions",
        "limitations": [
            "requires audio embeddings for session regions",
            "a mean erases which role is missing",
        ],
    }

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        regions = request.session.region_audio_embeddings
        if not regions:
            raise InsufficientContextError(
                "mean-session-v1 needs audio embeddings for session regions"
            )
        mean_vector = np.asarray(regions, dtype=np.float64).mean(axis=0)
        return rank_by_cosine(
            request,
            list(mean_vector),
            get_embedding=lambda candidate: candidate.audio_embedding,
            model_id=self.model_id,
            evidence_label="Fits the overall sound of your current session",
        )
