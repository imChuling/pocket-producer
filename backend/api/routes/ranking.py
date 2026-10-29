import asyncio
import io
import logging
import os
import threading
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator

from ranking.enrichment import attach_audio_embeddings
from ranking.intent import apply_parsed_intent, parse_intent
from ranking.schemas import FeedbackEvent, RankRequest, RankResponse
from ranking.service import default_service

from ..auth import verify_firebase_token
from ..deps import get_db, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ranking", tags=["ranking"])

RANK_TIMEOUT_SECONDS = 2.0
INTENT_TIMEOUT_SECONDS = 8.0

_service = default_service()


@router.get("/model-card")
@limiter.limit("30/minute")
async def model_card(request: Request, user_id: str = Depends(verify_firebase_token)):
    return {"default": "rules-v1", "models": _service.model_cards()}


@router.post("/rank", response_model=RankResponse)
@limiter.limit("20/minute")
async def rank(
    request: Request,
    rank_request: RankRequest,
    user_id: str = Depends(verify_firebase_token),
) -> RankResponse:
    db = get_db()
    rank_request = await asyncio.to_thread(attach_audio_embeddings, db, user_id, rank_request)
    rank_request = apply_parsed_intent(rank_request)
    loop = asyncio.get_running_loop()
    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _service.rank, rank_request),
            timeout=RANK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(
            "ranking timeout after %.1fs: requested=%s, falling back to rules",
            RANK_TIMEOUT_SECONDS,
            rank_request.model_id,
        )
        response = _service.rank_fallback(rank_request)
    if response.fallback_used:
        logger.info(
            "ranking fallback: requested=%s served=%s request_id=%s",
            rank_request.model_id,
            response.model_id,
            response.request_id,
        )
    await asyncio.to_thread(_log_exposure, db, user_id, rank_request, response)
    return response


def _log_exposure(db, user_id: str, rank_request: RankRequest, response: RankResponse) -> None:
    """Persist the served list so feedback events have a denominator.

    Ids and ranking metadata only: no text_intent, no embeddings, no OAuth
    material. candidate_signals holds the per-candidate signal vector
    (five scalars) when the serving ranker exposes one, so later decisions
    can supervise the fusion weights. A failed write must never fail the
    rank request itself.
    """
    try:
        db["ranking_requests"].insert_one(
            {
                "request_id": response.request_id,
                "user_id": user_id,
                "project_id": rank_request.session.project_id,
                "model_id_requested": rank_request.model_id,
                "model_id_served": response.model_id,
                "fallback_used": response.fallback_used,
                "fragment_ids": [c.fragment_id for c in response.candidates],
                "candidate_signals": [c.signals for c in response.candidates],
                "n_candidates_in": len(rank_request.candidates),
                "created_at": datetime.now(UTC),
            }
        )
    except Exception:
        logger.warning(
            "exposure logging failed for request_id=%s", response.request_id
        )


# --- LLM intent parsing -----------------------------------------------------


class IntentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.post("/intent")
@limiter.limit("15/minute")
async def parse_intent_endpoint(
    request: Request,
    body: IntentRequest,
    user_id: str = Depends(verify_firebase_token),
):
    """Interpret free-text creative intent as structured, editable fields.

    The client shows the result as chips the user can correct, then echoes
    the approved version back inside SessionFingerprint.parsed_intent. A
    null result means the client should degrade to raw-text matching; it is
    never an error the user has to see.
    """
    try:
        parsed = await asyncio.wait_for(
            asyncio.to_thread(parse_intent, body.text),
            timeout=INTENT_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning("intent parsing timed out after %.1fs", INTENT_TIMEOUT_SECONDS)
        parsed = None
    return {"parsed": parsed.model_dump() if parsed is not None else None}


# --- Session audio CLAP encoding ------------------------------------------

_clap_adapter = None
_clap_lock = threading.Lock()
_clap_infer_lock = threading.Lock()

EMBED_TIMEOUT_SECONDS = 20.0


def _get_clap():
    global _clap_adapter
    if _clap_adapter is not None:
        return _clap_adapter
    if os.environ.get("POCKET_ENABLE_CLAP") != "1":
        return None
    with _clap_lock:
        if _clap_adapter is not None:
            return _clap_adapter
        import torch

        torch.set_num_threads(2)
        from ranking.adapters.msclap import MsClapAdapter

        _clap_adapter = MsClapAdapter()
    return _clap_adapter


def _encode_audio_serialized(clap, waveform, sample_rate):
    with _clap_infer_lock:
        return clap.encode_audio(waveform, sample_rate)


MAX_SESSION_FILES = 8
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/session-embed")
@limiter.limit("10/minute")
async def session_embed(
    request: Request,
    files: list[UploadFile] = File(...),
    user_id: str = Depends(verify_firebase_token),
):
    clap = _get_clap()
    if clap is None:
        raise HTTPException(
            status_code=503,
            detail="CLAP encoding is not enabled on this server",
        )
    if len(files) > MAX_SESSION_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_SESSION_FILES} files per request",
        )

    async def _encode_all():
        embeddings: list[list[float]] = []
        for upload in files:
            raw = await upload.read()
            if len(raw) > MAX_FILE_SIZE:
                embeddings.append([])
                continue
            try:
                import soundfile

                waveform, sample_rate = soundfile.read(
                    io.BytesIO(raw), dtype="float32"
                )
                vector = await asyncio.to_thread(
                    _encode_audio_serialized,
                    clap,
                    np.asarray(waveform, dtype=np.float32),
                    sample_rate,
                )
                embeddings.append(vector.tolist())
            except Exception:
                logger.warning("session-embed: failed to encode %s", upload.filename)
                embeddings.append([])
        return embeddings

    try:
        embeddings = await asyncio.wait_for(
            _encode_all(), timeout=EMBED_TIMEOUT_SECONDS
        )
    except TimeoutError:
        logger.warning("session-embed timed out after %.0fs", EMBED_TIMEOUT_SECONDS)
        embeddings = []
    valid = [e for e in embeddings if len(e) > 0]
    return {"embeddings": valid, "total": len(files), "encoded": len(valid)}


