"""The routes record what the user changed by hand, bounded per document."""

from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

USER = "u1"


class Recorder:
    def __init__(self, doc):
        self.doc = doc
        self.updates = []

    def find_one(self, query, projection=None):
        return dict(self.doc) if query.get("_id") == self.doc["_id"] else None

    def update_one(self, query, update):
        self.updates.append(update)
        return MagicMock(matched_count=1)


class DB:
    def __init__(self, **collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections.setdefault(name, Recorder({"_id": None}))


@pytest.fixture()
def client_for():
    import api.auth
    import api.deps

    original = api.deps._mongo

    def make(db):
        class Mongo:
            def __getitem__(self, name):
                return db

        api.deps._mongo = Mongo()
        from fastapi.testclient import TestClient

        from api.main import app

        app.dependency_overrides[api.auth.verify_firebase_token] = lambda: USER
        return TestClient(app)

    with patch("api.pipeline.get_genai_client", return_value=MagicMock()):
        yield make
    from api.main import app

    app.dependency_overrides.clear()
    api.deps._mongo = original


def test_title_edit_keeps_the_title_it_replaced(client_for):
    doc = {"_id": ObjectId(), "user_id": USER, "title": "Rainy Piano"}
    fragments = Recorder(doc)
    client = client_for(DB(fragments=fragments))
    res = client.post(f"/api/fragments/{doc['_id']}/title", data={"title": "rain at 3am"})
    assert res.status_code == 200
    (update,) = fragments.updates
    pushed = update["$push"]["title_history"]
    assert pushed["$each"][0]["from"] == "Rainy Piano" and pushed["$each"][0]["to"] == "rain at 3am"
    assert pushed["$slice"] < 0


def test_unchanged_title_records_nothing(client_for):
    doc = {"_id": ObjectId(), "user_id": USER, "title": "Same"}
    fragments = Recorder(doc)
    client_for(DB(fragments=fragments)).post(
        f"/api/fragments/{doc['_id']}/title", data={"title": "Same"}
    )
    assert "$push" not in fragments.updates[0]


def test_tag_edit_records_what_was_added_and_removed(client_for):
    doc = {"_id": ObjectId(), "user_id": USER, "tags": ["melody", "piano"], "emotions": ["calm"]}
    fragments = Recorder(doc)
    client = client_for(DB(fragments=fragments))
    res = client.post(
        f"/api/fragments/{doc['_id']}/tags",
        json={"tags": ["piano", "lofi"], "emotions": ["calm"]},
    )
    assert res.status_code == 200
    (update,) = fragments.updates
    (edit,) = update["$push"]["tag_edits"]["$each"]
    assert (edit["field"], edit["added"], edit["removed"]) == ("tags", ["lofi"], ["melody"])


def test_skipped_suggestion_is_recorded_before_a_new_one_is_made(client_for):
    project = {"_id": ObjectId(), "user_id": USER, "next_action": {"action": "Write a bridge"}}
    projects = Recorder(project)

    async def new_action(db, user_id, project_id):
        return {"action": "Record a bass line"}

    with patch("api.pipeline._generate_next_action", new_action):
        res = client_for(DB(projects=projects)).post(f"/api/projects/{project['_id']}/skip-action")
    assert res.status_code == 200
    skipped = projects.updates[0]["$push"]["skipped_actions"]["$each"][0]
    assert skipped["action"] == {"action": "Write a bridge"}
    assert projects.updates[1]["$set"]["next_action"] == {"action": "Record a bass line"}
