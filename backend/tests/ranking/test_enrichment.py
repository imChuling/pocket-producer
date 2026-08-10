"""Attaching stored audio vectors to rank candidates, scoped to the owner."""

from bson import ObjectId

from ranking.enrichment import attach_audio_embeddings
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint

OWNED = str(ObjectId())
FOREIGN = str(ObjectId())
MISSING = str(ObjectId())


class StubCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query, projection=None):
        wanted = set(query["_id"]["$in"])
        user_id = query["user_id"]
        return [
            doc
            for doc in self._docs
            if doc["_id"] in wanted and doc["user_id"] == user_id
        ]


class StubDB:
    def __init__(self, docs):
        self._fragments = StubCollection(docs)

    def __getitem__(self, name):
        assert name == "fragments"
        return self._fragments


def db() -> StubDB:
    return StubDB(
        [
            {
                "_id": ObjectId(OWNED),
                "user_id": "u1",
                "representations": {"audio_semantic": {"vector": [0.1, 0.9]}},
                "embedding": [0.7, 0.3],
            },
            {
                "_id": ObjectId(FOREIGN),
                "user_id": "someone-else",
                "representations": {"audio_semantic": {"vector": [0.5, 0.5]}},
            },
        ]
    )


def candidate(fragment_id: str) -> FragmentCandidate:
    return FragmentCandidate(
        fragment_id=fragment_id,
        duration_seconds=4.0,
        created_at_iso="2026-07-01T00:00:00Z",
        audio_url=f"/api/fragments/{fragment_id}/audio",
    )


def request(*ids: str) -> RankRequest:
    return RankRequest(
        session=SessionFingerprint(
            project_id="p1", playhead_seconds=0, track_count=0
        ),
        candidates=[candidate(fragment_id) for fragment_id in ids],
    )


def test_owned_fragment_gets_its_stored_vector():
    enriched = attach_audio_embeddings(db(), "u1", request(OWNED))
    assert enriched.candidates[0].audio_embedding == [0.1, 0.9]


def test_legacy_text_embedding_is_attached_as_text_vector():
    enriched = attach_audio_embeddings(db(), "u1", request(OWNED))
    assert enriched.candidates[0].text_embedding == [0.7, 0.3]


def test_foreign_fragment_never_leaks_a_vector():
    enriched = attach_audio_embeddings(db(), "u1", request(FOREIGN))
    assert enriched.candidates[0].audio_embedding is None


def test_missing_and_invalid_ids_stay_none():
    enriched = attach_audio_embeddings(
        db(), "u1", request(MISSING, "not-an-object-id")
    )
    assert all(c.audio_embedding is None for c in enriched.candidates)


def test_existing_embeddings_are_not_overwritten():
    req = request(OWNED)
    req.candidates[0].audio_embedding = [9.0, 9.0]
    enriched = attach_audio_embeddings(db(), "u1", req)
    assert enriched.candidates[0].audio_embedding == [9.0, 9.0]
