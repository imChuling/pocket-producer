"""role-gap-v1: rank candidates by how well they fill a missing instrument role.

This is the first retrieval space that captures something cosine similarity
fundamentally cannot: the relationship between what a session ALREADY HAS
and what it NEEDS. A session full of percussion loops has high cosine
similarity with more percussion — but a bass line would be more useful.

Requires CLAP audio embeddings on both session regions and candidates.
"""

import uuid

from ranking.audio_cosine import InsufficientContextError
from ranking.role_probe import RoleProbe
from ranking.schemas import (
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)


class RoleGapRanker:
    model_id = "role-gap-v1"
    model_card = {
        "id": "role-gap-v1",
        "task": "session-conditioned fragment ranking",
        "type": "zero-shot role-gap detection via CLAP instrument probe",
        "role_vocabulary": ["percussion", "bass", "chords", "melody", "fx", "vocal"],
        "limitations": [
            "requires CLAP audio embeddings for session regions and candidates",
            "zero-shot probe accuracy is ~0.41 on single-role FSLD items, ~0.37 on 3-stem mixtures",
            "multi-label roles (e.g. melodic bass) assign only the argmax role",
        ],
    }

    def __init__(self, probe: "RoleProbe | None" = None, *, adapter=None):
        self._probe = probe
        self._adapter = adapter

    def _ensure_probe(self):
        if self._probe is None and self._adapter is not None:
            from ranking.role_probe import build_probe_from_adapter
            self._probe = build_probe_from_adapter(self._adapter)
            self._adapter = None

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        self._ensure_probe()
        regions = request.session.region_audio_embeddings
        if not regions:
            raise InsufficientContextError(
                "role-gap-v1 needs audio embeddings for session regions"
            )

        session_roles = self._probe.session_roles(regions)

        # Candidates without an embedding cannot be placed in any role; leave
        # them out rather than serving them as zero-score proposals.
        scorable = [c for c in request.candidates if c.audio_embedding is not None]
        if not scorable:
            raise InsufficientContextError(
                f"role-gap-v1 cannot score any of the {len(request.candidates)} "
                "candidates (no audio embeddings)"
            )

        scored: list[RankedCandidate] = []
        for candidate in scorable:
            gap_role, conf = self._probe.gap_score(
                candidate.audio_embedding, session_roles
            )

            if gap_role is not None:
                present = ", ".join(sorted(session_roles.keys())) or "none detected"
                scored.append(
                    RankedCandidate(
                        fragment_id=candidate.fragment_id,
                        score=round(conf, 6),
                        evidence=[
                            RankEvidence(
                                code="role_gap_fill",
                                label=f"Adds {gap_role} (session has {present})",
                                contribution=round(conf, 6),
                            )
                        ],
                    )
                )
            else:
                role, _ = self._probe.classify(candidate.audio_embedding)
                scored.append(
                    RankedCandidate(
                        fragment_id=candidate.fragment_id,
                        score=0.0,
                        evidence=[
                            RankEvidence(
                                code="role_gap_fill",
                                label=f"Session already has {role}",
                                contribution=0.0,
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
