"""The research export must never leak identity or auth material."""

from ranking.export import export_feedback_rows

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
