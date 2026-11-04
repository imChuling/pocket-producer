"""Shared dependencies used across route modules."""

import asyncio
import hashlib
import logging
import os
import re
import weakref

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pymongo import MongoClient
from slowapi import Limiter

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_DURATION_SEC = 300
MAX_TEXT_CHARS = 4000
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/x-m4a",
    "audio/mp4",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
}
PROMPT_INJECTION_RE = re.compile(
    r"(ignore (all )?(previous|prior|above) instructions|"
    r"system prompt|developer message|act as|jailbreak|"
    r"reveal (the )?(prompt|instructions)|"
    r"do not follow|you are now|forget (your |everything|all)"
    r"|new instructions|override (the |your )?instructions"
    r"|disregard (all |previous |prior )?"
    r"|</?(creator_fragment|system|instruction)>)",
    re.IGNORECASE,
)

def _rate_limit_key(request) -> str:
    """Per-user when a bearer token is present, else per forwarded client IP.

    A conference room shares one NAT address, so keying on IP alone would make
    every attendee share a single quota. The token is hashed, never stored.
    """
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer ") and len(authorization) > 20:
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        return f"user:{digest[:24]}"
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


limiter = Limiter(key_func=_rate_limit_key)

# ---------------------------------------------------------------------------
# Concurrent pipeline guard — reject (not queue) when too many are running
# ---------------------------------------------------------------------------
MAX_CONCURRENT_PIPELINES = int(os.environ.get("MAX_CONCURRENT_PIPELINES", "2"))
_pipeline_count = 0
_pipeline_count_lock = asyncio.Lock()


async def acquire_pipeline_slot() -> bool:
    global _pipeline_count
    async with _pipeline_count_lock:
        if _pipeline_count >= MAX_CONCURRENT_PIPELINES:
            return False
        _pipeline_count += 1
        return True


async def release_pipeline_slot():
    global _pipeline_count
    async with _pipeline_count_lock:
        _pipeline_count = max(0, _pipeline_count - 1)


# Per-user agent-pipeline serialization — two fragments uploaded close
# together must not both create a project for the same neighborhood.
# Weak values: a lock lives only while a pipeline holds it, so the map does
# not grow by one entry per user ever seen for the life of the process.
_user_agent_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
_user_agent_locks_guard = asyncio.Lock()


async def get_user_agent_lock(user_id: str) -> asyncio.Lock:
    async with _user_agent_locks_guard:
        lock = _user_agent_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            _user_agent_locks[user_id] = lock
        return lock


# DNA update debounce — collapse rapid successive triggers into one run.
# Pending-ness is tracked per user: one user's debounce window must not
# swallow another user's trigger, and a caller cancelled mid-wait (a
# reanalyze stream the client closed) must not leave the flag set forever.
_dna_lock = asyncio.Lock()
_dna_pending: set[str] = set()


async def debounced_dna_update(user_id: str | None = None, delay: float = 2.0):
    """Schedule a DNA update for one user, collapsing rapid triggers."""
    key = user_id or ""
    if key in _dna_pending:
        return
    _dna_pending.add(key)
    try:
        await asyncio.sleep(delay)
    finally:
        _dna_pending.discard(key)
    async with _dna_lock:
        try:
            from jobs.dna_insights import run as run_dna
            await asyncio.to_thread(run_dna, user_id)
        except Exception:
            logger.warning("Debounced DNA update failed", exc_info=True)

# ---------------------------------------------------------------------------
# Per-user daily quota for LLM-backed actions (uploads, intent parsing).
# The Gemini bill is ours; this caps what one trial account can spend.
# ---------------------------------------------------------------------------
DAILY_LLM_QUOTA = int(os.environ.get("POCKET_DAILY_LLM_QUOTA", "30"))


def consume_daily_quota(db, user_id: str, bucket: str, limit: int = DAILY_LLM_QUOTA) -> None:
    """Count one `bucket` action for today; raise 429 once the user is over `limit`.

    One document per (user, UTC day) with per-bucket counters, incremented
    atomically. A rejected call is not counted, so the user gets exactly
    `limit` successful actions per day.
    """
    from datetime import UTC, datetime

    from pymongo import ReturnDocument

    day = datetime.now(UTC).strftime("%Y-%m-%d")
    doc = db["usage_quota"].find_one_and_update(
        {"user_id": user_id, "day": day},
        {"$inc": {f"counts.{bucket}": 1}, "$setOnInsert": {"created_at": datetime.now(UTC)}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    used = int((doc or {}).get("counts", {}).get(bucket, 0))
    if used > limit:
        db["usage_quota"].update_one(
            {"user_id": user_id, "day": day}, {"$inc": {f"counts.{bucket}": -1}}
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily trial limit reached ({limit} {bucket} actions per day). "
                "Ranking, preview, insert and undo keep working; try again tomorrow."
            ),
            headers={"Retry-After": "3600"},
        )


_mongo = None


def get_db():
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(
            os.environ["MONGODB_CONNECTION_STRING"],
            maxPoolSize=10,
            serverSelectionTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
    return _mongo["pocketproducer"]


def parse_object_id(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail=f"Invalid {label}: {value}")


def sanitize_creator_text(value: str | None) -> tuple[str | None, bool]:
    """Normalize creator text and flag likely prompt-injection attempts."""
    if value is None:
        return None, False
    cleaned = "".join(
        ch for ch in value.replace("\x00", "") if ch in "\n\t" or ord(ch) >= 32
    ).strip()
    if len(cleaned) > MAX_TEXT_CHARS:
        cleaned = cleaned[:MAX_TEXT_CHARS].rstrip()
    cleaned = re.sub(r"</?(creator_fragment|system|instruction)\b[^>]*>", "", cleaned)
    return cleaned, bool(PROMPT_INJECTION_RE.search(cleaned))
