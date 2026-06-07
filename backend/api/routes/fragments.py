import asyncio
import logging
import uuid
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from google.cloud import storage
from pydantic import BaseModel

from ..auth import verify_firebase_token
from ..deps import get_db, limiter, parse_object_id, sanitize_creator_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fragments", tags=["fragments"])

_background_tasks: set[asyncio.Task] = set()


@router.get("")
@limiter.limit("30/minute")
async def list_fragments(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
    limit: int = 50,
):
    db = get_db()
    fragments = list(
        db["fragments"]
        .find({"user_id": user_id}, {"embedding": 0, "edit_history": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    for f in fragments:
        f["_id"] = str(f["_id"])
    return {"fragments": fragments}


@router.get("/{fragment_id}")
@limiter.limit("60/minute")
async def get_fragment(request: Request, fragment_id: str, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id}, {"embedding": 0}
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    fragment["_id"] = str(fragment["_id"])
    return fragment


@router.post("/{fragment_id}/title")
@limiter.limit("30/minute")
async def update_fragment_title(
    request: Request,
    fragment_id: str,
    title: str = Form(...),
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    result = db["fragments"].update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"title": title.strip()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"updated": True}


class NotesUpdateRequest(BaseModel):
    notes: str


@router.post("/{fragment_id}/notes")
@limiter.limit("30/minute")
async def update_fragment_notes(
    request: Request,
    fragment_id: str,
    body: NotesUpdateRequest,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    trimmed = body.notes.strip()
    if trimmed:
        result = db["fragments"].update_one(
            {"_id": oid, "user_id": user_id},
            {"$set": {"notes": sanitize_creator_text(trimmed)}},
        )
    else:
        result = db["fragments"].update_one(
            {"_id": oid, "user_id": user_id},
            {"$unset": {"notes": ""}},
        )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"updated": True}


class TagUpdateRequest(BaseModel):
    tags: list[str] | None = None
    emotions: list[str] | None = None
    potential: str | None = None
    structure_hint: str | None = None
    style: list[str] | None = None


@router.post("/{fragment_id}/tags")
@limiter.limit("30/minute")
async def update_fragment_tags(
    request: Request,
    fragment_id: str,
    body: TagUpdateRequest,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one({"_id": oid, "user_id": user_id})
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    update: dict = {}
    edited_fields: list[str] = list(fragment.get("user_edited_fields", []))

    if body.tags is not None:
        update["tags"] = body.tags
        if "tags" not in edited_fields:
            edited_fields.append("tags")
    if body.emotions is not None:
        update["emotions"] = body.emotions
        if "emotions" not in edited_fields:
            edited_fields.append("emotions")
    if body.potential is not None:
        update["potential"] = body.potential
        if "potential" not in edited_fields:
            edited_fields.append("potential")
    if body.structure_hint is not None:
        update["structure_hint"] = body.structure_hint
        if "structure_hint" not in edited_fields:
            edited_fields.append("structure_hint")
    if body.style is not None:
        update["style"] = body.style
        if "style" not in edited_fields:
            edited_fields.append("style")

    if not update:
        return {"updated": False, "message": "No fields to update"}

    update["user_edited_fields"] = edited_fields
    db["fragments"].update_one({"_id": oid, "user_id": user_id}, {"$set": update})
    return {"updated": True, "user_edited_fields": edited_fields}


@router.post("/{fragment_id}/delete")
@limiter.limit("20/minute")
async def delete_fragment(
    request: Request,
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id}, {"audio_url": 1}
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    result = db["fragments"].delete_one({"_id": oid, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")

    # Remove this fragment from any projects that reference it
    pull_result = db["projects"].update_many(
        {"user_id": user_id, "fragment_ids": fragment_id},
        {"$pull": {"fragment_ids": fragment_id}},
    )
    if pull_result.modified_count:
        logger.info(
            "Removed fragment %s from %d project(s)", fragment_id, pull_result.modified_count
        )
        # Clean up empty projects (all fragments deleted)
        db["projects"].delete_many(
            {"user_id": user_id, "fragment_ids": {"$size": 0}},
        )

    audio_url = fragment.get("audio_url")
    if audio_url and audio_url.startswith("gs://"):
        try:
            bucket_name, blob_name = audio_url.replace("gs://", "").split("/", 1)
            storage.Client().bucket(bucket_name).blob(blob_name).delete()
        except Exception:
            logger.warning("Failed to delete GCS object for fragment %s", fragment_id)

    return {"deleted": True}


class TextEditRequest(BaseModel):
    text: str


@router.post("/{fragment_id}/edit-text")
@limiter.limit("20/minute")
async def edit_fragment_text(
    request: Request,
    fragment_id: str,
    body: TextEditRequest,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one({"_id": oid, "user_id": user_id})
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    new_text, prompt_injection_flag = sanitize_creator_text(body.text)
    if not new_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    old_text = fragment.get("text", "")
    if old_text == new_text:
        return {"updated": False, "message": "No change"}

    history_entry = {
        "id": str(uuid.uuid4()),
        "text": old_text,
        "edited_at": datetime.now(UTC).isoformat(),
    }

    edited_fields = list(fragment.get("user_edited_fields", []))
    if "text" not in edited_fields:
        edited_fields.append("text")

    db["fragments"].update_one(
        {"_id": oid, "user_id": user_id},
        {
            "$push": {"edit_history": {"$each": [history_entry], "$slice": -50}},
            "$set": {
                "text": new_text,
                "status": "processing",
                "prompt_injection_flag": prompt_injection_flag,
                "user_edited_fields": edited_fields,
            },
        },
    )

    from ..pipeline import tag_fragment_direct

    task = asyncio.create_task(_reanalyze_fragment_text(user_id, str(oid), new_text, tag_fragment_direct))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"updated": True, "text": new_text}


async def _reanalyze_fragment_text(user_id: str, fragment_id: str, new_text: str, tag_fragment_direct):
    from tools.embedding import generate_embedding

    db = get_db()
    oid = ObjectId(fragment_id)
    try:
        tag_task = tag_fragment_direct(new_text)
        embed_task = generate_embedding(new_text)
        tag_result, embedding = await asyncio.gather(tag_task, embed_task, return_exceptions=True)

        update: dict = {"status": "ready"}

        if isinstance(tag_result, dict):
            fragment = db["fragments"].find_one({"_id": oid, "user_id": user_id})
            edited_fields = fragment.get("user_edited_fields", []) if fragment else []
            for field in ["emotions", "themes", "tags", "structure_hint", "style", "potential", "key", "bpm", "suggestion"]:
                if field not in edited_fields and field in tag_result:
                    update[field] = tag_result[field]

        if not isinstance(embedding, Exception) and embedding:
            update["embedding"] = embedding

        db["fragments"].update_one({"_id": oid, "user_id": user_id}, {"$set": update})
        logger.info("Re-analysis complete for fragment %s", fragment_id)
    except Exception:
        logger.exception("Re-analysis failed for fragment %s", fragment_id)
        db["fragments"].update_one(
            {"_id": oid, "user_id": user_id},
            {"$set": {"status": "ready"}, "$unset": {"embedding": ""}},
        )


@router.post("/{fragment_id}/edit-history/{entry_id}/delete")
@limiter.limit("30/minute")
async def delete_edit_history_entry(
    request: Request,
    fragment_id: str,
    entry_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    result = db["fragments"].update_one(
        {"_id": oid, "user_id": user_id},
        {"$pull": {"edit_history": {"id": entry_id}}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"deleted": True}


@router.get("/{fragment_id}/audio")
@limiter.limit("60/minute")
async def stream_audio(
    request: Request,
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
    range: str | None = Header(None),
):
    from fastapi.responses import StreamingResponse

    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id}, {"audio_url": 1}
    )
    if not fragment or not fragment.get("audio_url"):
        raise HTTPException(status_code=404, detail="Audio not found")

    gcs_uri = fragment["audio_url"]
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name, blob_name = parts[0], parts[1]

    gcs_client = storage.Client()
    blob = gcs_client.bucket(bucket_name).blob(blob_name)
    blob.reload()
    file_size = blob.size
    if not file_size:
        raise HTTPException(status_code=404, detail="Audio file not found in storage")

    ext = blob_name.rsplit(".", 1)[-1].lower() if "." in blob_name else ""
    content_types = {
        "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4",
        "webm": "audio/webm", "ogg": "audio/ogg", "flac": "audio/flac",
    }
    content_type = content_types.get(ext, "audio/mpeg")

    if range:
        range_spec = range.replace("bytes=", "")
        range_start_str, range_end_str = range_spec.split("-", 1)
        range_start = int(range_start_str) if range_start_str else 0
        range_end = int(range_end_str) if range_end_str else file_size - 1
        range_end = min(range_end, file_size - 1)
        content_length = range_end - range_start + 1

        def stream_range():
            with blob.open("rb") as f:
                f.seek(range_start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(64 * 1024, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            stream_range(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {range_start}-{range_end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Cache-Control": "private, max-age=3600",
            },
        )

    def stream():
        with blob.open("rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.post("/{fragment_id}/reanalyze")
@limiter.limit("6/minute")
async def reanalyze_fragment(
    request: Request,
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    from ..pipeline import process_fragment_background

    db = get_db()
    frag = db["fragments"].find_one(
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"_id": 1, "audio_url": 1, "text": 1},
    )
    if not frag:
        raise HTTPException(404, "Fragment not found")

    db["fragments"].update_one(
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"$set": {"status": "processing"}},
    )

    import json as _json

    from starlette.responses import StreamingResponse

    async def _stream():
        yield _json.dumps({"status": "processing", "fragment_id": fragment_id}) + "\n"
        work = asyncio.ensure_future(
            process_fragment_background(user_id, fragment_id, frag.get("audio_url"), frag.get("text"))
        )
        try:
            while True:
                try:
                    await asyncio.wait_for(asyncio.shield(work), timeout=10)
                    break
                except asyncio.TimeoutError:
                    yield _json.dumps({"status": "heartbeat"}) + "\n"
            yield _json.dumps({"status": "done", "fragment_id": fragment_id}) + "\n"
        except Exception:
            if not work.done():
                work.cancel()
            frag_doc = db["fragments"].find_one(
                {"_id": ObjectId(fragment_id), "user_id": user_id}, {"status": 1}
            )
            if frag_doc and frag_doc.get("status") == "processing":
                db["fragments"].update_one(
                    {"_id": ObjectId(fragment_id), "user_id": user_id},
                    {"$set": {"status": "error"}},
                )
            logger.exception("Reanalyze failed for %s", fragment_id)
            yield _json.dumps({"status": "error", "fragment_id": fragment_id}) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@router.post("/{fragment_id}/group-with-agent")
@limiter.limit("6/minute")
async def group_fragment_with_agent_endpoint(
    request: Request,
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    import os

    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id},
        {"embedding": 1, "status": 1},
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    if not fragment.get("embedding"):
        raise HTTPException(status_code=400, detail="Fragment has no embedding yet")

    from agents import group_fragment_with_agents

    result = await group_fragment_with_agents(db, user_id, fragment_id)
    return {
        "fragment_id": fragment_id,
        "pipeline": "producer->memory",
        "mcp_read_tools_enabled": os.environ.get("ENABLE_MCP_MEMORY_TOOLS") == "1",
        "result": result,
    }
