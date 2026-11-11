"""Route tests for the unauthenticated /api/demo endpoints."""

import io
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from api.routes.demo import DEMO_USER_ID, MAX_FRAGMENTS

AUDIO_BYTES = b"0123456789" * 10


class StubCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class StubCollection:
    def __init__(self):
        self.docs = []

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

    @staticmethod
    def _project(doc, projection):
        if not projection:
            return dict(doc)
        if all(v == 0 for v in projection.values()):
            return {k: v for k, v in doc.items() if k not in projection}
        return {k: v for k, v in doc.items() if k == "_id" or k in projection}

    def find(self, query, projection=None):
        return StubCursor(
            [self._project(d, projection) for d in self.docs if self._matches(d, query)]
        )

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._matches(doc, query):
                return self._project(doc, projection)
        return None


class StubDB:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        return self._collections.setdefault(name, StubCollection())


class _FakeBlob:
    size = len(AUDIO_BYTES)

    def reload(self):
        pass

    def open(self, mode):
        return io.BytesIO(AUDIO_BYTES)


@pytest.fixture()
def db():
    return StubDB()


@pytest.fixture()
def client(db):
    import api.deps

    class _FakeMongo:
        def __getitem__(self, name):
            return db

    gcs = MagicMock()
    gcs.bucket.return_value.blob.return_value = _FakeBlob()

    original = api.deps._mongo
    api.deps._mongo = _FakeMongo()
    with (
        patch("api.pipeline.get_genai_client", return_value=MagicMock()),
        patch("api._clients.get_gcs_client", return_value=gcs),
    ):
        from fastapi.testclient import TestClient

        from api.main import app

        yield TestClient(app)
    api.deps._mongo = original


def add_fragment(db, user_id=DEMO_USER_ID, **extra):
    doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "type": "audio",
        "title": "loop",
        "audio_url": "gs://bucket/demo/loop.mp3",
        "pipeline_step": "done",
        "embedding": [0.1],
        "representations": {"chroma": {}},
        "emotions": ["calm"],
        "themes": ["night"],
        "style": ["lo-fi"],
        "created_at": datetime(2026, 11, 1, tzinfo=UTC),
        **extra,
    }
    db["fragments"].docs.append(doc)
    return doc


def add_project(db, fragments, user_id=DEMO_USER_ID):
    doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "title": "Late Night Feels",
        "fragment_ids": [str(f["_id"]) for f in fragments],
    }
    db["projects"].docs.append(doc)
    return doc


def test_fragments_serve_only_the_seed_account_without_auth(client, db):
    add_fragment(db, title="seeded")
    add_fragment(db, user_id="real-user", title="private")

    res = client.get("/api/demo/fragments")

    assert res.status_code == 200
    assert [f["title"] for f in res.json()["fragments"]] == ["seeded"]


def test_fragments_omit_storage_paths_and_vectors(client, db):
    add_fragment(db)

    fragment = client.get("/api/demo/fragments").json()["fragments"][0]

    for field in ("audio_url", "pipeline_step", "embedding", "representations"):
        assert field not in fragment


def test_fragments_limit_is_capped(client, db):
    for _ in range(MAX_FRAGMENTS + 5):
        add_fragment(db)

    res = client.get("/api/demo/fragments?limit=100000")

    assert len(res.json()["fragments"]) == MAX_FRAGMENTS


def test_audio_streams_a_seed_fragment_without_auth(client, db):
    fragment = add_fragment(db)

    res = client.get(f"/api/demo/fragments/{fragment['_id']}/audio")

    assert res.status_code == 200
    assert res.content == AUDIO_BYTES
    assert res.headers["content-type"] == "audio/mpeg"


def test_audio_honours_range_requests(client, db):
    fragment = add_fragment(db)

    res = client.get(
        f"/api/demo/fragments/{fragment['_id']}/audio", headers={"Range": "bytes=10-19"}
    )

    assert res.status_code == 206
    assert res.content == AUDIO_BYTES[10:20]


def test_audio_refuses_fragments_outside_the_seed_account(client, db):
    private = add_fragment(db, user_id="real-user")

    res = client.get(f"/api/demo/fragments/{private['_id']}/audio")

    assert res.status_code == 404


def test_audio_rejects_a_malformed_id(client):
    assert client.get("/api/demo/fragments/not-an-id/audio").status_code == 400


def test_project_detail_returns_its_fragments_in_order(client, db):
    first = add_fragment(db, title="first")
    second = add_fragment(db, title="second")
    project = add_project(db, [second, first])

    res = client.get(f"/api/demo/projects/{project['_id']}")

    assert res.status_code == 200
    body = res.json()
    assert [f["title"] for f in body["fragments"]] == ["second", "first"]
    assert "audio_url" not in body["fragments"][0]


def test_project_detail_hides_projects_outside_the_seed_account(client, db):
    project = add_project(db, [add_fragment(db, user_id="real-user")], user_id="real-user")

    assert client.get(f"/api/demo/projects/{project['_id']}").status_code == 404


def test_project_detail_rejects_a_malformed_id(client):
    assert client.get("/api/demo/projects/not-an-id").status_code == 400


def test_dna_counts_seed_fragments_and_invents_no_capture_rhythm(client, db):
    add_fragment(db, project_id="p1")
    add_fragment(db, emotions=["calm", "bright"])
    add_fragment(db, user_id="real-user", emotions=["angry"])

    body = client.get("/api/demo/dna").json()

    assert body["total_fragments"] == 2
    assert body["total_projects"] == 1
    assert body["emotions"] == {"calm": 2, "bright": 1}
    assert body["hourly_distribution"] == {}
    assert "peak_hours" not in body
