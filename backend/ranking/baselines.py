"""Deterministic, explainable rules baseline (rules-v1).

Every score component simultaneously produces its evidence entry; natural
language is never generated first and rationalized afterwards.
"""

import uuid

from ranking import features
from ranking.schemas import (
    FragmentCandidate,
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
    SessionFingerprint,
)

WEIGHTS = {
    "tempo_match": 0.30,
    "key_match": 0.20,
    "track_gap": 0.10,
    "intent_match": 0.25,
    "novelty": 0.10,
    "recency": 0.05,
}

_LABELS = {
    "tempo_match": "Tempo close to the project's BPM",
    "key_match": "Same key as the project",
    "track_gap": "Adds a role the session doesn't have yet",
    "intent_match": "Matches your stated intent",
    "novelty": "Brings new material into the session",
    "recency": "Recently captured fragment",
}


class RulesRanker:
    model_id = "rules-v1"
    model_card = {
        "id": "rules-v1",
        "task": "session-conditioned fragment ranking",
        "type": "deterministic explainable rules",
        "features": sorted(WEIGHTS),
        "network": "none",
        "limitations": [
            "hand-tuned weights, not learned",
            "no audio content understanding beyond metadata",
        ],
    }

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        newest_iso = max(
            (c.created_at_iso for c in request.candidates), default=""
        )
        scored = [
            self._score(request.session, candidate, newest_iso)
            for candidate in request.candidates
        ]
        scored.sort(key=lambda c: (-c.score, c.fragment_id))
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=scored[: request.limit],
        )

    def _score(
        self,
        session: SessionFingerprint,
        candidate: FragmentCandidate,
        newest_iso: str,
    ) -> RankedCandidate:
        values = {
            "tempo_match": features.tempo_match(session.bpm, candidate.bpm),
            "key_match": features.key_match(session.key, candidate.key),
            "track_gap": features.track_gap(
                session.active_track_types, candidate.tags
            ),
            "intent_match": features.intent_match(
                session.text_intent, candidate.tags
            ),
            "novelty": features.novelty(
                candidate.tags, session.active_track_types, session.text_intent
            ),
            "recency": features.recency(candidate.created_at_iso, newest_iso),
        }
        evidence = [
            RankEvidence(
                code=code,
                label=_LABELS[code],
                contribution=round(WEIGHTS[code] * value, 6),
            )
            for code, value in values.items()
            if value > 0.0
        ]
        evidence.sort(key=lambda e: -e.contribution)
        score = sum(WEIGHTS[code] * value for code, value in values.items())
        return RankedCandidate(
            fragment_id=candidate.fragment_id,
            score=round(score, 6),
            evidence=evidence,
        )
