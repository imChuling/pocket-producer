import asyncio
import logging
import os
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..auth import verify_firebase_token
from ..deps import debounced_dna_update, get_db, limiter

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


@router.get("/api/dna/network")
@limiter.limit("10/minute")
async def get_dna_network(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    frags = list(db["fragments"].find(
        {"user_id": user_id, "status": "ready"},
        {"embedding": 0, "raw_text": 0, "edit_history": 0},
    ))
    projects = list(db["projects"].find(
        {"user_id": user_id},
        {"fragment_ids": 1, "title": 1, "connection_types": 1},
    ))
    nodes = []
    for f in frags:
        nodes.append({
            "id": str(f["_id"]),
            "title": f.get("title") or (f.get("text") or "")[:40],
            "type": f.get("type", "text"),
            "emotions": f.get("emotions", []),
            "project_id": f.get("project_id"),
            "project_title": f.get("project_title"),
        })
    edges = []
    for p in projects:
        fids = p.get("fragment_ids", [])
        for i, a in enumerate(fids):
            for b in fids[i + 1:]:
                edges.append({
                    "source": a,
                    "target": b,
                    "project_id": str(p["_id"]),
                    "project_title": p.get("title", ""),
                })
    return {"nodes": nodes, "edges": edges}



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

    async def _process_one(frag):
        frag_id = str(frag["_id"])
        embedding = frag.get("embedding")
        if not embedding:
            return False
        tag_result = {
            "emotions": frag.get("emotions", []),
            "themes": frag.get("themes", []),
            "tags": frag.get("tags", []),
        }
        try:
            await memory_and_project(db, user_id, frag_id, embedding, tag_result, t0)
            return True
        except Exception:
            logger.exception("Reprocess failed for %s", frag_id)
            return False

    results = await asyncio.gather(*[_process_one(f) for f in fragments])
    processed = sum(1 for r in results if r)

    await debounced_dna_update()

    return {"message": f"Processed {processed} fragments", "processed": processed}


@router.post("/api/fix-stuck")
@limiter.limit("5/minute")
async def fix_stuck_fragments(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
):
    from datetime import timedelta
    db = get_db()
    cutoff = datetime.now(UTC) - timedelta(minutes=2)
    result = db["fragments"].update_many(
        {
            "user_id": user_id,
            "status": "processing",
            "$or": [
                {"tags": {"$exists": True, "$ne": []}},
                {"created_at": {"$lt": cutoff}},
            ],
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
        "mcp_read_tools_enabled": os.environ.get("ENABLE_MCP_MEMORY_TOOLS") != "0",
        "mcp_server_url_configured": bool(os.environ.get("MCP_SERVER_URL")),
        "skills_loaded": ["rescue-scoring", "musical-knowledge", "refusal-rules", "relationship-rules"],
    }


@router.get("/api/settings/sensitivity")
@limiter.limit("10/minute")
async def get_sensitivity(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    doc = db["user_settings"].find_one({"user_id": user_id}, {"sensitivity": 1})
    if doc and "sensitivity" in doc:
        threshold = doc["sensitivity"]["threshold"]
        level = doc["sensitivity"]["level"]
    else:
        threshold = float(os.environ.get("SIMILARITY_THRESHOLD", "0.55"))
        level = "high" if threshold <= 0.50 else "medium" if threshold <= 0.62 else "low"
    return {"threshold": threshold, "level": level}


@router.post("/api/settings/sensitivity")
@limiter.limit("5/minute")
async def set_sensitivity(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    body = await request.json()
    level = body.get("level", "medium")
    thresholds = {"high": 0.45, "medium": 0.55, "low": 0.70}
    threshold = thresholds.get(level, 0.55)
    db["user_settings"].update_one(
        {"user_id": user_id},
        {"$set": {"sensitivity": {"threshold": threshold, "level": level}}},
        upsert=True,
    )
    return {"threshold": threshold, "level": level}


@router.delete("/api/account")
@limiter.limit("1/minute")
async def delete_account(request: Request, user_id: str = Depends(verify_firebase_token)):
    """Delete all user data: fragments (+ GCS audio), projects, DNA, settings, notifications."""
    db = get_db()

    # Collect GCS audio URIs before deleting fragments
    gcs_uris = []
    for frag in db["fragments"].find({"user_id": user_id}, {"audio_url": 1}):
        url = frag.get("audio_url")
        if url and url.startswith("gs://"):
            gcs_uris.append(url)

    # Delete all collections
    r_frags = db["fragments"].delete_many({"user_id": user_id})
    r_projects = db["projects"].delete_many({"user_id": user_id})
    r_dna = db["user_dna"].delete_many({"user_id": user_id})
    r_settings = db["user_settings"].delete_many({"user_id": user_id})
    r_notifs = db["notifications"].delete_many({"user_id": user_id})

    # Delete GCS audio files
    gcs_deleted = 0
    if gcs_uris:
        try:
            from google.cloud import storage
            client = storage.Client()
            for uri in gcs_uris:
                parts = uri.replace("gs://", "").split("/", 1)
                if len(parts) == 2:
                    try:
                        client.bucket(parts[0]).blob(parts[1]).delete()
                        gcs_deleted += 1
                    except Exception:
                        logger.warning("Failed to delete GCS object: %s", uri)
        except Exception:
            logger.exception("GCS cleanup failed")

    logger.info(
        "Account deleted for %s: %d fragments, %d projects, %d dna, %d settings, %d notifications, %d GCS files",
        user_id, r_frags.deleted_count, r_projects.deleted_count, r_dna.deleted_count,
        r_settings.deleted_count, r_notifs.deleted_count, gcs_deleted,
    )
    return {
        "deleted": {
            "fragments": r_frags.deleted_count,
            "projects": r_projects.deleted_count,
            "dna": r_dna.deleted_count,
            "settings": r_settings.deleted_count,
            "notifications": r_notifs.deleted_count,
            "gcs_audio_files": gcs_deleted,
        }
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


@router.post("/api/resurrect-scan")
@limiter.limit("5/minute")
async def user_resurrect_scan(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
):
    """Scan for connections between newest fragment and older fragments/projects.

    Unlike the batch job, this runs per-user on demand and uses a gentler time
    threshold so it works during demos.
    """
    from datetime import UTC, datetime

    db = get_db()

    # Find the most recent fragment
    latest = db["fragments"].find_one(
        {"user_id": user_id, "status": "ready", "embedding": {"$exists": True}},
        sort=[("created_at", -1)],
    )
    if not latest or not latest.get("embedding"):
        return {"notifications_created": 0, "reason": "no_ready_fragments_with_embedding"}

    # Vector search for similar older fragments
    pipeline = [
        {
            "$vectorSearch": {
                "index": "fragment_vector_index",
                "path": "embedding",
                "queryVector": latest["embedding"],
                "numCandidates": 50,
                "limit": 5,
                "filter": {"user_id": user_id},
            }
        },
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$match": {
            "_id": {"$ne": latest["_id"]},
            "score": {"$gte": 0.75},
        }},
        {"$project": {"embedding": 0}},
    ]
    neighbors = list(db["fragments"].aggregate(pipeline))

    created = 0
    for neighbor in neighbors:
        project_id = neighbor.get("project_id")
        if not project_id:
            continue

        # Check if we already sent this notification
        exists = db["notifications"].find_one({
            "user_id": user_id,
            "new_fragment_id": str(latest["_id"]),
            "sleeping_project_id": project_id,
        })
        if exists:
            continue

        project = db["projects"].find_one({"_id": ObjectId(project_id), "user_id": user_id})
        if not project:
            continue

        # Build a human-readable message
        latest_title = latest.get("title") or "your latest recording"
        project_title = project.get("title") or "an earlier project"
        neighbor_title = neighbor.get("title") or "a fragment"
        emotions = neighbor.get("emotions", [])
        emotion_str = f" — both carry a sense of {emotions[0]}" if emotions else ""

        message = (
            f"Your new fragment \"{latest_title}\" resonates with "
            f"\"{neighbor_title}\" in project \"{project_title}\""
            f"{emotion_str}. "
            f"This could be a thread worth pulling."
        )

        db["notifications"].insert_one({
            "user_id": user_id,
            "type": "resurrect",
            "new_fragment_id": str(latest["_id"]),
            "new_fragment_title": latest_title,
            "sleeping_project_id": project_id,
            "sleeping_project_title": project_title,
            "similarity_score": neighbor.get("score", 0),
            "message": message,
            "created_at": datetime.now(UTC),
            "read": False,
        })
        created += 1

    return {"notifications_created": created}
