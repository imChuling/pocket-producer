"""audio-cosine-v1: rank candidates by CLAP cross-modal cosine.

The context vector comes from the user's stated text intent encoded with the
same frozen audio-text model that produced the candidate audio vectors, so
"gloomy pad" can match a dark pad even when no tag words overlap. Candidates
without an audio representation score zero and carry no fabricated evidence.
"""

from collections.abc import Callable

from ranking.cosine_core import rank_by_cosine
from ranking.schemas import RankRequest, RankResponse


class InsufficientContextError(ValueError):
    """The request lacks the context this ranker needs (e.g. no text intent)."""


class AudioCosineRanker:
    model_id = "audio-cosine-v1"
    model_card = {
        "id": "audio-cosine-v1",
        "task": "session-conditioned fragment ranking",
        "type": "frozen audio-text embedding cosine (text intent as query)",
        "representation_model": "msclap-2023",
        "limitations": [
            "requires a non-empty text intent",
            "no session-structure awareness",
        ],
    }

    def __init__(self, text_encoder: Callable[[str], list[float]]):
        self._text_encoder = text_encoder

    def healthy(self) -> bool:
        return True

    def rank(self, request: RankRequest) -> RankResponse:
        intent = request.session.text_intent.strip()
        if not intent:
            raise InsufficientContextError(
                "audio-cosine-v1 needs a text intent as its query"
            )
        return rank_by_cosine(
            request,
            self._text_encoder(intent),
            get_embedding=lambda candidate: candidate.audio_embedding,
            model_id=self.model_id,
            evidence_label=f'Sounds close to your intent "{intent}"',
        )
