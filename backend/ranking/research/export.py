"""Research export for feedback events.

Allowlist-based on purpose: only fields named here can ever leave the
database, so newly added document fields stay private by default.
"""

import hashlib

_ALLOWED_FIELDS = (
    "request_id",
    "project_id",
    "fragment_id",
    "event",
    "rank_position",
    "model_id",
    "created_at",
)


def _hash_participant(user_id: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()
    return f"p_{digest[:16]}"


def export_feedback_rows(docs: list[dict], salt: str) -> list[dict]:
    rows = []
    for doc in docs:
        row = {key: doc[key] for key in _ALLOWED_FIELDS if key in doc}
        user_id = doc.get("user_id")
        if user_id:
            row["participant_hash"] = _hash_participant(str(user_id), salt)
        rows.append(row)
    return rows
