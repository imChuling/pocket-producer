"""Read-only demo endpoint: serves seed account data without authentication."""

import asyncio

from fastapi import APIRouter, Request

from ..deps import get_db, limiter

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_USER_ID = "demo-seed-user"


@router.get("/fragments")
@limiter.limit("30/minute")
async def demo_fragments(request: Request, limit: int = 50):
    db = get_db()
    fragments = await asyncio.to_thread(
        lambda: list(
            db["fragments"]
            .find(
                {"user_id": DEMO_USER_ID},
                {"embedding": 0, "representations": 0, "edit_history": 0},
            )
            .sort("created_at", -1)
            .limit(limit)
        )
    )
    for f in fragments:
        f["_id"] = str(f["_id"])
    return {"fragments": fragments, "demo": True}


@router.get("/projects")
@limiter.limit("30/minute")
async def demo_projects(request: Request):
    db = get_db()
    projects = await asyncio.to_thread(
        lambda: list(
            db["projects"]
            .find({"user_id": DEMO_USER_ID}, {"embedding": 0})
            .sort("updated_at", -1)
            .limit(20)
        )
    )
    for p in projects:
        p["_id"] = str(p["_id"])
    return {"projects": projects, "demo": True}
