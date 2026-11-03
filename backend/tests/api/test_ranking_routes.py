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

    def find_one(self, query, *args, **kwargs):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        doc = self.find_one(query)
        if doc is None and upsert:
            doc = {**query, **update.get("$setOnInsert", {})}
            self.docs.append(doc)
        if doc is not None:
            for path, delta in update.get("$inc", {}).items():
                head, _, tail = path.partition(".")
                target = doc.setdefault(head, {}) if tail else doc
                key = tail or head
                target[key] = target.get(key, 0) + delta
        return doc

    def update_one(self, query, update):
        self.find_one_and_update(query, update)


class StubDB:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = StubCollection()
        return self._collections[name]

    def command(self, name):
        assert name == "ping"
        return {"ok": 1}


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


def test_rank_logs_exposure(auth_client):
    response = auth_client.post(
        "/api/ranking/rank",
        json=rank_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    body = response.json()
    docs = _stub_db["ranking_requests"].docs
    assert len(docs) == 1
    doc = docs[0]
    assert doc["request_id"] == body["request_id"]
    assert doc["user_id"] == FAKE_USER_ID
    assert doc["project_id"] == "p1"
    assert doc["model_id_requested"] == "rules-v1"
    assert doc["model_id_served"] == body["model_id"]
    assert doc["fallback_used"] is False
    assert doc["fragment_ids"] == [c["fragment_id"] for c in body["candidates"]]
    # rules-v1 exposes no signal vector; the slot is still logged per candidate
    assert doc["candidate_signals"] == [None] * len(body["candidates"])
    assert doc["n_candidates_in"] == 1
    assert "created_at" in doc
    # session content and auth material must never be stored
    lowered = {k.lower() for k in doc}
    assert "text_intent" not in lowered
    assert "access_token" not in lowered
    assert "authorization" not in lowered


def test_rank_logs_signal_vectors_for_fusion(auth_client):
    import numpy as np

    def unit(seed):
        v = np.random.default_rng(seed).normal(size=1024)
        return (v / np.linalg.norm(v)).tolist()

    ctx = unit(0)
    payload = rank_payload(model_id="fusion-5sig-v1")
    payload["session"]["region_audio_embeddings"] = [ctx]
    payload["session"]["context_tags"] = ["dark"]
    payload["candidates"] = [
        {
            **payload["candidates"][0],
            "fragment_id": fid,
            "audio_embedding": emb,
            "text_embedding": [0.0],
        }
        for fid, emb in (("same", ctx), ("other", unit(1)))
    ]
    response = auth_client.post(
        "/api/ranking/rank", json=payload, headers={"Authorization": "Bearer fake"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "fusion-5sig-v1" and body["fallback_used"] is False
    assert body["candidates"][0]["fragment_id"] == "same"
    doc = _stub_db["ranking_requests"].docs[0]
    assert doc["candidate_signals"] == [c["signals"] for c in body["candidates"]]
    assert all(len(sig) == 5 for sig in doc["candidate_signals"])
    assert doc["candidate_signals"][0][0] == pytest.approx(1.0)


def test_rank_logs_exposure_on_fallback(auth_client):
    response = auth_client.post(
        "/api/ranking/rank",
        json=rank_payload(model_id="missing-model"),
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    doc = _stub_db["ranking_requests"].docs[0]
    assert doc["model_id_requested"] == "missing-model"
    assert doc["model_id_served"] == "rules-v1"
    assert doc["fallback_used"] is True


def test_rank_succeeds_when_exposure_logging_fails(auth_client):
    class BrokenCollection:
        def insert_one(self, doc):
            raise RuntimeError("mongo down")

    _stub_db._collections["ranking_requests"] = BrokenCollection()
    response = auth_client.post(
        "/api/ranking/rank",
        json=rank_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    assert response.json()["candidates"]


def test_intent_endpoint_returns_parsed_fields(auth_client):
    from ranking.schemas import ParsedIntent

    parsed = ParsedIntent(tags=["dark", "cinematic"], roles=["bass"], bpm=90)
    with patch("api.routes.ranking.parse_intent", return_value=parsed):
        response = auth_client.post(
            "/api/ranking/intent",
            json={"text": "darker, more cinematic, not too heavy"},
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 200
    body = response.json()["parsed"]
    assert body["tags"] == ["dark", "cinematic"]
    assert body["roles"] == ["bass"]
    assert body["bpm"] == 90


def test_intent_endpoint_degrades_to_null_on_failure(auth_client):
    with patch("api.routes.ranking.parse_intent", return_value=None):
        response = auth_client.post(
            "/api/ranking/intent",
            json={"text": "something"},
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 200
    assert response.json()["parsed"] is None


def test_intent_endpoint_requires_auth(anon_client):
    response = anon_client.post("/api/ranking/intent", json={"text": "dark"})
    assert response.status_code in (401, 422)


def test_rank_applies_parsed_intent_without_llm_call(auth_client):
    """parsed_intent tags reach intent_match; no Gemini call on the rank path."""
    payload = rank_payload()
    payload["session"]["text_intent"] = "something moodier"
    payload["session"]["parsed_intent"] = {
        "tags": ["dark", "bass"],
        "roles": [],
        "bpm": None,
        "key": None,
    }
    with patch("ranking.intent._get_genai_client") as get_client:
        response = auth_client.post(
            "/api/ranking/rank",
            json=payload,
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 200
    get_client.assert_not_called()
    evidence = {
        e["code"]: e["contribution"]
        for e in response.json()["candidates"][0]["evidence"]
    }
    # "something moodier" alone matches no tags; the expansion does.
    assert evidence.get("intent_match", 0) > 0


def test_ready_reports_dependencies(anon_client):
    response = anon_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["mongo"] == "ok"
    assert body["clap"] in {"disabled", "loading", "ready"}
    assert "rules-v1" in body["models"]
    assert isinstance(body["fusion_registered"], bool)


class _FakeClap:
    """Stands in for MsClapAdapter: unit vector whose first entry is the RMS."""

    _model = object()

    def encode_audio(self, waveform, sample_rate):
        import numpy as np

        vector = np.zeros(1024)
        vector[0] = float(np.sqrt(np.mean(np.square(waveform)))) + 1e-6
        return vector / np.linalg.norm(vector)


def _wav_bytes(seconds=1.0, freq=220.0, sr=22050, stereo=False):
    import io

    import numpy as np
    import soundfile

    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * freq * t)).astype("float32")
    data = np.stack([mono, mono], axis=1) if stereo else mono
    buf = io.BytesIO()
    soundfile.write(buf, data, sr, format="WAV")
    return buf.getvalue()


def test_session_embed_returns_embeddings_chroma_and_failures(auth_client, monkeypatch):
    from ranking.adapters import shared

    monkeypatch.setenv("POCKET_ENABLE_CLAP", "1")
    shared.reset_for_tests(_FakeClap())
    response = auth_client.post(
        "/api/ranking/session-embed",
        files=[
            ("files", ("a.wav", _wav_bytes(), "audio/wav")),
            ("files", ("b.wav", _wav_bytes(stereo=True), "audio/wav")),
            ("files", ("bad.wav", b"not audio at all", "audio/wav")),
        ],
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3 and body["encoded"] == 2
    assert len(body["embeddings"]) == 2 and all(len(e) == 1024 for e in body["embeddings"])
    assert len(body["chroma"]) == 2 and all(len(c) == 12 for c in body["chroma"])
    # a 220 Hz tone is an A: pitch class 9 should dominate the chroma profile
    assert max(range(12), key=lambda i: body["chroma"][0][i]) == 9
    assert body["failed"] == [{"file": "bad.wav", "reason": body["failed"][0]["reason"]}]
    assert body["timed_out"] is False
    shared.reset_for_tests(None)


def test_session_embed_is_503_when_clap_disabled(auth_client, monkeypatch):
    from ranking.adapters import shared

    monkeypatch.delenv("POCKET_ENABLE_CLAP", raising=False)
    shared.reset_for_tests(None)
    response = auth_client.post(
        "/api/ranking/session-embed",
        files=[("files", ("a.wav", _wav_bytes(), "audio/wav"))],
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 503


def test_feedback_marks_orphan_when_no_exposure(auth_client):
    payload = {
        "request_id": "orphan-req",
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
    doc = _stub_db["ranking_feedback"].docs[0]
    assert doc["exposure_verified"] is False


def test_feedback_marks_verified_when_exposure_exists(auth_client):
    auth_client.post(
        "/api/ranking/rank",
        json=rank_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    request_id = _stub_db["ranking_requests"].docs[0]["request_id"]
    payload = {
        "request_id": request_id,
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
    doc = _stub_db["ranking_feedback"].docs[0]
    assert doc["exposure_verified"] is True


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
