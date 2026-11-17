"""Adapter registry with mandatory rules fallback.

Any requested model that is missing or unhealthy resolves to rules-v1; the
caller is told a fallback happened so it can be audited and surfaced in the UI.
"""

from typing import Protocol, runtime_checkable

from ranking.schemas import RankRequest, RankResponse

FALLBACK_MODEL_ID = "rules-v1"


@runtime_checkable
class RankerAdapter(Protocol):
    """What the ranking service expects of every registered ranker.

    `model_id` is the unique id clients select. `healthy()` is checked when
    the id is resolved; a ranker that reports unhealthy is replaced by the
    rules fallback. `rank()` may raise for any reason, for example when the
    request lacks the audio or session data it needs: the service catches
    the exception and serves `rules-v1` on the same request with
    `fallback_used` set, so raising is the intended way to decline. It must
    not mutate the request, because that same object is then passed to the
    fallback and written to the exposure log. It returns at most
    `request.limit` candidates, each drawn from `request.candidates`.
    """

    model_id: str

    def healthy(self) -> bool: ...

    def rank(self, request: RankRequest) -> RankResponse: ...


class RankerRegistry:
    def __init__(self):
        self._adapters: dict[str, RankerAdapter] = {}

    def register(self, adapter: RankerAdapter) -> None:
        self._adapters[adapter.model_id] = adapter

    def adapters(self) -> list[RankerAdapter]:
        return list(self._adapters.values())

    def resolve(self, requested: str) -> tuple[RankerAdapter, bool]:
        adapter = self._adapters.get(requested)
        if adapter is not None and adapter.healthy():
            return adapter, False
        return self._adapters[FALLBACK_MODEL_ID], requested != FALLBACK_MODEL_ID
