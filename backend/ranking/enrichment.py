"""Attach stored audio representations to rank candidates.

Vectors never travel from the browser; the server looks them up scoped to the
authenticated owner, so a request can never rank against another user's
representations.
"""

from bson import ObjectId
from bson.errors import InvalidId

from ranking.schemas import RankRequest


def attach_audio_embeddings(db, user_id: str, request: RankRequest) -> RankRequest:
    wanted: dict[str, ObjectId] = {}
    for candidate in request.candidates:
        if candidate.audio_embedding is not None and candidate.text_embedding is not None:
            continue
        try:
            wanted[candidate.fragment_id] = ObjectId(candidate.fragment_id)
        except (InvalidId, TypeError):
            continue
    if not wanted:
        return request
    docs = db["fragments"].find(
        {"_id": {"$in": list(wanted.values())}, "user_id": user_id},
        {"representations.audio_semantic.vector": 1, "embedding": 1},
    )
    audio_vectors: dict[str, list[float] | None] = {}
    text_vectors: dict[str, list[float] | None] = {}
    for doc in docs:
        fragment_id = str(doc["_id"])
        audio_vectors[fragment_id] = (
            (doc.get("representations") or {})
            .get("audio_semantic", {})
            .get("vector")
        )
        # The legacy `embedding` field is the voyage-3 TEXT representation.
        text_vectors[fragment_id] = doc.get("embedding")
    for candidate in request.candidates:
        if candidate.audio_embedding is None:
            vector = audio_vectors.get(candidate.fragment_id)
            if vector:
                candidate.audio_embedding = list(vector)
        if candidate.text_embedding is None:
            vector = text_vectors.get(candidate.fragment_id)
            if vector:
                candidate.text_embedding = list(vector)
    return request
