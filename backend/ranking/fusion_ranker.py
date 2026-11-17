"""fusion-5sig-v1: BPR-trained five-signal fusion, deployed variant.

Mirrors the offline research model (research/run_fusion.py
candidate_signals): audio cosine to session regions (mean- and
max-pooled), tempo match, key compatibility, and tag Jaccard, combined
with weights trained offline on pack co-membership weak labels.

Deployment deltas from the offline model, stated openly:
- Audiotool documents carry no key signature, so the session key is set
  only when the typed intent states one; otherwise the key term is zero.
  Compact fragment keys ("Em") are compared in the two-word form
  ("e minor") via serving_key;
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

from ranking import beat_sync
from ranking.audio_cosine import InsufficientContextError
from ranking.features import key_match, serving_key, tempo_match
from ranking.schemas import (
    FragmentCandidate,
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)

SIGNAL_NAMES = ["audio_cos_mean", "audio_cos_max", "tempo", "key", "tag_jaccard"]
# Logged after the five scored signals so decisions can later train weights
# for them (research/finetune_from_feedback.py --extra-signals). They do not
# enter the score; 0.0 when the session or the fragment has no beat data.
LOGGED_SIGNAL_NAMES = [*SIGNAL_NAMES, "chroma_beat_aligned", "onset_pattern"]

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
    """Load finite online weights, validating declared canonical signal order.

    Legacy unnamed five-weight artifacts use SIGNAL_NAMES in its fixed order.
    Extended and explicitly research-only artifacts are refused.
    """
    data = json.loads(pathlib.Path(path).read_text())
    if data.get("research_only") or data.get("deployable") is False:
        raise ValueError(
            "research-only artifact is not deployable by the five-signal online fusion"
        )
    if len(data["weights"]) != len(SIGNAL_NAMES):
        raise ValueError(
            f"online fusion requires {len(SIGNAL_NAMES)} weights; got {len(data['weights'])}. "
            "Extended weights are research-only"
        )
    if "signals" in data and data["signals"] != SIGNAL_NAMES:
        raise ValueError(f"online signals must be unique and in canonical order: {SIGNAL_NAMES}")
    weights = np.asarray(data["weights"], dtype=np.float64)
    if weights.shape != (len(SIGNAL_NAMES),) or not np.isfinite(weights).all():
        raise ValueError("online weights must be five finite scalar numbers")
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
                "key signal is zero unless the typed intent states a key "
                "(Audiotool reports none)",
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
                key_match(serving_key(request.session.key), serving_key(cand.key)),
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
            logit = float(contributions.sum())
            if logit >= 0:
                probability = 1.0 / (1.0 + math.exp(-logit))
            else:
                exp_logit = math.exp(logit)
                probability = exp_logit / (1.0 + exp_logit)
            score = round(probability, 6)
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
        served = ranked[: request.limit]
        frames_by_id = {c.fragment_id: c.beat_frames for c in request.candidates}
        beats = request.session.session_beats
        for candidate in served:
            measured = beat_sync.candidate_measurements(
                beats.model_dump() if beats else None, frames_by_id.get(candidate.fragment_id)
            )
            candidate.signals = [
                *candidate.signals,
                *(round(v, 6) for v in (measured.values if measured else (0.0, 0.0))),
            ]
            candidate.signal_available = [
                # The base five retain their deployed definitions, including
                # structural zero for absent key/tags/tempo. Beat signals
                # are optional measurements and require an explicit mask.
                *([True] * len(SIGNAL_NAMES)),
                *(measured.available if measured else (False, False)),
            ]
        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=served,
            signal_names=LOGGED_SIGNAL_NAMES,
        )
