"""Ranking service: resolve adapter, rank, stamp server-side request id."""

import logging
import uuid

from ranking.baselines import RulesRanker
from ranking.registry import FALLBACK_MODEL_ID, RankerRegistry
from ranking.schemas import RankRequest, RankResponse

logger = logging.getLogger(__name__)


class RankingService:
    def __init__(self, registry: RankerRegistry):
        self._registry = registry

    def rank(self, request: RankRequest) -> RankResponse:
        adapter, fallback_used = self._registry.resolve(request.model_id)
        try:
            response = adapter.rank(request)
        except Exception:
            # Any adapter failure degrades to the deterministic rules ranker;
            # the fallback is audited via fallback_used and this log line.
            logger.warning(
                "ranker %s failed; falling back to rules", adapter.model_id,
                exc_info=True,
            )
            adapter, _ = self._registry.resolve(FALLBACK_MODEL_ID)
            response = adapter.rank(request)
            fallback_used = True
        return response.model_copy(
            update={
                "request_id": str(uuid.uuid4()),
                "model_id": adapter.model_id,
                "fallback_used": fallback_used,
            }
        )

    def rank_fallback(self, request: RankRequest) -> RankResponse:
        adapter, _ = self._registry.resolve(FALLBACK_MODEL_ID)
        response = adapter.rank(request)
        return response.model_copy(
            update={
                "request_id": str(uuid.uuid4()),
                "model_id": adapter.model_id,
                "fallback_used": True,
            }
        )

    def model_cards(self) -> list[dict]:
        return [
            getattr(adapter, "model_card", None) or {"id": adapter.model_id}
            for adapter in self._registry.adapters()
        ]


def default_service() -> RankingService:
    import os

    from ranking.mean_session import MeanSessionRanker
    from ranking.recency import RecencyRanker
    from ranking.text_cosine import TextCosineRanker

    registry = RankerRegistry()
    registry.register(RulesRanker())
    registry.register(RecencyRanker())
    # Falls back automatically until session region audio is available.
    registry.register(MeanSessionRanker())

    def encode_intent_text(text: str) -> list[float]:
        # Same frozen Voyage model that produced the stored text vectors;
        # any API failure degrades to rules via the service fallback.
        from tools.embedding import _embed_sync

        return _embed_sync(text, "query")

    registry.register(TextCosineRanker(text_encoder=encode_intent_text))

    if os.environ.get("POCKET_ENABLE_CLAP") == "1":
        # Weights load lazily on the first request, never at import time.
        from ranking.adapters.msclap import MsClapAdapter
        from ranking.audio_cosine import AudioCosineRanker
        from ranking.role_gap_ranker import RoleGapRanker
        from ranking.role_probe import build_probe_from_adapter

        clap = MsClapAdapter()

        def encode_intent_audio_space(text: str) -> list[float]:
            return clap.encode_text([text])[0].tolist()

        registry.register(AudioCosineRanker(text_encoder=encode_intent_audio_space))
        registry.register(RoleGapRanker(probe=build_probe_from_adapter(clap)))

    from ranking.harmonic_ranker import HarmonicFitRanker

    registry.register(HarmonicFitRanker())

    from pathlib import Path as _Path

    fusion_weights = _Path(
        os.environ.get(
            "POCKET_FUSION_WEIGHTS", "artifacts/fusion-deploy/weights.json"
        )
    )
    if not fusion_weights.is_file() and not fusion_weights.is_absolute():
        # Fall back to repo-root-relative when running from backend/.
        fusion_weights = _Path(__file__).resolve().parents[2] / fusion_weights

    if fusion_weights.is_file():
        from ranking.fusion_ranker import FusionRanker, load_weights

        try:
            registry.register(FusionRanker(load_weights(fusion_weights)))
            logger.info("registered fusion-5sig-v1 from %s", fusion_weights)
        except Exception:
            logger.warning(
                "failed to load fusion weights from %s", fusion_weights, exc_info=True
            )

    ladder_dir = os.environ.get("POCKET_LADDER_DIR", "")
    if ladder_dir:
        from pathlib import Path

        from ranking.ladder_adapter import LadderRankerAdapter

        base = Path(ladder_dir)
        for model_id in ("linear-v1", "deepsets-v1", "pocketrank-context-v1"):
            checkpoint = base / model_id
            if (checkpoint / "model.safetensors").is_file():
                try:
                    registry.register(LadderRankerAdapter(model_id, checkpoint))
                    logger.info("registered ladder model %s from %s", model_id, checkpoint)
                except Exception:
                    logger.warning("failed to load %s from %s", model_id, checkpoint, exc_info=True)

    return RankingService(registry)
