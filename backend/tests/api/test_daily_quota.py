"""Per-user daily allowance for LLM-backed actions."""

import pytest
from fastapi import HTTPException

from api.deps import consume_daily_quota


class _Quota:
    def __init__(self):
        self.docs = []

    def find_one(self, query):
        return next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        doc = self.find_one(query)
        if doc is None and upsert:
            doc = {**query, **update.get("$setOnInsert", {}), "counts": {}}
            self.docs.append(doc)
        for path, delta in update.get("$inc", {}).items():
            bucket = path.split(".", 1)[1]
            doc["counts"][bucket] = doc["counts"].get(bucket, 0) + delta
        return doc

    def update_one(self, query, update):
        self.find_one_and_update(query, update)


class _DB:
    def __init__(self):
        self.quota = _Quota()

    def __getitem__(self, name):
        assert name == "usage_quota"
        return self.quota


def test_limit_is_exact_and_rejections_are_not_counted():
    db = _DB()
    for _ in range(3):
        consume_daily_quota(db, "u1", "ingest", limit=3)
    with pytest.raises(HTTPException) as excinfo:
        consume_daily_quota(db, "u1", "ingest", limit=3)
    assert excinfo.value.status_code == 429
    assert "3 ingest" in excinfo.value.detail
    assert excinfo.value.headers["Retry-After"] == "3600"
    assert db.quota.docs[0]["counts"]["ingest"] == 3


def test_buckets_and_users_are_independent():
    db = _DB()
    for _ in range(2):
        consume_daily_quota(db, "u1", "ingest", limit=2)
    consume_daily_quota(db, "u1", "intent", limit=2)
    consume_daily_quota(db, "u2", "ingest", limit=2)
    with pytest.raises(HTTPException):
        consume_daily_quota(db, "u1", "ingest", limit=2)


def test_default_limit_is_thirty():
    from api.deps import DAILY_LLM_QUOTA

    assert DAILY_LLM_QUOTA == 30
