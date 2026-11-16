"""The feedback export script writes only allowlisted fields, in a form the analyses read."""

import json
from datetime import UTC, datetime

import pytest

from ranking.fusion_ranker import SIGNAL_NAMES
from ranking.research.export import FEEDBACK_FIELDS, REQUEST_FIELDS
from ranking.research.feedback_pairs import build_feedback_pairs
from scripts.export_feedback import export

WHEN = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.projections = []

    def find(self, query, projection):
        # Returns whole documents on purpose: the allowlist must hold even
        # if the database ignored the projection.
        self.projections.append(projection)
        return iter(self.docs)


def fake_db():
    requests = [
        {
            "_id": "oid-1",
            "request_id": "req-1",
            "user_id": "firebase-uid-123",
            "project_id": "p1",
            "model_id_requested": "fusion-5sig-v1",
            "model_id_served": "fusion-5sig-v1",
            "fallback_used": False,
            "fragment_ids": ["good", "bad"],
            "candidate_signals": [[0.9] * 5, [0.1] * 5],
            "candidate_signal_names": list(SIGNAL_NAMES),
            "candidate_signal_available": [None, None],
            "n_candidates_in": 2,
            "created_at": WHEN,
            "text_intent": "my secret song idea",
        }
    ]
    feedback = [
        {
            "_id": f"oid-{i}",
            "user_id": "firebase-uid-123",
            "request_id": "req-1",
            "project_id": "p1",
            "fragment_id": fid,
            "event": event,
            "rank_position": rank,
            "model_id": "fusion-5sig-v1",
            "exposure_verified": True,
            "created_at": WHEN,
            "email": "someone@example.com",
        }
        for i, (fid, event, rank) in enumerate((("good", "insert", 1), ("bad", "reject", 2)))
    ]
    return {
        "ranking_requests": FakeCollection(requests),
        "ranking_feedback": FakeCollection(feedback),
    }


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_export_writes_no_identity_and_feeds_the_pair_builder(tmp_path):
    db = fake_db()
    requests_path, feedback_path = export(db, tmp_path, salt="test-salt")
    requests, feedback = read_jsonl(requests_path), read_jsonl(feedback_path)

    text = requests_path.read_text() + feedback_path.read_text()
    for secret in ("firebase-uid-123", "my secret song idea", "someone@example.com", "oid-"):
        assert secret not in text
    assert set(requests[0]) <= set(REQUEST_FIELDS) | {"participant_hash"}
    assert all(set(row) <= set(FEEDBACK_FIELDS) | {"participant_hash"} for row in feedback)
    assert requests[0]["created_at"] == WHEN.isoformat()

    pairs = build_feedback_pairs(requests, feedback)
    assert [(p["positive"], p["negative"]) for p in pairs] == [("good", "bad")]


def test_export_asks_the_database_only_for_allowlisted_fields(tmp_path):
    db = fake_db()
    export(db, tmp_path, salt="test-salt")
    expected = (("ranking_requests", REQUEST_FIELDS), ("ranking_feedback", FEEDBACK_FIELDS))
    for name, fields in expected:
        (projection,) = db[name].projections
        assert {k for k, v in projection.items() if v} == set(fields) | {"user_id"}
        assert projection["_id"] == 0


def test_export_refuses_without_a_salt(tmp_path):
    with pytest.raises(ValueError):
        export(fake_db(), tmp_path, salt="")
    assert not list(tmp_path.iterdir())
