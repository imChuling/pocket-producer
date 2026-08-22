import asyncio
import io
import logging
import os
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator

from ranking.enrichment import attach_audio_embeddings
from ranking.schemas import FeedbackEvent, RankRequest, RankResponse
from ranking.service import default_service

from ..auth import verify_firebase_token
from ..deps import get_db, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ranking", tags=["ranking"])

RANK_TIMEOUT_SECONDS = 2.0

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
    rank_request = attach_audio_embeddings(get_db(), user_id, rank_request)
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
    return response


# --- Session audio CLAP encoding ------------------------------------------

_clap_adapter = None


def _get_clap():
    global _clap_adapter
    if _clap_adapter is not None:
        return _clap_adapter
    if os.environ.get("POCKET_ENABLE_CLAP") != "1":
        return None
    from ranking.adapters.msclap import MsClapAdapter

    _clap_adapter = MsClapAdapter()
    return _clap_adapter


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
    embeddings: list[list[float]] = []
    for upload in files:
        raw = await upload.read()
        if len(raw) > MAX_FILE_SIZE:
            embeddings.append([])
            continue
        try:
            import soundfile

            waveform, sample_rate = soundfile.read(io.BytesIO(raw), dtype="float32")
            vector = clap.encode_audio(
                np.asarray(waveform, dtype=np.float32), sample_rate
            )
            embeddings.append(vector.tolist())
        except Exception:
            logger.warning("session-embed: failed to encode %s", upload.filename)
            embeddings.append([])
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


@router.get("/pairs/next")
@limiter.limit("30/minute")
async def next_annotation_pair(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
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
    return {"status": "ok"}


@router.post("/feedback")
@limiter.limit("30/minute")
async def feedback(
    request: Request,
    event: FeedbackEvent,
    user_id: str = Depends(verify_firebase_token),
):
    # user_id comes from the verified Firebase token only; a user_id in the
    # request body is ignored by schema. OAuth tokens are never accepted here.
    db = get_db()
    db["ranking_feedback"].insert_one(
        {
            **event.model_dump(),
            "user_id": user_id,
            "created_at": datetime.now(UTC),
        }
    )
    return {"status": "ok"}
