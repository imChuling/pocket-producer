"""Online adapter for the capacity-ladder models (linear, deepsets, context).

Bridges the torch nn.Module forward interface (region_tokens, mask,
candidate, structured) to the RankerAdapter protocol (RankRequest →
RankResponse).  Models that cannot score a candidate (missing audio
embedding) skip it — skips are honest, never zero-filled.  If nothing at
all is scorable, the adapter raises InsufficientContextError so the
service falls back to rules instead of returning an empty success.
"""

import hashlib
import json
import uuid
from pathlib import Path

import torch

from ranking.audio_cosine import InsufficientContextError
from ranking.context_model import (
    LadderConfig,
    PocketRankContext,
    trainable_parameters,
)
from ranking.deepsets_ranker import DeepSetsRanker
from ranking.linear_ranker import LinearRanker
from ranking.schemas import (
    FragmentCandidate,
    RankedCandidate,
    RankEvidence,
    RankRequest,
    RankResponse,
)
from ranking.weak_pairs import CONTEXT_MAX

_MODEL_CLASSES = {
    "linear-v1": LinearRanker,
    "deepsets-v1": DeepSetsRanker,
    "pocketrank-context-v1": PocketRankContext,
}


class LadderRankerAdapter:
    def __init__(self, model_id: str, checkpoint_dir: str | Path):
        from safetensors.torch import load_file

        directory = Path(checkpoint_dir)
        config = LadderConfig(**json.loads((directory / "config.json").read_text()))
        cls = _MODEL_CLASSES.get(model_id)
        if cls is None:
            raise ValueError(f"unknown ladder model: {model_id}")
        if config.structured_dim != 0:
            raise ValueError(
                f"FSLD checkpoints were trained with structured_dim=0; "
                f"got {config.structured_dim} — refusing to serve with silent zero-fill"
            )
        self._model = cls(config)
        self._model.load_state_dict(load_file(str(directory / "model.safetensors")))
        self._model.eval()
        self._config = config
        self.model_id = model_id
        # Research provenance only — never the server filesystem path.
        weights = (directory / "model.safetensors").read_bytes()
        metrics_path = directory.parent / "metrics.json"
        metrics = (
            json.loads(metrics_path.read_text()) if metrics_path.is_file() else {}
        )
        self.model_card = {
            "id": model_id,
            "task": "session-conditioned fragment ranking",
            "type": f"learned reranker ({model_id})",
            "input_dim": config.input_dim,
            "trainable_parameters": trainable_parameters(self._model),
            "checkpoint_hash": f"sha256:{hashlib.sha256(weights).hexdigest()}",
            "dataset_hash": metrics.get("dataset_hash"),
            "label_layer": metrics.get("label_layer"),
        }

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        regions = request.session.region_audio_embeddings
        if not regions:
            raise InsufficientContextError(
                f"{self.model_id} needs session region audio embeddings"
            )

        context = torch.tensor(regions, dtype=torch.float32)
        if context.ndim != 2 or context.shape[1] != self._config.input_dim:
            raise InsufficientContextError(
                f"{self.model_id} got session embeddings of dim "
                f"{tuple(context.shape)}, expected (*, {self._config.input_dim})"
            )
        if not torch.isfinite(context).all():
            raise InsufficientContextError(
                f"{self.model_id} got non-finite session embeddings"
            )

        region_tokens = torch.zeros(CONTEXT_MAX, self._config.input_dim)
        mask = torch.ones(CONTEXT_MAX, dtype=torch.bool)
        n = min(context.shape[0], CONTEXT_MAX)
        region_tokens[:n] = context[:n]
        mask[:n] = False

        scorable: list[tuple[int, FragmentCandidate, torch.Tensor]] = []
        for idx, candidate in enumerate(request.candidates):
            if not candidate.audio_embedding:
                continue
            if len(candidate.audio_embedding) != self._config.input_dim:
                continue
            vector = torch.tensor(candidate.audio_embedding, dtype=torch.float32)
            if not torch.isfinite(vector).all():
                continue
            scorable.append((idx, candidate, vector))

        if not scorable:
            # An empty success would silently hide the rules ranker, which
            # can still order these candidates by structured features.
            raise InsufficientContextError(
                f"{self.model_id} cannot score any of the "
                f"{len(request.candidates)} candidates (no usable audio embeddings)"
            )

        candidate_batch = torch.stack([s[2] for s in scorable])
        batch_size = candidate_batch.shape[0]
        structured = torch.zeros(batch_size, self._config.structured_dim)

        with torch.no_grad():
            scores = self._model(
                region_tokens.unsqueeze(0).expand(batch_size, -1, -1),
                mask.unsqueeze(0).expand(batch_size, -1),
                candidate_batch,
                structured,
            )

        scored: list[tuple[float, FragmentCandidate]] = []
        for i, (_, candidate, _) in enumerate(scorable):
            scored.append((float(scores[i]), candidate))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        ranked = scored[: request.limit]

        return RankResponse(
            request_id=str(uuid.uuid4()),
            model_id=self.model_id,
            fallback_used=False,
            candidates=[
                RankedCandidate(
                    fragment_id=candidate.fragment_id,
                    score=round(score, 4),
                    evidence=[
                        RankEvidence(
                            code="model_signal",
                            label=f"Scored by {self.model_id}",
                            contribution=round(score, 4),
                        )
                    ],
                )
                for score, candidate in ranked
            ],
        )
