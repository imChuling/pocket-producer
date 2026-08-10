"""Adapter registry with mandatory rules fallback.

Any requested model that is missing or unhealthy resolves to rules-v1; the
caller is told a fallback happened so it can be audited and surfaced in the UI.
"""

from typing import Protocol, runtime_checkable

from ranking.schemas import RankRequest, RankResponse

FALLBACK_MODEL_ID = "rules-v1"


@runtime_checkable
class RankerAdapter(Protocol):
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
