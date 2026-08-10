"""Blind pairwise annotation routes: serve next pair, record label."""

from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

FAKE_USER_ID = "test_user_123"

PAIR_ID = ObjectId()
FRAGMENT_LEFT = ObjectId()
FRAGMENT_RIGHT = ObjectId()
CONTEXT_FRAGMENT = ObjectId()


class StubCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        doc.setdefault("_id", ObjectId())
        self.docs.append(doc)
        result = MagicMock()
        result.inserted_id = doc["_id"]
        return result

    def find_one(self, query, projection=None, sort=None):
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    def find(self, query, projection=None):
        return [doc for doc in self.docs if self._matches(doc, query)]

    def count_documents(self, query):
        return len(self.find(query))

    def update_one(self, query, update):
        result = MagicMock()
        result.modified_count = 0
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                result.modified_count = 1
                break
        return result

    @staticmethod
    def _matches(doc, query):
        for key, expected in query.items():
            value = doc.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if value not in expected["$in"]:
                    return False
            elif value != expected:
                return False
        return True


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


def seed_pair(status="pending"):
    _stub_db["annotation_pairs"].insert_one(
        {
            "_id": PAIR_ID,
            "user_id": FAKE_USER_ID,
            "context_project_id": "proj1",
            "context_fragment_ids": [str(CONTEXT_FRAGMENT)],
            "left_fragment_id": str(FRAGMENT_LEFT),
            "right_fragment_id": str(FRAGMENT_RIGHT),
            "status": status,
        }
    )
    for fragment_id, title in [
        (FRAGMENT_LEFT, "Left idea"),
        (FRAGMENT_RIGHT, "Right idea"),
        (CONTEXT_FRAGMENT, "Context loop"),
    ]:
        _stub_db["fragments"].insert_one(
            {"_id": fragment_id, "user_id": FAKE_USER_ID, "title": title}
        )


@pytest.fixture(autouse=True)
def _reset_db():
    global _stub_db
    _stub_db = StubDB()


@pytest.fixture()
def auth_client():
    import api.auth
    import api.deps

    original = api.deps._mongo
    api.deps._mongo = _FakeMongo()
    with patch("api.pipeline.get_genai_client", return_value=MagicMock()):
        from fastapi.testclient import TestClient

        from api.main import app

        app.dependency_overrides[api.auth.verify_firebase_token] = (
            lambda: FAKE_USER_ID
        )
        yield TestClient(app)
        app.dependency_overrides.clear()
    api.deps._mongo = original


AUTH = {"Authorization": "Bearer fake"}


def label_payload(**overrides):
    base = {
        "choice": "left",
        "reason_codes": ["tempo_fit"],
        "confidence": 4,
    }
    base.update(overrides)
    return base


def test_next_pair_requires_auth():
    import api.deps

    original = api.deps._mongo
    api.deps._mongo = _FakeMongo()
    with patch("api.pipeline.get_genai_client", return_value=MagicMock()):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        response = client.get("/api/ranking/pairs/next")
        assert response.status_code in (401, 422)
    api.deps._mongo = original


def test_next_returns_pending_pair_with_titles(auth_client):
    seed_pair()
    response = auth_client.get("/api/ranking/pairs/next", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["done"] is False
    assert body["pair"]["left"]["title"] == "Left idea"
    assert body["pair"]["right"]["title"] == "Right idea"
    assert body["pair"]["context"][0]["title"] == "Context loop"
    assert body["remaining"] == 1
    # blind: no model ids anywhere in the payload
    assert "model" not in str(body).lower()


def test_next_reports_done_when_no_pending_pairs(auth_client):
    response = auth_client.get("/api/ranking/pairs/next", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["done"] is True


def test_label_persists_and_marks_pair_labeled(auth_client):
    seed_pair()
    response = auth_client.post(
        f"/api/ranking/pairs/{PAIR_ID}/label",
        json=label_payload(),
        headers=AUTH,
    )
    assert response.status_code == 200
    labels = _stub_db["annotation_labels"].docs
    assert len(labels) == 1
    assert labels[0]["choice"] == "left"
    assert labels[0]["models_hidden"] is True
    assert labels[0]["user_id"] == FAKE_USER_ID
    pair = _stub_db["annotation_pairs"].docs[0]
    assert pair["status"] == "labeled"


def test_label_rejects_already_labeled_pair(auth_client):
    seed_pair(status="labeled")
    response = auth_client.post(
        f"/api/ranking/pairs/{PAIR_ID}/label",
        json=label_payload(),
        headers=AUTH,
    )
    assert response.status_code == 409


def test_label_rejects_invalid_choice(auth_client):
    seed_pair()
    response = auth_client.post(
        f"/api/ranking/pairs/{PAIR_ID}/label",
        json=label_payload(choice="both"),
        headers=AUTH,
    )
    assert response.status_code == 422


def test_label_rejects_unknown_reason_code(auth_client):
    seed_pair()
    response = auth_client.post(
        f"/api/ranking/pairs/{PAIR_ID}/label",
        json=label_payload(reason_codes=["sounds_expensive"]),
        headers=AUTH,
    )
    assert response.status_code == 422


def test_label_of_foreign_pair_is_not_found(auth_client):
    _stub_db["annotation_pairs"].insert_one(
        {
            "_id": PAIR_ID,
            "user_id": "someone-else",
            "status": "pending",
            "left_fragment_id": str(FRAGMENT_LEFT),
            "right_fragment_id": str(FRAGMENT_RIGHT),
            "context_fragment_ids": [],
            "context_project_id": "p",
        }
    )
    response = auth_client.post(
        f"/api/ranking/pairs/{PAIR_ID}/label",
        json=label_payload(),
        headers=AUTH,
    )
    assert response.status_code == 404
