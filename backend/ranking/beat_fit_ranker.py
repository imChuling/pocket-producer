"""beat-fit-v1: rank candidates by harmony and rhythm in step with the session.

Score = beat-synchronous chroma agreement plus shared-beat onset correlation,
each standardised over the candidates in the request. No weights are fitted.
Combining harmony and rhythm is a product design choice; the retrieval
study did not establish a gain over onset_pattern alone. It was added after
the behavioural report on the same recordings and needs independent validation.

Needs the session's beat data (project tempo plus region positions, built by
/api/ranking/session-embed) and each candidate's stored frames.
"""

import uuid

import numpy as np

from ranking import beat_sync
from ranking.audio_cosine import InsufficientContextError
from ranking.schemas import RankedCandidate, RankEvidence, RankRequest, RankResponse


def _standardise(values: np.ndarray) -> np.ndarray:
    spread = values.std()
    return (values - values.mean()) / spread if spread > 0 else np.zeros_like(values)


class BeatFitRanker:
    model_id = "beat-fit-v1"
    model_card = {
        "id": "beat-fit-v1",
        "task": "session-conditioned fragment ranking",
        "type": "standardised sum of beat-synchronous chroma agreement and shared-beat onset "
        "correlation, no fitted weights",
        "signals": list(beat_sync.BEAT_FIT_SIGNAL_NAMES),
        "implementation_revision": "shared-beat-onsets-v4",
        "limitations": [
            "needs the project tempo; without it the session has no beat grid",
            "the fragment's first 10 s are compared with the session's first 10 s",
            "region loop and offset settings are ignored; each region plays its sample "
            "from the start",
            "the original full-grid combination was selected post hoc on MUSDB18-HQ",
            "shared-beat onset correlation has no independent retrieval or listener evaluation",
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

        # Signal support is independent of its value and of the other
        # candidates. A mapped correlation > 0 is not evidence of alignment.
        scorable = []
        for candidate in request.candidates:
            measured = beat_sync.candidate_measurements(
                beats_dict, candidate.beat_frames, shared_onsets_only=True,
            )
            if measured is not None and any(measured.available):
                scorable.append((candidate, measured))
        if not scorable:
            raise InsufficientContextError(
                f"beat-fit-v1 cannot score any of the {len(request.candidates)} candidates "
                "(no beat data)"
            )

        raw = np.asarray([m.values for _, m in scorable], dtype=np.float64)
        available = np.asarray([m.available for _, m in scorable], dtype=bool)
        # A measurement unique to one candidate can be shown but cannot compare two clips.
        parts = np.zeros_like(raw)
        for index in range(raw.shape[1]):
            usable = available[:, index]
            values = raw[usable, index]
            if len(scorable) == 1:
                parts[usable, index] = values
            elif values.size > 1:
                parts[usable, index] = _standardise(values)

        ranked: list[RankedCandidate] = []
        for (candidate, measured), contributions in zip(scorable, parts):
            evidence = []
            for index, (code, name, value) in enumerate((
                ("beat_harmony", "Beat chroma cosine", measured.values[0]),
                ("beat_rhythm", "Onset correlation", measured.onset_correlation),
            )):
                if not measured.available[index]:
                    continue
                tied = (available[:, index].sum() > 1
                        and np.ptp(raw[available[:, index], index]) == 0)
                label = f"{name} {value:.2f} ({measured.shared_beats} shared beats)"
                if tied:
                    label += "; tied across candidates"
                evidence.append(RankEvidence(
                    code=code, label=label, raw_value=round(float(value), 6),
                    contribution=round(float(contributions[index]), 6),
                ))
            evidence.sort(key=lambda e: -e.contribution)
            ranked.append(
                RankedCandidate(
                    fragment_id=candidate.fragment_id,
                    score=round(float(contributions.sum()), 6),
                    evidence=evidence,
                    signals=[round(float(v), 6) for v in measured.values],
                    signal_available=list(measured.available),
                )
            )
        ranked.sort(key=lambda c: (-c.score, c.fragment_id))
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            implementation_revision=self.model_card["implementation_revision"],
            fallback_used=False,
            candidates=ranked[: request.limit],
            signal_names=list(beat_sync.BEAT_FIT_SIGNAL_NAMES),
        )
