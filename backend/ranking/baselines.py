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

# Filling a role the session lacks outweighs repeating one it has: a full
# tag duplicate (tag_overlap 1.0) scores below a new role (track_gap +
# novelty), while partial tag overlap still rewards coherence.
WEIGHTS = {
    "tempo_match": 0.25,
    "key_match": 0.20,
    "track_gap": 0.15,
    "intent_match": 0.20,
    "novelty": 0.05,
    "tag_overlap": 0.10,
    "recency": 0.05,
}

# Offline stand-in for rules-v1 on FSLD pairs, where only these three of its
# signals are computable. The ratios are frozen by
# protocol-heldout-correction-v1; the published held-out rules numbers
# depend on them, so they are not tied to the live WEIGHTS above.
OFFLINE_STANDIN_WEIGHTS = {
    "tempo_match": 0.30,
    "key_match": 0.20,
    "tag_overlap": 0.35,
}

_LABELS = {
    "tempo_match": "Tempo close to the project's BPM",
    "key_match": "Same key as the project",
    "track_gap": "Adds a role the session doesn't have yet",
    "intent_match": "Matches your stated intent",
    "novelty": "Brings new material into the session",
    "tag_overlap": "Shares tags with fragments in this session",
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
                session.active_track_types, candidate.tags, session.context_tags
            ),
            "intent_match": features.intent_match(
                session.text_intent, candidate.tags
            ),
            "novelty": features.novelty(
                candidate.tags,
                session.active_track_types,
                session.text_intent,
                session.context_tags,
            ),
            "tag_overlap": features.tag_overlap(session.context_tags, candidate.tags),
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
