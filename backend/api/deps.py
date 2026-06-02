"""Shared dependencies used across route modules."""

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

MAX_AUDIO_BYTES = 25 * 1024 * 1024
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

limiter = Limiter(key_func=get_remote_address)

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