# --- Blind pairwise annotation (research protocol, models hidden) ----------

REASON_CODES = frozenset(
    {
        "tempo_fit",
        "key_fit",
        "supports_next_step",
        "fills_missing_role",
        "rhythmic_fit",
        "mood_fit",
        "novelty_welcome",
        "too_similar",
        "wrong_energy",
        "other",
    }
)


class PairLabel(BaseModel):
    choice: Literal["left", "right", "neither"]
    reason_codes: list[str] = []
    confidence: int = Field(ge=1, le=5)

    @field_validator("reason_codes")
    @classmethod
    def reason_codes_must_be_known(cls, value: list[str]) -> list[str]:
        unknown = set(value) - REASON_CODES
        if unknown:
            raise ValueError(f"unknown reason codes: {sorted(unknown)}")
        return value


def _fragment_summary(db, user_id: str, fragment_id: str) -> dict:
    try:
        oid = ObjectId(fragment_id)
    except (InvalidId, TypeError):
        return {"fragment_id": fragment_id, "title": None, "audio_url": None}
    doc = db["fragments"].find_one({"_id": oid, "user_id": user_id}) or {}
    return {
        "fragment_id": fragment_id,
        "title": doc.get("title"),
        "audio_url": f"/api/fragments/{fragment_id}/audio",
    }


def _next_pair_sync(db, user_id):
    """Fetch the next annotation pair and its fragment summaries."""
    remaining = db["annotation_pairs"].count_documents(
        {"user_id": user_id, "status": "pending"}
    )
    pair = db["annotation_pairs"].find_one(
        {"user_id": user_id, "status": "pending"}
    )
    if pair is None:
        return {"done": True, "remaining": 0}
    return {
        "done": False,
        "remaining": remaining,
        "pair": {
            "pair_id": str(pair["_id"]),
            "context_project_id": pair.get("context_project_id"),
            "context": [
                _fragment_summary(db, user_id, fragment_id)
                for fragment_id in pair.get("context_fragment_ids", [])
            ],
            "left": _fragment_summary(db, user_id, pair["left_fragment_id"]),
            "right": _fragment_summary(db, user_id, pair["right_fragment_id"]),
        },
    }


@router.get("/pairs/next")
@limiter.limit("30/minute")
async def next_annotation_pair(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    return await asyncio.to_thread(_next_pair_sync, db, user_id)


def _label_pair_sync(db, oid, user_id, pair_id, label):
    """Validate and persist a pairwise annotation label."""
    pair = db["annotation_pairs"].find_one({"_id": oid, "user_id": user_id})
    if pair is None:
        raise HTTPException(status_code=404, detail="Pair not found")
    if pair.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Pair already labeled")
    db["annotation_labels"].insert_one(
        {
            "pair_id": pair_id,
            "user_id": user_id,
            "choice": label.choice,
            "reason_codes": label.reason_codes,
            "confidence": label.confidence,
            "models_hidden": True,
            "created_at": datetime.now(UTC),
        }
    )
    db["annotation_pairs"].update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"status": "labeled"}}
    )


@router.post("/pairs/{pair_id}/label")
@limiter.limit("30/minute")
async def label_annotation_pair(
    request: Request,
    pair_id: str,
    label: PairLabel,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    try:
        oid = ObjectId(pair_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Pair not found")
    await asyncio.to_thread(_label_pair_sync, db, oid, user_id, pair_id, label)
    return {"status": "ok"}


@router.post("/feedback")
@limiter.limit("30/minute")
async def feedback(
    request: Request,
    event: FeedbackEvent,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    exposure = await asyncio.to_thread(
        db["ranking_requests"].find_one,
        {"request_id": event.request_id, "user_id": user_id},
        {"_id": 1},
    )
    if exposure is None:
        logger.warning(
            "feedback references unknown request_id=%s user=%s",
            event.request_id,
            user_id,
        )
    await asyncio.to_thread(
        db["ranking_feedback"].insert_one,
        {
            **event.model_dump(),
            "user_id": user_id,
            "created_at": datetime.now(UTC),
            "exposure_verified": exposure is not None,
        },
    )
    return {"status": "ok"}
