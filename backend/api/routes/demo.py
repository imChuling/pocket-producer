"""Read-only demo endpoints: serve the seed account without authentication.

The list views are also exported as static files by
`scripts/export_demo_snapshot.py`, so the demo pages render without waking
the backend; only audio playback reaches these routes in normal use.
"""

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


def fragments_payload(db, limit: int = 50) -> dict:
    limit = max(1, min(limit, MAX_FRAGMENTS))
    fragments = list(
        db["fragments"]
        .find({"user_id": DEMO_USER_ID}, _FRAGMENT_PROJECTION)
        .sort("created_at", -1)
        .limit(limit)
    )
    for f in fragments:
        f["_id"] = str(f["_id"])
    return {"fragments": fragments, "demo": True}


def projects_payload(db) -> dict:
    projects = list(
        db["projects"]
        .find({"user_id": DEMO_USER_ID}, {"embedding": 0})
        .sort([("rescue_score", -1), ("_id", 1)])
        .limit(20)
    )
    for p in projects:
        p["_id"] = str(p["_id"])
    return {"projects": projects, "demo": True}


def project_detail_payload(db, oid) -> dict | None:
    project = db["projects"].find_one({"_id": oid, "user_id": DEMO_USER_ID}, {"embedding": 0})
    if not project:
        return None
    project["_id"] = str(project["_id"])

    fragment_ids = project.get("fragment_ids") or []
    oids = [parse_object_id(fid, "fragment_id") for fid in fragment_ids]
    fragments = []
    if oids:
        fragments = list(
            db["fragments"].find(
                {"_id": {"$in": oids}, "user_id": DEMO_USER_ID}, _FRAGMENT_PROJECTION
            )
        )
    for f in fragments:
        f["_id"] = str(f["_id"])
    order = {fid: i for i, fid in enumerate(fragment_ids)}
    fragments.sort(key=lambda f: order.get(f["_id"], len(order)))
    project["fragments"] = fragments
    return project


def dna_payload(db) -> dict:
    """DNA summary computed from the seed fragments."""
    fragments = list(
        db["fragments"].find(
            {"user_id": DEMO_USER_ID},
            {"emotions": 1, "themes": 1, "style": 1, "created_at": 1,
             "project_id": 1, "connection_types": 1},
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


@router.get("/fragments")
@limiter.limit("30/minute")
async def demo_fragments(request: Request, limit: int = 50):
    return await asyncio.to_thread(fragments_payload, get_db(), limit)


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

    # Private on purpose: a shared cache in front of the API stored a partial
    # (206) body and replayed it to every later full request.
    return await gcs_audio_response(fragment["audio_url"], range)


@router.get("/projects")
@limiter.limit("30/minute")
async def demo_projects(request: Request):
    return await asyncio.to_thread(projects_payload, get_db())


@router.get("/projects/{project_id}")
@limiter.limit("30/minute")
async def demo_project_detail(request: Request, project_id: str):
    oid = parse_object_id(project_id, "project_id")
    project = await asyncio.to_thread(project_detail_payload, get_db(), oid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/dna")
@limiter.limit("30/minute")
async def demo_dna(request: Request):
    return await asyncio.to_thread(dna_payload, get_db())
