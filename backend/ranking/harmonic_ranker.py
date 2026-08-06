"""harmonic-fit-v1: rank candidates by tonal compatibility with the session.

Scores each candidate's chroma profile against the session's aggregated
chroma using transpose-invariant cross-correlation. This captures whether
a candidate is in a compatible key — something neither CLAP cosine nor
role-gap detection can express.

Requires pre-computed 12-dim chroma vectors on session regions and candidates.
"""

import uuid

from ranking.audio_cosine import InsufficientContextError
from ranking.harmonic_probe import (
    session_chroma,
    shift_label,
    transpose_invariant_score,
)
from ranking.schemas import (
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)


class HarmonicFitRanker:
    model_id = "harmonic-fit-v1"
    model_card = {
        "id": "harmonic-fit-v1",
        "task": "session-conditioned fragment ranking",
        "type": "transpose-invariant chroma cross-correlation",
        "chroma_method": "CQT-based 12-dim mean chroma profile",
        "limitations": [
            "requires pre-computed chroma vectors for session regions and candidates",
            "mean chroma loses temporal structure (key changes within a loop)",
            "percussion-heavy regions produce weak chroma signal",
        ],
    }

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        region_chromas = request.session.region_chroma_vectors
        if not region_chromas:
            raise InsufficientContextError(
                "harmonic-fit-v1 needs chroma vectors for session regions"
            )

        sess_chroma = session_chroma(region_chromas)

        scored: list[RankedCandidate] = []
        for candidate in request.candidates:
            if candidate.chroma_vector is None:
                scored.append(
                    RankedCandidate(
                        fragment_id=candidate.fragment_id, score=0.0, evidence=[]
                    )
                )
                continue

            score, shift = transpose_invariant_score(
                sess_chroma, candidate.chroma_vector
            )

            scored.append(
                RankedCandidate(
                    fragment_id=candidate.fragment_id,
                    score=score,
                    evidence=[
                        RankEvidence(
                            code="harmonic_fit",
                            label=f"Harmonically compatible ({shift_label(shift)})",
                            contribution=score,
                        )
                    ],
                )
            )

        scored.sort(key=lambda c: (-c.score, c.fragment_id))
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=scored[: request.limit],
        )
