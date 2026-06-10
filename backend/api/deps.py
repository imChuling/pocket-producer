"""Shared dependencies used across route modules."""

import asyncio
import logging
import os
import re

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pymongo import MongoClient
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_DURATION_SEC = 180
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

limiter = Limiter(key_func=get_remote_address)

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


# DNA update debounce — collapse rapid successive triggers into one run
_dna_lock = asyncio.Lock()
_dna_pending = False


async def debounced_dna_update(delay: float = 2.0):
    """Schedule a DNA update, collapsing multiple calls within `delay` seconds."""
    global _dna_pending
    if _dna_pending:
        return
    _dna_pending = True
    await asyncio.sleep(delay)
    async with _dna_lock:
        _dna_pending = False
        try:
            from jobs.dna_insights import run as run_dna
            await asyncio.to_thread(run_dna)
        except Exception:
            logger.warning("Debounced DNA update failed", exc_info=True)

_mongo = None


def get_db():
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.environ["MONGODB_CONNECTION_STRING"], maxPoolSize=10)
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
