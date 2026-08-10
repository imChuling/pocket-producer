"""Route tests for /api/ranking endpoints: auth, fallback, feedback storage."""

import time
from unittest.mock import MagicMock, patch

import pytest

FAKE_USER_ID = "test_user_123"


class StubCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)
        result = MagicMock()
        result.inserted_id = "stub-id"
        return result


class StubDB:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = StubCollection()
        return self._collections[name]


_stub_db = StubDB()


class _FakeMongo:
    def __getitem__(self, name):
        return _stub_db


@pytest.fixture(autouse=True)
def _reset_db():
    global _stub_db
    _stub_db = StubDB()


@pytest.fixture()
def anon_client():
    import api.deps

    original = api.deps._mongo
    api.deps._mongo = _FakeMongo()
    with patch("api.pipeline.get_genai_client", return_value=MagicMock()):
        from fastapi.testclient import TestClient

        from api.main import app

        yield TestClient(app)
        app.dependency_overrides.clear()
    api.deps._mongo = original


@pytest.fixture()
def auth_client(anon_client):
    import api.auth
    from api.main import app

    app.dependency_overrides[api.auth.verify_firebase_token] = lambda: FAKE_USER_ID
    yield anon_client
    app.dependency_overrides.clear()


def rank_payload(model_id: str = "rules-v1") -> dict:
    return {
        "session": {
            "project_id": "p1",
            "bpm": 120,
            "key": "A minor",
            "playhead_seconds": 10,
            "track_count": 2,
            "active_track_types": ["drums"],
            "recent_entity_ids": [],
            "text_intent": "dark bass",
        },
        "candidates": [
            {
                "fragment_id": "f1",
                "duration_seconds": 8,
                "bpm": 121,
                "key": "A minor",
                "tags": ["dark", "bass"],
                "created_at_iso": "2026-07-01T00:00:00Z",
                "audio_url": "/api/fragments/f1/audio",
            }
        ],
        "model_id": model_id,
        "limit": 3,
    }


def test_rank_requires_authenticated_user(anon_client):
    response = anon_client.post("/api/ranking/rank", json=rank_payload())
    assert response.status_code in (401, 422)  # missing header rejected


def test_rank_rejects_invalid_token(anon_client):
    response = anon_client.post(
        "/api/ranking/rank",
        json=rank_payload(),
        headers={"Authorization": "NotBearer x"},
    )
    assert response.status_code == 401


def test_rank_returns_scored_candidates(auth_client):
    response = auth_client.post(
        "/api/ranking/rank",
        json=rank_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "rules-v1"
    assert body["fallback_used"] is False
    assert body["candidates"][0]["fragment_id"] == "f1"
    assert body["candidates"][0]["evidence"]


def test_unknown_model_falls_back_to_rules(auth_client):
    response = auth_client.post(
        "/api/ranking/rank",
        json=rank_payload(model_id="missing-model"),
        headers={"Authorization": "Bearer fake"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["model_id"] == "rules-v1"
    assert body["fallback_used"] is True


def test_model_card_endpoint_lists_adapters(auth_client):
    response = auth_client.get(
        "/api/ranking/model-card", headers={"Authorization": "Bearer fake"}
    )
    assert response.status_code == 200
    assert any(m["id"] == "rules-v1" for m in response.json()["models"])


def test_feedback_persists_server_side_user_id(auth_client):
    payload = {
        "request_id": "req-1",
        "project_id": "p1",
        "fragment_id": "f1",
        "event": "insert",
        "rank_position": 1,
        "model_id": "rules-v1",
    }
    response = auth_client.post(
        "/api/ranking/feedback",
        json=payload,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    docs = _stub_db["ranking_feedback"].docs
    assert len(docs) == 1
    doc = docs[0]
    assert doc["user_id"] == FAKE_USER_ID
    assert doc["event"] == "insert"
    assert doc["rank_position"] == 1
    assert "created_at" in doc
    # OAuth material must never be stored
    assert "access_token" not in doc and "authorization" not in {
        k.lower() for k in doc
    }


def test_slow_adapter_triggers_timeout_fallback(auth_client):
    """A ranker that exceeds RANK_TIMEOUT_SECONDS falls back to rules-v1."""
    from ranking.baselines import RulesRanker
    from ranking.registry import RankerRegistry
    from ranking.service import RankingService

    class SlowRanker:
        model_id = "slow-v1"

        def healthy(self):
            return True

        def rank(self, request):
            time.sleep(3)
            raise AssertionError("should have timed out before reaching here")

    reg = RankerRegistry()
    reg.register(RulesRanker())
    reg.register(SlowRanker())
    slow_service = RankingService(reg)

    import api.routes.ranking as ranking_mod

    original_service = ranking_mod._service
    original_timeout = ranking_mod.RANK_TIMEOUT_SECONDS
    ranking_mod._service = slow_service
    ranking_mod.RANK_TIMEOUT_SECONDS = 0.5
    try:
        response = auth_client.post(
            "/api/ranking/rank",
            json=rank_payload(model_id="slow-v1"),
            headers={"Authorization": "Bearer fake"},
        )
        body = response.json()
        assert response.status_code == 200
        assert body["model_id"] == "rules-v1"
        assert body["fallback_used"] is True
    finally:
        ranking_mod._service = original_service
        ranking_mod.RANK_TIMEOUT_SECONDS = original_timeout


def test_feedback_ignores_user_id_in_body(auth_client):
    payload = {
        "request_id": "req-2",
        "project_id": "p1",
        "fragment_id": "f1",
        "event": "undo",
        "rank_position": 2,
        "model_id": "rules-v1",
        "user_id": "attacker-user",
    }
    response = auth_client.post(
        "/api/ranking/feedback",
        json=payload,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    assert _stub_db["ranking_feedback"].docs[0]["user_id"] == FAKE_USER_ID
