import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from ..auth import verify_firebase_token
from ..deps import get_db, limiter, parse_object_id

logger = logging.getLogger(__name__)


class CompleteActionRequest(BaseModel):
    note: str = ""  # optional: what the creator did


class AudiotoolLinkRequest(BaseModel):
    audiotool_project_id: str
    display_name: str = ""
    fragment_id: str
    insertion_id: str | None = Field(default=None, min_length=1)


class AudiotoolUnlinkRequest(BaseModel):
    audiotool_project_id: str
    fragment_id: str
    insertion_id: str | None = Field(default=None, min_length=1)


router = APIRouter(prefix="/api/projects", tags=["projects"])

SKIPPED_ACTIONS_LIMIT = 20


@router.get("")
@limiter.limit("30/minute")
async def list_projects(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    projects = await asyncio.to_thread(
        lambda: list(
            db["projects"].find({"user_id": user_id}).sort([("rescue_score", -1), ("_id", -1)]).limit(50)
        )
    )
    for p in projects:
        p["_id"] = str(p["_id"])
    return {"projects": projects}


def _link_audiotool_sync(db, user_id, body):
    source = {"_id": parse_object_id(body.fragment_id, "fragment_id"), "user_id": user_id}
    if db["fragments"].find_one(source, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="Fragment not found")
    result = _change_audiotool_placement(db, user_id, body, link=True)
    # A concurrent library deletion may have cleaned its mirrors before this write.
    if db["fragments"].find_one(source, {"_id": 1}) is None:
        _change_audiotool_placement(db, user_id, body, link=False)
        raise HTTPException(status_code=404, detail="Fragment not found")
    return result


def _create_audiotool_project(projects, session, placement, title, now):
    # Mongo's unique _id serializes simultaneous first inserts across API workers.
    # Pre-existing mirrors retain their original ObjectId and title.
    key = json.dumps([session["user_id"], session["audiotool_project_id"]]).encode()
    project_id = ObjectId(hashlib.sha256(key).digest()[:12])
    projects.insert_one({
        **session,
        "_id": project_id,
        "title": title,
        "fragment_ids": [placement["fragment_id"]],
        "audiotool_insertions": [placement],
        "connection_reasons": ["Inserted into this Audiotool session"],
        "connection_types": ["audiotool_session"],
        "sections": [],
        "rescue_score": None,
        "last_activity_at": now,
        "created_at": now,
    })
    return {"project_id": str(project_id), "title": title}


def _change_audiotool_placement(db, user_id, body, *, link):
    projects = db["projects"]
    session = {"user_id": user_id, "audiotool_project_id": body.audiotool_project_id}
    placement = {"fragment_id": body.fragment_id, "insertion_id": body.insertion_id}
    if link:
        title = f"Audiotool: {body.display_name.strip() or body.audiotool_project_id}"[:80]
    for _ in range(32):
        project = projects.find_one(session)
        now = datetime.now(UTC)
        if project is None:
            if not link:
                return {"unlinked": False}
            try:
                return _create_audiotool_project(projects, session, placement, title, now)
            except DuplicateKeyError:
                continue

        placements = list(project.get("audiotool_insertions") or [])
        recorded = {p["fragment_id"] for p in placements}
        # A fragment-only record represents one legacy membership. Older clients can
        # still add/remove that membership alongside independently addressable regions.
        placements.extend(
            {"fragment_id": fid, "insertion_id": None}
            for fid in project.get("fragment_ids", []) if fid not in recorded
        )
        if link:
            response = {"project_id": str(project["_id"]), "title": project.get("title", title)}
            if placement in placements:
                return response
            placements.append(placement)
        else:
            if placement not in placements:
                return {"unlinked": False}
            placements.remove(placement)
            response = {"unlinked": True, "project_deleted": not placements}

        # Condition both mutation paths on the snapshot. Racing additions, removals or
        # fragment deletions force a fresh read before we write or delete the mirror.
        snapshot = {
            **session,
            "_id": project["_id"],
            "fragment_ids": project.get("fragment_ids"),
            "audiotool_insertions": project.get("audiotool_insertions"),
        }
        if placements:
            members = list(dict.fromkeys(p["fragment_id"] for p in placements))
            saved = projects.update_one(snapshot, {"$set": {
                "fragment_ids": members, "audiotool_insertions": placements, "last_activity_at": now,
            }}).matched_count
        else:
            saved = projects.delete_one(snapshot).deleted_count
        if saved:
            return response
    raise HTTPException(status_code=503, detail="Concurrent project update. Please retry.")


@router.post("/audiotool-session")
@limiter.limit("30/minute")
async def link_audiotool_fragment(
    request: Request,
    body: AudiotoolLinkRequest,
    user_id: str = Depends(verify_firebase_token),
):
    """Record an Audiotool insertion in the Projects view.

    Finds or creates the project mirroring this Audiotool session and adds
    the inserted fragment to its fragment_ids.  The fragment document is
    left untouched: stamping project_id on it would make the capture
    pipeline's duplicate-group guard reuse the session project for
    thematic grouping.
    """
    db = get_db()
    return await asyncio.to_thread(_link_audiotool_sync, db, user_id, body)


def _unlink_audiotool_sync(db, user_id, body):
    return _change_audiotool_placement(db, user_id, body, link=False)


@router.post("/audiotool-session/unlink")
@limiter.limit("30/minute")
async def unlink_audiotool_fragment(
    request: Request,
    body: AudiotoolUnlinkRequest,
    user_id: str = Depends(verify_firebase_token),
):
    """Undo the project-side record of an Audiotool insertion.

    Removes one placement. The fragment stays visible while another placement remains.
    The final removal deletes the empty mirror.
    """
    db = get_db()
    return await asyncio.to_thread(_unlink_audiotool_sync, db, user_id, body)


@router.get("/{project_id}")
@limiter.limit("30/minute")
async def get_project(request: Request, project_id: str, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    oid = parse_object_id(project_id, "project_id")

    def _sync():
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

    return await asyncio.to_thread(_sync)


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
    project = await asyncio.to_thread(
        db["projects"].find_one, {"_id": oid, "user_id": user_id}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    old_action = project.get("next_action")

    await asyncio.to_thread(
        db["projects"].update_one,
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

    from tools.rescue_score import compute_rescue_score

    frag_ids = [ObjectId(fid) for fid in project.get("fragment_ids", []) if ObjectId.is_valid(str(fid))]
    fragments = await asyncio.to_thread(
        lambda: list(db["fragments"].find({"_id": {"$in": frag_ids}, "user_id": user_id}, {"embedding": 0}))
    )
    score_data = compute_rescue_score(fragments, project_id)

    from api.pipeline import _generate_next_action

    new_action = await _generate_next_action(db, user_id, project_id)

    await asyncio.to_thread(
        db["projects"].update_one,
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
    project = await asyncio.to_thread(
        db["projects"].find_one, {"_id": oid, "user_id": user_id}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from api.pipeline import _generate_next_action

    # Recorded before generating the replacement, so the new suggestion can
    # take this skip into account.
    skipped = project.get("next_action")
    if skipped:
        await asyncio.to_thread(
            db["projects"].update_one,
            {"_id": oid, "user_id": user_id},
            {"$push": {"skipped_actions": {
                "$each": [{"action": skipped, "skipped_at": datetime.now(UTC)}],
                "$slice": -SKIPPED_ACTIONS_LIMIT,
            }}},
        )

    new_action = await _generate_next_action(db, user_id, project_id)

    await asyncio.to_thread(
        db["projects"].update_one,
        {"_id": oid, "user_id": user_id},
        {"$set": {"next_action": new_action}},
    )

    return {"new_action": new_action}
