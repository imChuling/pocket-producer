"""Tests for ranker registry resolution and safe fallback."""

from ranking.baselines import RulesRanker
from ranking.registry import RankerRegistry
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint
from ranking.service import RankingService


def make_request(model_id: str = "rules-v1") -> RankRequest:
    return RankRequest(
        session=SessionFingerprint(
            project_id="p1",
            playhead_seconds=0,
            track_count=1,
            active_track_types=["drums"],
        ),
        candidates=[
            FragmentCandidate(
                fragment_id="f1",
                duration_seconds=4.0,
                created_at_iso="2026-07-01T00:00:00Z",
                audio_url="/api/fragments/f1/audio",
            )
        ],
        model_id=model_id,
    )


class UnhealthyRanker:
    model_id = "broken-v1"

    def healthy(self) -> bool:
        return False

    def rank(self, request):  # pragma: no cover - must never be called
        raise AssertionError("unhealthy adapter must not be used")


def registry() -> RankerRegistry:
    reg = RankerRegistry()
    reg.register(RulesRanker())
    reg.register(UnhealthyRanker())
    return reg


class TestRegistry:
    def test_known_healthy_adapter_resolves_without_fallback(self):
        adapter, fallback = registry().resolve("rules-v1")
        assert adapter.model_id == "rules-v1"
        assert fallback is False

    def test_unknown_model_falls_back_to_rules(self):
        adapter, fallback = registry().resolve("missing-model")
        assert adapter.model_id == "rules-v1"
        assert fallback is True

    def test_unhealthy_adapter_falls_back_to_rules(self):
        adapter, fallback = registry().resolve("broken-v1")
        assert adapter.model_id == "rules-v1"
        assert fallback is True


class FailingRanker:
    model_id = "failing-v1"

    def healthy(self) -> bool:
        return True

    def rank(self, request):
        raise ValueError("no usable context for this ranker")


class TestRankingService:
    def test_adapter_exception_falls_back_to_rules(self):
        reg = registry()
        reg.register(FailingRanker())
        response = RankingService(reg).rank(make_request(model_id="failing-v1"))
        assert response.model_id == "rules-v1"
        assert response.fallback_used is True
        assert len(response.candidates) == 1

    def test_response_reports_requested_fallback_and_server_request_id(self):
        service = RankingService(registry())
        first = service.rank(make_request(model_id="missing-model"))
        second = service.rank(make_request(model_id="missing-model"))
        assert first.model_id == "rules-v1"
        assert first.fallback_used is True
        assert first.request_id and first.request_id != second.request_id

    def test_direct_rules_request_is_not_fallback(self):
        response = RankingService(registry()).rank(make_request())
        assert response.fallback_used is False
        assert len(response.candidates) == 1

    def test_rank_fallback_always_returns_rules(self):
        reg = registry()
        reg.register(FailingRanker())
        service = RankingService(reg)
        response = service.rank_fallback(make_request(model_id="failing-v1"))
        assert response.model_id == "rules-v1"
        assert response.fallback_used is True
        assert response.request_id

    def test_model_cards_listed(self):
        cards = RankingService(registry()).model_cards()
        assert any(card["id"] == "rules-v1" for card in cards)
