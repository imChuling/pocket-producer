import asyncio
import json
import logging
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import verify_firebase_token
from ..deps import get_db, limiter, parse_object_id

logger = logging.getLogger(__name__)


class CompleteActionRequest(BaseModel):
    note: str = ""  # optional: what the creator did

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
@limiter.limit("30/minute")
async def list_projects(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    projects = list(
        db["projects"].find({"user_id": user_id}).sort([("rescue_score", -1), ("_id", -1)]).limit(50)
    )
    for p in projects:
        p["_id"] = str(p["_id"])
    return {"projects": projects}


@router.get("/{project_id}")
@limiter.limit("30/minute")
async def get_project(request: Request, project_id: str, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    oid = parse_object_id(project_id, "project_id")
    project = db["projects"].find_one({"_id": oid, "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["_id"] = str(project["_id"])

    fragment_ids = project.get("fragment_ids", [])
    if fragment_ids:
        oids = [ObjectId(fid) for fid in fragment_ids if ObjectId.is_valid(fid)]
        fragments = list(
            db["fragments"].find({"_id": {"$in": oids}, "user_id": user_id}, {"embedding": 0})
        )
        for f in fragments:
            f["_id"] = str(f["_id"])
        project["fragments"] = fragments
    else:
        project["fragments"] = []

    return project


@router.post("/{project_id}/complete-action")
@limiter.limit("10/minute")
async def complete_action(
    request: Request,
    project_id: str,
    body: CompleteActionRequest,
    user_id: str = Depends(verify_firebase_token),
):
    """Mark the current next_action as done, refresh score, generate a new action."""
    db = get_db()
    oid = parse_object_id(project_id, "project_id")
    project = db["projects"].find_one({"_id": oid, "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    old_action = project.get("next_action")

    # Archive the completed action
    db["projects"].update_one(
        {"_id": oid, "user_id": user_id},
        {
            "$push": {
                "completed_actions": {
                    "action": old_action,
                    "note": body.note,
                    "completed_at": datetime.now(UTC),
                }
            },
            "$set": {"last_activity_at": datetime.now(UTC)},
        },
    )

    # Refresh score (freshness will improve since last_activity_at just updated)
    from tools.rescue_score import compute_rescue_score

    frag_ids = [ObjectId(fid) for fid in project.get("fragment_ids", []) if ObjectId.is_valid(str(fid))]
    fragments = list(db["fragments"].find({"_id": {"$in": frag_ids}, "user_id": user_id}, {"embedding": 0}))
    score_data = compute_rescue_score(fragments, project_id)

    # Generate a new next action
    from api.pipeline import _generate_next_action

    new_action = await _generate_next_action(db, user_id, project_id)

    db["projects"].update_one(
        {"_id": oid, "user_id": user_id},
        {
            "$set": {
                "rescue_score": score_data.get("rescue_score"),
                "score_breakdown": score_data.get("components"),
                "next_action": new_action,
            }
        },
    )

    return {
        "completed": old_action,
        "new_action": new_action,
        "rescue_score": score_data.get("rescue_score"),
    }


@router.post("/{project_id}/skip-action")
@limiter.limit("10/minute")
async def skip_action(
    request: Request,
    project_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    """Skip the current next_action and generate a different one."""
    db = get_db()
    oid = parse_object_id(project_id, "project_id")
    project = db["projects"].find_one({"_id": oid, "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from api.pipeline import _generate_next_action

    new_action = await _generate_next_action(db, user_id, project_id)

    db["projects"].update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"next_action": new_action}},
    )

    return {"new_action": new_action}
