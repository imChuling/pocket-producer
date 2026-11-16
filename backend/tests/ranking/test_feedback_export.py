"""The research export must never leak identity or auth material."""

import pytest

from ranking.research.export import export_feedback_rows, export_request_rows

RAW_DOCS = [
    {
        "_id": "abc",
        "user_id": "firebase-uid-123",
        "request_id": "req-1",
        "project_id": "p1",
        "project_title": "My secret song",
        "fragment_id": "f1",
        "event": "insert",
        "rank_position": 1,
        "model_id": "rules-v1",
        "created_at": "2026-07-30T12:00:00Z",
        "email": "someone@example.com",
        "access_token": "oops-token",
        "Authorization": "Bearer oops",
    }
]


def test_export_strips_identity_and_auth_fields():
    rows = export_feedback_rows(RAW_DOCS, salt="test-salt")
    assert len(rows) == 1
    row = rows[0]
    lowered = {k.lower() for k in row}
    assert "email" not in lowered
    assert "access_token" not in lowered
    assert "authorization" not in lowered
    assert "project_title" not in lowered
    assert "user_id" not in lowered
    assert "_id" not in lowered


def test_export_hashes_participant_one_way_and_stably():
    first = export_feedback_rows(RAW_DOCS, salt="test-salt")[0]
    second = export_feedback_rows(RAW_DOCS, salt="test-salt")[0]
    assert first["participant_hash"] == second["participant_hash"]
    assert "firebase-uid-123" not in first["participant_hash"]
    different_salt = export_feedback_rows(RAW_DOCS, salt="other")[0]
    assert different_salt["participant_hash"] != first["participant_hash"]


def test_export_keeps_research_fields():
    row = export_feedback_rows(RAW_DOCS, salt="test-salt")[0]
    assert row["event"] == "insert"
    assert row["rank_position"] == 1
    assert row["model_id"] == "rules-v1"
    assert row["request_id"] == "req-1"
    assert row["fragment_id"] == "f1"
    assert row["created_at"] == "2026-07-30T12:00:00Z"


def test_export_requires_a_salt():
    with pytest.raises(ValueError):
        export_feedback_rows(RAW_DOCS, salt="")


REQUEST_DOC = {
    "_id": "def",
    "request_id": "req-1",
    "user_id": "firebase-uid-123",
    "project_id": "p1",
    "model_id_requested": "fusion-5sig-v1",
    "model_id_served": "fusion-5sig-v1",
    "fallback_used": False,
    "fragment_ids": ["f1", "f2"],
    "candidate_signals": [[0.1] * 5, [0.2] * 5],
    "candidate_signal_names": ["a", "b", "c", "d", "e"],
    "candidate_signal_available": [None, None],
    "n_candidates_in": 2,
    "created_at": "2026-07-30T12:00:00Z",
    "text_intent": "dark bass",
    "email": "someone@example.com",
}


def test_request_export_keeps_what_the_analyses_read_and_hashes_the_user():
    row = export_request_rows([REQUEST_DOC], salt="test-salt")[0]
    assert "user_id" not in row and "_id" not in row
    assert "text_intent" not in row and "email" not in row
    assert row["participant_hash"] == export_feedback_rows(RAW_DOCS, salt="test-salt")[0][
        "participant_hash"
    ]
    for key in ("request_id", "model_id_served", "fragment_ids", "candidate_signals",
                "candidate_signal_names", "candidate_signal_available"):
        assert row[key] == REQUEST_DOC[key]
