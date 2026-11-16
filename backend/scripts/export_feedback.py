"""Export the proposal log and feedback events for local analysis.

Writes two JSONL files that research/analyze_feedback.py and
research/finetune_from_feedback.py read. Only allowlisted fields are
fetched and written (ranking.research.export); the user ID is replaced by
a salted one-way hash. The salt comes from FEEDBACK_EXPORT_SALT and is not
stored with the export. Keep the output on this machine.

  cd backend && FEEDBACK_EXPORT_SALT=... .venv/bin/python -m scripts.export_feedback \
    --out ../artifacts/feedback-export

Output: <out>/requests.jsonl and <out>/feedback.jsonl.
"""

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from ranking.research.export import (  # noqa: E402
    FEEDBACK_FIELDS,
    REQUEST_FIELDS,
    export_feedback_rows,
    export_request_rows,
)

COLLECTIONS = (
    ("ranking_requests", REQUEST_FIELDS, export_request_rows, "requests.jsonl"),
    ("ranking_feedback", FEEDBACK_FIELDS, export_feedback_rows, "feedback.jsonl"),
)


def _encode(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"cannot export {type(value).__name__}")


def export(db, out: pathlib.Path, salt: str) -> list[pathlib.Path]:
    """Write both collections to `out`; return the files written."""
    if not salt:
        raise ValueError("FEEDBACK_EXPORT_SALT must be set to a non-empty value")
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for collection, fields, to_rows, filename in COLLECTIONS:
        projection = {"_id": 0, "user_id": 1, **{field: 1 for field in fields}}
        rows = to_rows(db[collection].find({}, projection), salt)
        path = out / filename
        path.write_text(
            "".join(json.dumps(row, default=_encode, ensure_ascii=False) + "\n" for row in rows)
        )
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    salt = os.environ.get("FEEDBACK_EXPORT_SALT", "")
    if not salt:
        parser.error("set FEEDBACK_EXPORT_SALT; it is not stored with the export")

    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGODB_CONNECTION_STRING"], serverSelectionTimeoutMS=5000)
    for path in export(client["pocketproducer"], args.out, salt):
        print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
