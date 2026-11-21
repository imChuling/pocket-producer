"""Route tests for /api/projects/audiotool-session link/unlink."""

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

FAKE_USER_ID = "test_user_123"

FRAGMENT_A = ObjectId()
FRAGMENT_B = ObjectId()


class StubCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        doc.setdefault("_id", ObjectId())
        if any(existing["_id"] == doc["_id"] for existing in self.docs):
            raise DuplicateKeyError("duplicate _id")
        self.docs.append(deepcopy(doc))
        result = MagicMock()
        result.inserted_id = doc["_id"]
        return result

    def find_one(self, query, projection=None, sort=None):
        for doc in self.docs:
            if self._matches(doc, query):
                return deepcopy(doc)
        return None

    def find(self, query, projection=None):
        return [doc for doc in self.docs if self._matches(doc, query)]

    def update_one(self, query, update):
        result = MagicMock()
        result.matched_count = result.modified_count = 0
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
                    if key in doc:
                        doc[key] = [v for v in doc[key] if not (
                            self._matches(v, value) if isinstance(value, dict) else v == value
                        )]
                result.matched_count = result.modified_count = 1
                break
        return result

    def delete_one(self, query):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, query):
                del self.docs[i]
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    def update_many(self, query, update):
        ids = [doc["_id"] for doc in self.docs if self._matches(doc, query)]
        for oid in ids:
            self.update_one({"_id": oid}, update)
        return MagicMock(modified_count=len(ids))

    def delete_many(self, query):
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]

    @staticmethod
    def _matches(doc, query):
        for key, expected in query.items():
            value = doc.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if value not in expected["$in"]:
                    return False
            elif isinstance(expected, dict) and "$size" in expected:
                if not isinstance(value, list) or len(value) != expected["$size"]:
                    return False
            elif isinstance(value, list) and not isinstance(expected, list):
                if expected not in value:
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


def test_undo_targets_one_placement_and_retries_are_idempotent(auth_client):
    seed_fragment()
    link = "/api/projects/audiotool-session"
    first = {**link_payload(), "insertion_id": "region-1"}
    second = {**link_payload(), "insertion_id": "region-2"}
    for payload in (first, second, second):
        assert auth_client.post(link, json=payload, headers=HEADERS).is_success

    assert auth_client.post(link + "/unlink", json=second, headers=HEADERS).json() == {
        "unlinked": True, "project_deleted": False,
    }
    assert auth_client.post(link + "/unlink", json=second, headers=HEADERS).json() == {
        "unlinked": False,
    }
    assert _stub_db["projects"].docs[0]["fragment_ids"] == [str(FRAGMENT_A)]
    assert auth_client.post(link + "/unlink", json=first, headers=HEADERS).json() == {
        "unlinked": True, "project_deleted": True,
    }


def test_named_placement_preserves_legacy_membership(auth_client):
    seed_fragment()
    _stub_db["projects"].insert_one({
        "user_id": FAKE_USER_ID, "audiotool_project_id": "at-project-1",
        "fragment_ids": [str(FRAGMENT_A)], "title": "Legacy session",
    })
    link = "/api/projects/audiotool-session"
    named = {**link_payload(), "insertion_id": "region-new"}
    auth_client.post(link, json=named, headers=HEADERS).raise_for_status()
    assert auth_client.post(link + "/unlink", json=named, headers=HEADERS).json() == {
        "unlinked": True, "project_deleted": False,
    }
    assert auth_client.post(link + "/unlink", json=link_payload(), headers=HEADERS).json() == {
        "unlinked": True, "project_deleted": True,
    }


def test_concurrent_first_links_share_one_project(auth_client, monkeypatch):
    from api.routes.projects import AudiotoolLinkRequest, _link_audiotool_sync

    seed_fragment(FRAGMENT_A)
    seed_fragment(FRAGMENT_B)
    projects = _stub_db["projects"]
    insert = projects.insert_one

    def interleaved_create(doc):
        monkeypatch.setattr(projects, "insert_one", insert)
        other = AudiotoolLinkRequest(**link_payload(str(FRAGMENT_B)), insertion_id="b")
        _link_audiotool_sync(_stub_db, FAKE_USER_ID, other)
        return insert(doc)

    monkeypatch.setattr(projects, "insert_one", interleaved_create)
    response = auth_client.post(
        "/api/projects/audiotool-session", json={**link_payload(), "insertion_id": "a"},
        headers=HEADERS,
    )
    response.raise_for_status()
    assert len(projects.docs) == 1
    assert set(projects.docs[0]["fragment_ids"]) == {str(FRAGMENT_A), str(FRAGMENT_B)}


def test_last_unlink_racing_another_link_preserves_the_new_placement(auth_client, monkeypatch):
    from api.routes.projects import AudiotoolLinkRequest, _link_audiotool_sync

    seed_fragment(FRAGMENT_A)
    seed_fragment(FRAGMENT_B)
    url = "/api/projects/audiotool-session"
    payload = {**link_payload(), "insertion_id": "a"}
    auth_client.post(url, json=payload, headers=HEADERS).raise_for_status()
    projects = _stub_db["projects"]
    delete = projects.delete_one

    def interleaved_delete(query):
        monkeypatch.setattr(projects, "delete_one", delete)
        other = AudiotoolLinkRequest(**link_payload(str(FRAGMENT_B)), insertion_id="b")
        _link_audiotool_sync(_stub_db, FAKE_USER_ID, other)
        return delete(query)

    monkeypatch.setattr(projects, "delete_one", interleaved_delete)
    result = auth_client.post(url + "/unlink", json=payload, headers=HEADERS)
    assert result.json() == {"unlinked": True, "project_deleted": False}
    assert projects.docs[0]["fragment_ids"] == [str(FRAGMENT_B)]



def test_fragment_deletion_cleans_its_placements_and_preserves_other_members(auth_client):
    seed_fragment(FRAGMENT_A)
    a, b = str(FRAGMENT_A), str(FRAGMENT_B)
    other = {"fragment_id": b, "insertion_id": "region-b"}
    _stub_db["projects"].insert_one({
        "user_id": FAKE_USER_ID, "audiotool_project_id": "session", "fragment_ids": [a, b],
        "audiotool_insertions": [{"fragment_id": a, "insertion_id": "region-a"}, other],
    })
    unrelated = _stub_db["projects"].insert_one({
        "user_id": FAKE_USER_ID, "fragment_ids": [], "sections": ["draft arrangement"],
    })
    auth_client.post(f"/api/fragments/{a}/delete", headers=HEADERS).raise_for_status()
    assert _stub_db["projects"].find_one({"_id": unrelated.inserted_id}) is not None
    project = _stub_db["projects"].docs[0]
    assert project["fragment_ids"] == [b]
    assert project["audiotool_insertions"] == [other]


def test_concurrent_fragment_deletion_does_not_leave_a_dangling_mirror(auth_client, monkeypatch):
    seed_fragment()
    projects = _stub_db["projects"]
    insert = projects.insert_one

    def delete_fragment_before_create(doc):
        _stub_db["fragments"].delete_one({"_id": FRAGMENT_A})
        return insert(doc)

    monkeypatch.setattr(projects, "insert_one", delete_fragment_before_create)
    response = auth_client.post(
        "/api/projects/audiotool-session", json={**link_payload(), "insertion_id": "region-a"},
        headers=HEADERS,
    )
    assert response.status_code == 404
    assert projects.docs == []
