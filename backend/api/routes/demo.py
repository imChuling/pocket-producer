"""Read-only demo endpoints: serve the seed account without authentication."""

import asyncio
from collections import Counter

from fastapi import APIRouter, Header, HTTPException, Request

from ..deps import get_db, limiter, parse_object_id
from .fragments import gcs_audio_response

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_USER_ID = "demo-seed-user"
MAX_FRAGMENTS = 100

# Storage paths and pipeline state stay server-side.
_FRAGMENT_PROJECTION = {
    "embedding": 0,
    "representations": 0,
    "edit_history": 0,
    "audio_url": 0,
    "pipeline_step": 0,
}


@router.get("/fragments")
@limiter.limit("30/minute")
async def demo_fragments(request: Request, limit: int = 50):
    limit = max(1, min(limit, MAX_FRAGMENTS))
    db = get_db()
    fragments = await asyncio.to_thread(
        lambda: list(
            db["fragments"]
            .find({"user_id": DEMO_USER_ID}, _FRAGMENT_PROJECTION)
            .sort("created_at", -1)
            .limit(limit)
        )
    )
    for f in fragments:
        f["_id"] = str(f["_id"])
    return {"fragments": fragments, "demo": True}


@router.get("/fragments/{fragment_id}/audio")
@limiter.limit("60/minute")
async def demo_fragment_audio(
    request: Request,
    fragment_id: str,
    range: str | None = Header(None),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": oid, "user_id": DEMO_USER_ID},
        {"audio_url": 1},
    )
    if not fragment or not fragment.get("audio_url"):
        raise HTTPException(status_code=404, detail="Audio not found")

    return await gcs_audio_response(
        fragment["audio_url"], range, cache_control="public, max-age=3600"
    )


@router.get("/projects")
@limiter.limit("30/minute")
async def demo_projects(request: Request):
    db = get_db()
    projects = await asyncio.to_thread(
        lambda: list(
            db["projects"]
            .find({"user_id": DEMO_USER_ID}, {"embedding": 0})
            .sort("_id", 1)
            .limit(20)
        )
    )
    for p in projects:
        p["_id"] = str(p["_id"])
    return {"projects": projects, "demo": True}


@router.get("/projects/{project_id}")
@limiter.limit("30/minute")
async def demo_project_detail(request: Request, project_id: str):
    db = get_db()
    oid = parse_object_id(project_id, "project_id")
    project = await asyncio.to_thread(
        db["projects"].find_one,
        {"_id": oid, "user_id": DEMO_USER_ID},
        {"embedding": 0},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["_id"] = str(project["_id"])

    fragment_ids = project.get("fragment_ids") or []
    oids = [parse_object_id(fid, "fragment_id") for fid in fragment_ids]
    fragments = []
    if oids:
        fragments = await asyncio.to_thread(
            lambda: list(
                db["fragments"].find(
                    {"_id": {"$in": oids}, "user_id": DEMO_USER_ID},
                    _FRAGMENT_PROJECTION,
                )
            )
        )
    for f in fragments:
        f["_id"] = str(f["_id"])
    order = {fid: i for i, fid in enumerate(fragment_ids)}
    fragments.sort(key=lambda f: order.get(f["_id"], len(order)))

    project["fragments"] = fragments
    return project


@router.get("/dna")
@limiter.limit("30/minute")
async def demo_dna(request: Request):
    """Compute a DNA summary from the seed fragments on the fly."""
    db = get_db()
    fragments = await asyncio.to_thread(
        lambda: list(
            db["fragments"].find(
                {"user_id": DEMO_USER_ID},
                {"emotions": 1, "themes": 1, "style": 1, "created_at": 1,
                 "project_id": 1, "connection_types": 1},
            )
        )
    )
    if not fragments:
        return {"demo": True}

    emotions: Counter[str] = Counter()
    themes: Counter[str] = Counter()
    styles: Counter[str] = Counter()
    structures: Counter[str] = Counter()
    project_ids: set[str] = set()

    for f in fragments:
        emotions.update(f.get("emotions") or [])
        themes.update(f.get("themes") or [])
        styles.update(f.get("style") or [])
        structures.update(f.get("connection_types") or [])
        if f.get("project_id"):
            project_ids.add(str(f["project_id"]))

    # The seed fragments were all inserted in one batch, so capture times
    # carry no rhythm; the hourly view is left empty rather than invented.
    return {
        "emotions": dict(emotions),
        "themes": dict(themes),
        "top_styles": [{"_id": k, "count": v} for k, v in styles.most_common(10)],
        "hourly_distribution": {},
        "structure_distribution": [
            {"_id": k, "count": v} for k, v in structures.most_common(10)
        ],
        "total_fragments": len(fragments),
        "total_projects": len(project_ids),
        "updated_at": max(
            (f["created_at"] for f in fragments if f.get("created_at")), default=None
        ),
        "demo": True,
    }
