import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import verify_firebase_token
from ..deps import get_db, limiter, parse_object_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
@limiter.limit("30/minute")
async def list_notifications(request: Request, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    notifications = list(
        db["notifications"]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(20)
    )
    for n in notifications:
        n["_id"] = str(n["_id"])
        if not n.get("sleeping_project_title") and n.get("sleeping_project_id"):
            proj = db["projects"].find_one(
                {"_id": ObjectId(n["sleeping_project_id"]), "user_id": user_id},
                {"title": 1},
            )
            if proj:
                n["sleeping_project_title"] = proj.get("title", "")
    unread = sum(1 for n in notifications if not n.get("read"))
    return {"notifications": notifications, "unread_count": unread}


@router.post("/{notification_id}/read")
@limiter.limit("60/minute")
async def mark_notification_read(
    request: Request, notification_id: str, user_id: str = Depends(verify_firebase_token)
):
    db = get_db()
    oid = parse_object_id(notification_id, "notification_id")
    result = db["notifications"].update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"updated": True}


@router.post("/read-all")
@limiter.limit("10/minute")
async def mark_all_notifications_read(
    request: Request, user_id: str = Depends(verify_firebase_token)
):
    db = get_db()
    db["notifications"].update_many(
        {"user_id": user_id, "read": False}, {"$set": {"read": True}}
    )
    return {"updated": True}
