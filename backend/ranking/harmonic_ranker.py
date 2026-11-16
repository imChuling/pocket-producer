"""harmonic-fit-v1: rank candidates by pitch-class similarity to the session.

Scores each candidate's mean chroma profile against the session's aggregated
chroma under the best of 12 transpositions. Despite the name, this measures
whether a candidate could fit after transposing it, not whether it fits as
played: an untransposed candidate and a copy a semitone away score alike.
The behavioural tests confirm it (research/results-behavioral-v1.md, P2:
0.49, blind). The product never transposes a fragment, so a shift other
than 0 in the evidence label is stated as a condition ("if transposed").

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
            "transpose-invariant: does not tell whether a candidate fits in its "
            "current key (behavioural test P2 blind, 0.49)",
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

        # Candidates without a chroma vector cannot be scored here; leaving
        # them out matches fusion-5sig-v1 rather than serving evidence-free
        # zero-score proposals.
        scorable = [c for c in request.candidates if c.chroma_vector is not None]
        if not scorable:
            raise InsufficientContextError(
                f"harmonic-fit-v1 cannot score any of the {len(request.candidates)} "
                "candidates (no chroma vectors)"
            )

        scored: list[RankedCandidate] = []
        for candidate in scorable:
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
                            label=f"Pitch classes resemble the session {shift_label(shift)}",
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
