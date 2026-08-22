"""Route tests for /api/projects/audiotool-session link/unlink."""

from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

FAKE_USER_ID = "test_user_123"

FRAGMENT_A = ObjectId()
FRAGMENT_B = ObjectId()


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

    def update_one(self, query, update):
        result = MagicMock()
        result.modified_count = 0
        for doc in self.docs:
            if self._matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                for key in update.get("$unset", {}):
                    doc.pop(key, None)
                for key, value in update.get("$addToSet", {}).items():
                    doc.setdefault(key, [])
                    if value not in doc[key]:
                        doc[key].append(value)
                for key, value in update.get("$pull", {}).items():
                    doc[key] = [v for v in doc.get(key, []) if v != value]
                result.modified_count = 1
                break
        return result

    def delete_one(self, query):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, query):
                del self.docs[i]
                break

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


@pytest.fixture(autouse=True)
def _reset_db():
    global _stub_db
    _stub_db = StubDB()


@pytest.fixture()
def auth_client():
    import api.deps

    original = api.deps._mongo
    api.deps._mongo = _FakeMongo()
    with patch("api.pipeline.get_genai_client", return_value=MagicMock()):
        from fastapi.testclient import TestClient

        import api.auth
        from api.main import app

        app.dependency_overrides[api.auth.verify_firebase_token] = (
            lambda: FAKE_USER_ID
        )
        yield TestClient(app)
        app.dependency_overrides.clear()
    api.deps._mongo = original


def seed_fragment(oid=FRAGMENT_A, **extra):
    doc = {"_id": oid, "user_id": FAKE_USER_ID, "tags": [], **extra}
    _stub_db["fragments"].docs.append(doc)
    return doc


def link_payload(fragment_id=None):
    return {
        "audiotool_project_id": "at-project-1",
        "display_name": "My Track",
        "fragment_id": fragment_id or str(FRAGMENT_A),
    }


HEADERS = {"Authorization": "Bearer fake"}


def test_link_creates_session_project(auth_client):
    seed_fragment()
    response = auth_client.post(
        "/api/projects/audiotool-session", json=link_payload(), headers=HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Audiotool: My Track"

    project = _stub_db["projects"].docs[0]
    assert project["audiotool_project_id"] == "at-project-1"
    assert project["fragment_ids"] == [str(FRAGMENT_A)]

    # The fragment document stays untouched: stamping project_id would make
    # the capture pipeline's duplicate-group guard reuse this project.
    fragment = _stub_db["fragments"].docs[0]
    assert "project_id" not in fragment
    assert "project_title" not in fragment


def test_link_reuses_existing_session_project(auth_client):
    seed_fragment(FRAGMENT_A)
    seed_fragment(FRAGMENT_B)
    auth_client.post(
        "/api/projects/audiotool-session", json=link_payload(), headers=HEADERS
    )
    response = auth_client.post(
        "/api/projects/audiotool-session",
        json=link_payload(str(FRAGMENT_B)),
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert len(_stub_db["projects"].docs) == 1
    assert _stub_db["projects"].docs[0]["fragment_ids"] == [
        str(FRAGMENT_A),
        str(FRAGMENT_B),
    ]


def test_link_preserves_existing_capture_project(auth_client):
    seed_fragment(project_id="capture-proj", project_title="Rainy sketches")
    response = auth_client.post(
        "/api/projects/audiotool-session", json=link_payload(), headers=HEADERS
    )
    assert response.status_code == 200
    fragment = _stub_db["fragments"].docs[0]
    assert fragment["project_id"] == "capture-proj"
    assert fragment["project_title"] == "Rainy sketches"
    # Still listed under the session project for the Projects view.
    session_project = _stub_db["projects"].docs[0]
    assert session_project["fragment_ids"] == [str(FRAGMENT_A)]


def test_link_missing_fragment_404(auth_client):
    response = auth_client.post(
        "/api/projects/audiotool-session", json=link_payload(), headers=HEADERS
    )
    assert response.status_code == 404


def test_unlink_removes_fragment_and_empty_project(auth_client):
    seed_fragment()
    auth_client.post(
        "/api/projects/audiotool-session", json=link_payload(), headers=HEADERS
    )
    response = auth_client.post(
        "/api/projects/audiotool-session/unlink",
        json={
            "audiotool_project_id": "at-project-1",
            "fragment_id": str(FRAGMENT_A),
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"unlinked": True, "project_deleted": True}
    assert _stub_db["projects"].docs == []


def test_unlink_keeps_project_with_other_fragments(auth_client):
    seed_fragment(FRAGMENT_A)
    seed_fragment(FRAGMENT_B)
    auth_client.post(
        "/api/projects/audiotool-session", json=link_payload(), headers=HEADERS
    )
    auth_client.post(
        "/api/projects/audiotool-session",
        json=link_payload(str(FRAGMENT_B)),
        headers=HEADERS,
    )
    response = auth_client.post(
        "/api/projects/audiotool-session/unlink",
        json={
            "audiotool_project_id": "at-project-1",
            "fragment_id": str(FRAGMENT_A),
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["project_deleted"] is False
    assert _stub_db["projects"].docs[0]["fragment_ids"] == [str(FRAGMENT_B)]


def test_unlink_without_session_project_is_noop(auth_client):
    seed_fragment()
    response = auth_client.post(
        "/api/projects/audiotool-session/unlink",
        json={
            "audiotool_project_id": "never-linked",
            "fragment_id": str(FRAGMENT_A),
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"unlinked": False}
