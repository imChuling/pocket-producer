import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import verify_firebase_token
from ..deps import get_db, limiter, parse_object_id

logger = logging.getLogger(__name__)

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
