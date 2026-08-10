"""text-only-v1: legacy Voyage text-embedding cosine against the text intent.

This is the strongest thing the June system could do — kept as the honest
"what we had before" baseline. The query is the text intent embedded with the
same frozen Voyage model that produced the stored fragment text vectors.
"""

from collections.abc import Callable

from ranking.audio_cosine import InsufficientContextError
from ranking.cosine_core import rank_by_cosine
from ranking.schemas import RankRequest, RankResponse


class TextCosineRanker:
    model_id = "text-only-v1"
    model_card = {
        "id": "text-only-v1",
        "task": "session-conditioned fragment ranking",
        "type": "frozen text-embedding cosine (voyage-3, text intent as query)",
        "representation_model": "voyage-3",
        "limitations": [
            "requires a non-empty text intent",
            "blind to the audio itself; relies on transcripts/tags",
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
                "text-only-v1 needs a text intent as its query"
            )
        return rank_by_cosine(
            request,
            self._text_encoder(intent),
            get_embedding=lambda candidate: candidate.text_embedding,
            model_id=self.model_id,
            evidence_label=f'Description matches your intent "{intent}"',
        )
