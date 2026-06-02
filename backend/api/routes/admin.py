import asyncio
import logging
import os

from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..auth import verify_firebase_token
from ..deps import get_db, limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.get("/api/dna")
@limiter.limit("10/minute")
async def get_dna(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    dna = db["user_dna"].find_one({"user_id": user_id})
    if dna:
        dna["_id"] = str(dna["_id"])
    return dna or {}


@router.post("/api/reprocess-projects")
@limiter.limit("2/minute")
async def reprocess_projects(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
):
    import time

    from ..pipeline import memory_and_project

    db = get_db()
    fragments = list(
        db["fragments"].find(
            {
                "user_id": user_id,
                "embedding": {"$exists": True},
                "project_id": {"$exists": False},
                "status": "ready",
            },
            {"embedding": 1, "emotions": 1, "themes": 1, "tags": 1, "structure_hint": 1},
        )
    )
    if not fragments:
        return {"message": "No fragments to reprocess", "processed": 0}

    t0 = time.monotonic()
    processed = 0
    for frag in fragments:
        frag_id = str(frag["_id"])
        embedding = frag.get("embedding")
        if not embedding:
            continue
        tag_result = {
            "emotions": frag.get("emotions", []),
            "themes": frag.get("themes", []),
            "tags": frag.get("tags", []),
        }
        try:
            await memory_and_project(db, user_id, frag_id, embedding, tag_result, t0)
            processed += 1
        except Exception:
            logger.exception("Reprocess failed for %s", frag_id)

    from jobs.dna_insights import run as run_dna
    await asyncio.to_thread(run_dna)

    return {"message": f"Processed {processed} fragments", "processed": processed}


@router.post("/api/reanalyze-all")
@limiter.limit("2/minute")
async def reanalyze_all_fragments(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
):
    from ..pipeline import process_fragment_background

    db = get_db()
    fragments = list(
        db["fragments"].find(
            {"user_id": user_id},
            {"_id": 1, "audio_url": 1, "text": 1, "type": 1},
        )
    )
    if not fragments:
        return {"message": "No fragments found", "processed": 0}

    db["fragments"].update_many(
        {"user_id": user_id},
        {"$set": {"status": "processing"}},
    )

    tasks = set()
    for frag in fragments:
        frag_id = str(frag["_id"])
        task = asyncio.create_task(
            process_fragment_background(user_id, frag_id, frag.get("audio_url"), frag.get("text"))
        )
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    return {
        "message": f"Reanalyzing {len(fragments)} fragments in background",
        "processing": len(fragments),
    }


@router.post("/api/fix-stuck")
@limiter.limit("5/minute")
async def fix_stuck_fragments(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    result = db["fragments"].update_many(
        {
            "user_id": user_id,
            "status": "processing",
            "tags": {"$exists": True, "$ne": []},
        },
        {"$set": {"status": "ready"}},
    )
    return {"fixed": result.modified_count}


@router.post("/api/reset-projects")
@limiter.limit("2/minute")
async def reset_projects(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    deleted = db["projects"].delete_many({"user_id": user_id})
    db["fragments"].update_many(
        {"user_id": user_id},
        {"$unset": {
            "project_id": "", "project_title": "",
            "connection_reason": "", "connection_types": "",
        }},
    )
    return {"deleted_projects": deleted.deleted_count}


@router.get("/api/agent-memory/status")
@limiter.limit("10/minute")
async def agent_memory_status(request: Request, user_id: str = Depends(verify_firebase_token)):
    return {
        "user_id": user_id,
        "pipeline": "producer_agent -> memory_agent (sub_agent)",
        "path": "direct Gemini tagging -> Producer Agent -> Memory Agent (vector search + relationship rules) -> project decision",
        "producer_model": os.environ.get("PRODUCER_MODEL", "gemini-2.5-flash"),
        "memory_model": os.environ.get("MEMORY_MODEL", "gemini-2.5-flash"),
        "mcp_read_tools_enabled": os.environ.get("ENABLE_MCP_MEMORY_TOOLS") == "1",
        "mcp_server_url_configured": bool(os.environ.get("MCP_SERVER_URL")),
        "skills_loaded": ["rescue-scoring", "musical-knowledge", "refusal-rules", "relationship-rules"],
    }


def _verify_job_auth(authorization: str | None):
    job_secret = os.environ.get("JOB_TRIGGER_SECRET")
    if job_secret and authorization == f"Bearer {job_secret}":
        return
    service_url = os.environ.get("SERVICE_URL", "")
    if authorization and authorization.startswith("Bearer "):
        try:
            from google.auth.transport import requests as gauth_requests
            from google.oauth2 import id_token

            token = authorization[7:]
            id_token.verify_oauth2_token(
                token,
                gauth_requests.Request(),
                audience=service_url or None,
            )
            return
        except Exception:
            pass
    raise HTTPException(status_code=403, detail="Unauthorized")


@router.post("/api/jobs/dna")
async def trigger_dna_job(authorization: str = Header(None)):
    _verify_job_auth(authorization)
    from jobs.dna_insights import run
    run()
    return {"status": "completed"}


@router.post("/api/jobs/resurrect")
async def trigger_resurrect_job(authorization: str = Header(None)):
    _verify_job_auth(authorization)
    from jobs.resurrect import run
    run()
    return {"status": "completed"}
