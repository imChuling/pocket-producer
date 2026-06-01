"""Direct PyMongo tools for Agent use — replaces MCP MongoDB connection.

These async tools wrap synchronous PyMongo calls via asyncio.to_thread
so they don't block the event loop.
"""

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import MongoClient

_client: MongoClient | None = None
_ALLOWED_COLLECTIONS = {"fragments", "projects", "notifications", "user_dna"}


def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_CONNECTION_STRING"], maxPoolSize=10)
    return _client["pocketproducer"]


def _validate_collection(collection: str) -> None:
    if collection not in _ALLOWED_COLLECTIONS:
        raise ValueError(f"Collection not allowed: {collection}")


def _require_user_scope(filter: dict[str, Any]) -> None:
    if not filter.get("user_id"):
        raise ValueError("MongoDB agent tools require a user_id filter")


class _JSONEncoder(json.JSONEncoder):
    """Handle ObjectId and datetime in JSON serialization."""

    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def _to_json(obj: Any) -> str:
    return json.dumps(obj, cls=_JSONEncoder, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tools for Memory Agent (read-only)
# ---------------------------------------------------------------------------


def _vector_search_sync(
    collection: str,
    query_vector: list[float],
    user_id: str,
    limit: int = 10,
    num_candidates: int = 100,
) -> str:
    _validate_collection(collection)
    db = _get_db()
    pipeline = [
        {
            "$vectorSearch": {
                "index": "fragment_vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": limit,
                "filter": {"user_id": user_id},
            }
        },
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"embedding": 0}},
    ]
    results = list(db[collection].aggregate(pipeline))
    return _to_json(results)


async def vector_search(
    collection: str,
    query_vector: list[float],
    user_id: str,
    limit: int = 10,
) -> str:
    """Run $vectorSearch on a collection. Returns matching documents with similarity scores."""
    return await asyncio.to_thread(
        _vector_search_sync, collection, query_vector, user_id, limit
    )


def _find_sync(
    collection: str,
    filter: dict[str, Any] | None = None,
    limit: int = 20,
) -> str:
    _validate_collection(collection)
    _require_user_scope(filter or {})
    db = _get_db()
    cursor = db[collection].find(filter or {}, {"embedding": 0}).limit(limit)
    return _to_json(list(cursor))


async def find_documents(
    collection: str,
    filter: str = "{}",
    limit: int = 20,
) -> str:
    """Find documents in a collection. filter is a JSON string for the MongoDB query."""
    parsed_filter = json.loads(filter) if isinstance(filter, str) else filter
    return await asyncio.to_thread(_find_sync, collection, parsed_filter, limit)


def _count_sync(collection: str, filter: dict[str, Any] | None = None) -> str:
    _validate_collection(collection)
    _require_user_scope(filter or {})
    db = _get_db()
    count = db[collection].count_documents(filter or {})
    return _to_json({"count": count})


async def count_documents(
    collection: str,
    filter: str = "{}",
) -> str:
    """Count documents in a collection. filter is a JSON string."""
    parsed_filter = json.loads(filter) if isinstance(filter, str) else filter
    return await asyncio.to_thread(_count_sync, collection, parsed_filter)


# ---------------------------------------------------------------------------
# Tools for Producer Agent (read + write)
# ---------------------------------------------------------------------------


def _insert_sync(collection: str, documents: list[dict]) -> str:
    _validate_collection(collection)
    db = _get_db()
    for doc in documents:
        if not doc.get("user_id"):
            raise ValueError("Inserted documents must include user_id")
        if "created_at" not in doc:
            doc["created_at"] = datetime.now(UTC)
    result = db[collection].insert_many(documents)
    return _to_json(
        {"inserted_ids": [str(id) for id in result.inserted_ids]}
    )


async def insert_documents(
    collection: str,
    documents: str,
) -> str:
    """Insert one or more documents into a collection. documents is a JSON array string."""
    parsed = json.loads(documents) if isinstance(documents, str) else documents
    if isinstance(parsed, dict):
        parsed = [parsed]
    return await asyncio.to_thread(_insert_sync, collection, parsed)


def _update_sync(
    collection: str,
    filter: dict[str, Any],
    update: dict[str, Any],
) -> str:
    _validate_collection(collection)
    _require_user_scope(filter)
    db = _get_db()
    if not any(k.startswith("$") for k in update):
        update = {"$set": update}
    result = db[collection].update_one(filter, update)
    return _to_json(
        {
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
        }
    )


async def update_document(
    collection: str,
    filter: str,
    update: str,
) -> str:
    """Update a document in a collection. filter and update are JSON strings."""
    parsed_filter = json.loads(filter) if isinstance(filter, str) else filter
    parsed_update = json.loads(update) if isinstance(update, str) else update
    return await asyncio.to_thread(
        _update_sync, collection, parsed_filter, parsed_update
    )
