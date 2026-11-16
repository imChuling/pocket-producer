"""beat-fit-v1: rank candidates by harmony and rhythm in step with the session.

Score = beat-synchronous chroma agreement plus onset-pattern correlation,
each standardised over the candidates in the request. No weights are fitted;
this is the training-free combination that was strongest in the retrieval
study (research/results-retrieval-v1.md), there added after the behavioural
report and so an observation, not a tested claim.

Needs the session's beat data (project tempo plus region positions, built by
/api/ranking/session-embed) and each candidate's stored frames.
"""

import uuid

import numpy as np

from ranking import beat_sync
from ranking.audio_cosine import InsufficientContextError
from ranking.schemas import RankedCandidate, RankEvidence, RankRequest, RankResponse

_EVIDENCE = (
    ("beat_harmony", "Chords line up with the session's beats"),
    ("beat_rhythm", "Rhythm falls where the session's beats do"),
)


def _standardise(values: np.ndarray) -> np.ndarray:
    spread = values.std()
    return (values - values.mean()) / spread if spread > 0 else np.zeros_like(values)


class BeatFitRanker:
    model_id = "beat-fit-v1"
    model_card = {
        "id": "beat-fit-v1",
        "task": "session-conditioned fragment ranking",
        "type": "standardised sum of beat-synchronous chroma agreement and onset-pattern "
        "correlation, no fitted weights",
        "signals": list(beat_sync.SIGNAL_NAMES),
        "limitations": [
            "needs the project tempo; without it the session has no beat grid",
            "the fragment's first 10 s are compared with the session's first 10 s",
            "region loop and offset settings are ignored; each region plays its sample "
            "from the start",
            "selected post hoc on MUSDB18-HQ in the retrieval study",
        ],
    }

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        beats = request.session.session_beats
        if beats is None:
            raise InsufficientContextError(
                "beat-fit-v1 needs the session's tempo and region positions"
            )
        beats_dict = beats.model_dump()

        # A candidate without stored frames, or one that shares no sounding
        # beats or onsets with the session, has no evidence and is left out.
        scorable = []
        for candidate in request.candidates:
            values = beat_sync.candidate_signals(beats_dict, candidate.beat_frames)
            if values is not None and any(v > 0 for v in values):
                scorable.append((candidate, np.asarray(values, dtype=np.float64)))
        if not scorable:
            raise InsufficientContextError(
                f"beat-fit-v1 cannot score any of the {len(request.candidates)} candidates "
                "(no beat data)"
            )

        raw = np.stack([values for _, values in scorable])
        # With one candidate there is no set to standardise against; its own
        # values are the score and the evidence.
        parts = (
            np.column_stack([_standardise(raw[:, 0]), _standardise(raw[:, 1])])
            if len(scorable) > 1
            else raw
        )

        ranked: list[RankedCandidate] = []
        for (candidate, values), contributions in zip(scorable, parts):
            evidence = [
                RankEvidence(code=code, label=label, contribution=round(float(c), 6))
                for (code, label), c in zip(_EVIDENCE, contributions)
                if c > 0.0
            ]
            evidence.sort(key=lambda e: -e.contribution)
            ranked.append(
                RankedCandidate(
                    fragment_id=candidate.fragment_id,
                    score=round(float(contributions.sum()), 6),
                    evidence=evidence,
                    signals=[round(float(v), 6) for v in values],
                )
            )
        ranked.sort(key=lambda c: (-c.score, c.fragment_id))
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=ranked[: request.limit],
            signal_names=list(beat_sync.SIGNAL_NAMES),
        )
