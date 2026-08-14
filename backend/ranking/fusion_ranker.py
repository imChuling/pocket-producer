"""fusion-5sig-v1: BPR-trained five-signal fusion, deployed variant.

Mirrors the offline research model (research/run_fusion.py
candidate_signals): audio cosine to session regions (mean- and
max-pooled), tempo match, key compatibility, and tag Jaccard, combined
with weights trained offline on pack co-membership weak labels.

Deployment deltas from the offline model, stated openly:
- key is always None in Audiotool sessions (documents carry no key
  signature), so the key term contributes zero online;
- context tags come from session.context_tags (recently used
  fragments), not pack siblings.

Requires session region audio embeddings; without them this ranker
refuses (and the service falls back) instead of scoring on partial
signals the weights were not trained for.
"""

import json
import math
import pathlib
import uuid

import numpy as np

from ranking.audio_cosine import InsufficientContextError
from ranking.features import key_match, tempo_match
from ranking.schemas import (
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)

SIGNAL_NAMES = ["audio_cos_mean", "audio_cos_max", "tempo", "key", "tag_jaccard"]


def load_weights(path: str | pathlib.Path) -> dict:
    """Load a weights artifact: {"weights": [5 floats], "trained_on": ...}."""
    data = json.loads(pathlib.Path(path).read_text())
    if len(data["weights"]) != len(SIGNAL_NAMES):
        raise ValueError(
            f"expected {len(SIGNAL_NAMES)} weights, got {len(data['weights'])}"
        )
    return data


class FusionRanker:
    model_id = "fusion-5sig-v1"

    def __init__(self, weights_artifact: dict):
        self._w = np.asarray(weights_artifact["weights"], dtype=np.float64)
        self.model_card = {
            "id": self.model_id,
            "task": "session-conditioned fragment ranking",
            "type": "BPR logistic fusion of five similarity signals",
            "signals": SIGNAL_NAMES,
            "trained_on": weights_artifact.get("trained_on", "unknown"),
            "representation_model": weights_artifact.get(
                "representation_model", "unknown"
            ),
            "limitations": [
                "requires audio embeddings for session regions",
                "key signal is constant zero online (Audiotool has no key)",
                "weights trained on pack co-membership weak labels, not "
                "human continuation preference",
            ],
        }

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        regions = request.session.region_audio_embeddings
        if not regions:
            raise InsufficientContextError(
                "fusion-5sig-v1 needs audio embeddings for session regions"
            )

        ctx = np.asarray(regions, dtype=np.float64)
        ctx = ctx / np.linalg.norm(ctx, axis=1, keepdims=True)
        mean_ctx = ctx.mean(axis=0)
        mean_ctx = mean_ctx / np.linalg.norm(mean_ctx)

        ctx_tags = {t.lower() for t in request.session.context_tags}

        ranked: list[RankedCandidate] = []
        for cand in request.candidates:
            if not cand.audio_embedding:
                ranked.append(
                    RankedCandidate(
                        fragment_id=cand.fragment_id, score=0.0, evidence=[]
                    )
                )
                continue

            vec = np.asarray(cand.audio_embedding, dtype=np.float64)
            vec = vec / np.linalg.norm(vec)
            cand_tags = {t.lower() for t in cand.tags}
            union = ctx_tags | cand_tags
            signals = np.array([
                float(mean_ctx @ vec),
                float((ctx @ vec).max()),
                tempo_match(request.session.bpm, cand.bpm),
                key_match(request.session.key, cand.key),
                len(ctx_tags & cand_tags) / len(union) if union else 0.0,
            ])
            contributions = self._w * signals
            score = round(1.0 / (1.0 + math.exp(-float(contributions.sum()))), 6)

            # Zero-contribution signals carry no evidence: a missing input
            # (e.g. key, which Audiotool never provides) must not surface
            # as a reason for the recommendation.
            evidence = [
                RankEvidence(code=code, label=label, contribution=round(c, 6))
                for code, label, c in [
                    (
                        "timbral_match",
                        "Sounds close to your session regions",
                        float(contributions[0] + contributions[1]),
                    ),
                    ("tempo_match", "Tempo fits the session", float(contributions[2])),
                    ("key_match", "Key compatibility", float(contributions[3])),
                    (
                        "tag_overlap",
                        "Shares tags with recent fragments",
                        float(contributions[4]),
                    ),
                ]
                if c != 0.0
            ]
            ranked.append(
                RankedCandidate(
                    fragment_id=cand.fragment_id, score=score, evidence=evidence
                )
            )

        ranked.sort(key=lambda c: (-c.score, c.fragment_id))
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=ranked[: request.limit],
        )
