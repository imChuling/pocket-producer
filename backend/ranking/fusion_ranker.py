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
    FragmentCandidate,
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)

SIGNAL_NAMES = ["audio_cos_mean", "audio_cos_max", "tempo", "key", "tag_jaccard"]

_EVIDENCE = [
    ("timbral_match", "Sounds close to your session regions"),
    ("tempo_match", "Tempo fits the session"),
    ("key_match", "Key compatibility"),
    ("tag_overlap", "Shares tags with recent fragments"),
]


def _group(contributions: np.ndarray) -> np.ndarray:
    """Collapse the two cosine terms into one timbral contribution."""
    return np.array([
        contributions[0] + contributions[1],
        contributions[2],
        contributions[3],
        contributions[4],
    ])


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

        # Candidates without an audio embedding cannot be scored by this
        # ranker; they are left out rather than served as evidence-free
        # proposals at the bottom of the list.
        scored: list[tuple[FragmentCandidate, np.ndarray, np.ndarray]] = []
        for cand in request.candidates:
            if not cand.audio_embedding:
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
            scored.append((cand, signals, self._w * signals))
        if not scored:
            raise InsufficientContextError(
                f"fusion-5sig-v1 cannot score any of the {len(request.candidates)} "
                "candidates (no audio embeddings)"
            )

        # Evidence is relative to the other scorable candidates in this
        # request: a chip appears only where this candidate beats the mean,
        # so the cosine baseline level shared by every candidate is not
        # presented as a reason. With a single candidate there is no set to
        # compare against, so its own positive contributions are shown.
        grouped = np.stack([_group(c) for _, _, c in scored])
        baseline = grouped.mean(axis=0) if len(scored) > 1 else np.zeros(grouped.shape[1])

        ranked: list[RankedCandidate] = []
        for (cand, signals, contributions), group in zip(scored, grouped):
            score = round(1.0 / (1.0 + math.exp(-float(contributions.sum()))), 6)
            relative = group - baseline
            evidence = [
                RankEvidence(code=code, label=label, contribution=round(float(c), 6))
                for (code, label), c in zip(_EVIDENCE, relative)
                if c > 0.0
            ]
            evidence.sort(key=lambda e: -e.contribution)
            ranked.append(
                RankedCandidate(
                    fragment_id=cand.fragment_id,
                    score=score,
                    evidence=evidence,
                    signals=[round(float(s), 6) for s in signals],
                )
            )

        ranked.sort(key=lambda c: (-c.score, c.fragment_id))
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=ranked[: request.limit],
        )
