"""Research export for the proposal log and feedback events.

Allowlist-based on purpose: only fields named here can ever leave the
database, so newly added document fields stay private by default. The user
ID is replaced by a salted one-way hash, so rows from one person can still
be grouped without naming them.
"""

import hashlib

FEEDBACK_FIELDS = (
    "request_id",
    "project_id",
    "fragment_id",
    "insertion_id",
    "event",
    "rank_position",
    "model_id",
    "exposure_verified",
    "created_at",
)

REQUEST_FIELDS = (
    "request_id",
    "project_id",
    "model_id_requested",
    "model_id_served",
    "implementation_revision",
    "fallback_used",
    "fragment_ids",
    "candidate_signals",
    "candidate_signal_names",
    "candidate_signal_available",
    "n_candidates_in",
    "created_at",
)


def _hash_participant(user_id: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()
    return f"p_{digest[:16]}"


def _export_rows(docs, fields: tuple[str, ...], salt: str) -> list[dict]:
    if not salt:
        raise ValueError("a non-empty salt is required")
    rows = []
    for doc in docs:
        row = {key: doc[key] for key in fields if key in doc}
        user_id = doc.get("user_id")
        if user_id:
            row["participant_hash"] = _hash_participant(str(user_id), salt)
        rows.append(row)
    return rows


def export_feedback_rows(docs, salt: str) -> list[dict]:
    """Feedback events (ranking_feedback) reduced to the allowlist."""
    return _export_rows(docs, FEEDBACK_FIELDS, salt)


def export_request_rows(docs, salt: str) -> list[dict]:
    """Served proposal lists (ranking_requests) reduced to the allowlist."""
    return _export_rows(docs, REQUEST_FIELDS, salt)
