import asyncio
import logging
import uuid
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request
from pydantic import BaseModel
from pymongo import ReturnDocument

from ..analysis_status import analysis_stalled
from ..auth import verify_firebase_token
from ..deps import (
    acquire_pipeline_slot,
    debounced_dna_update,
    get_db,
    limiter,
    parse_object_id,
    release_pipeline_slot,
    sanitize_creator_text,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fragments", tags=["fragments"])

# Bounded per-fragment records of the user's own edits.
TITLE_HISTORY_LIMIT = 10
TAG_EDITS_LIMIT = 20

_background_tasks: set[asyncio.Task] = set()


@router.get("/{fragment_id}/status-stream")
async def fragment_status_stream(
    request: Request,
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    from starlette.responses import StreamingResponse

    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")

    async def _sse():
        last_step = None
        for _ in range(120):
            if await request.is_disconnected():
                break
            frag = await asyncio.to_thread(
                db["fragments"].find_one,
                {"_id": oid, "user_id": user_id},
                {"status": 1, "pipeline_step": 1, "project_id": 1, "project_title": 1},
            )
            if not frag:
                yield "data: {}\n\n"
                break
            step = frag.get("pipeline_step", "")
            status = frag.get("status", "processing")
            if step != last_step:
                last_step = step
                import json as _json
                payload = {"step": step, "status": status}
                if frag.get("project_title"):
                    payload["project_title"] = frag["project_title"]
                yield f"data: {_json.dumps(payload)}\n\n"
            if status in ("ready", "error") or step == "done":
                break
            await asyncio.sleep(1.5)

    return StreamingResponse(
        _sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("")
@limiter.limit("30/minute")
async def list_fragments(
    request: Request,
    user_id: str = Depends(verify_firebase_token),
    limit: int = Query(50, ge=1, le=200),
    before: str | None = Query(None, max_length=80),
):
    db = get_db()
    query = {"user_id": user_id}
    if before is not None:
        try:
            timestamp, object_id = before.split("|")
            if not ObjectId.is_valid(object_id):
                raise ValueError
            created = datetime.fromisoformat(timestamp) if timestamp else None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid fragment cursor") from exc
        older = [{"created_at": created, "_id": {"$lt": ObjectId(object_id)}}]
        if created is not None:
            older.extend([{"created_at": {"$lt": created}}, {"created_at": None}])
        query["$or"] = older

    # Use the id to break ties when several recordings share a timestamp.
    fragments = await asyncio.to_thread(
        lambda: list(
            db["fragments"]
            .find(query, {"embedding": 0, "edit_history": 0, "representations": 0})
            .sort([("created_at", -1), ("_id", -1)])
            .limit(limit + 1)
        )
    )
    next_cursor = None
    if len(fragments) > limit:
        fragments.pop()
        last = fragments[-1]
        created = last.get("created_at")
        next_cursor = f"{created.isoformat() if created else ''}|{last['_id']}"
    now = datetime.now(UTC)
    for fragment in fragments:
        fragment["_id"] = str(fragment["_id"])
        fragment["analysis_stalled"] = analysis_stalled(fragment, now)
    return {"fragments": fragments, "next_cursor": next_cursor}


@router.get("/{fragment_id}")
@limiter.limit("60/minute")
async def get_fragment(request: Request, fragment_id: str, user_id: str = Depends(verify_firebase_token)):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": oid, "user_id": user_id},
        {"embedding": 0},
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
    current = await asyncio.to_thread(
        db["fragments"].find_one, {"_id": oid, "user_id": user_id}, {"title": 1}
    )
    if current is None:
        raise HTTPException(status_code=404, detail="Fragment not found")
    new_title = title.strip()
    update: dict = {"$set": {"title": new_title}}
    if current.get("title") and current["title"] != new_title:
        # Kept so the app can take the user's own naming into account.
        update["$push"] = {"title_history": {
            "$each": [{"from": current["title"], "to": new_title, "at": datetime.now(UTC)}],
            "$slice": -TITLE_HISTORY_LIMIT,
        }}
        update["$addToSet"] = {"user_edited_fields": "title"}
    await asyncio.to_thread(db["fragments"].update_one, {"_id": oid, "user_id": user_id}, update)
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
        cleaned_notes, _ = sanitize_creator_text(trimmed)
        result = await asyncio.to_thread(
            db["fragments"].update_one,
            {"_id": oid, "user_id": user_id},
            {"$set": {"notes": cleaned_notes}},
        )
    else:
        cleaned_notes = None
        result = await asyncio.to_thread(
            db["fragments"].update_one,
            {"_id": oid, "user_id": user_id},
            {"$unset": {"notes": ""}},
        )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")

    if cleaned_notes:
        frag = await asyncio.to_thread(
            db["fragments"].find_one,
            {"_id": oid, "user_id": user_id},
            {"embedding": 1, "emotions": 1, "themes": 1, "tags": 1},
        )
        if frag and frag.get("embedding"):
            import time

            from ..pipeline import memory_and_project
            tag_for_project = {
                "emotions": frag.get("emotions", []),
                "themes": frag.get("themes", []),
                "tags": frag.get("tags", []),
            }

            async def _reeval():
                try:
                    await memory_and_project(
                        db, user_id, str(oid), frag["embedding"], tag_for_project, time.monotonic(),
                    )
                    await debounced_dna_update(user_id)
                except Exception:
                    logger.exception("Project re-evaluation after notes failed for %s", fragment_id)

            task = asyncio.create_task(_reeval())
            _background_tasks.add(task)
            task.add_done_callback(lambda t: _background_tasks.discard(t))

    return {"updated": True}


class CommentRequest(BaseModel):
    text: str


MAX_COMMENTS_PER_FRAGMENT = 50


async def _schedule_project_reeval(db, user_id: str, oid: ObjectId, fragment_id: str) -> None:
    """Re-run memory/project grouping in the background after intent changed."""
    frag = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": oid, "user_id": user_id},
        {"embedding": 1, "emotions": 1, "themes": 1, "tags": 1},
    )
    if not frag or not frag.get("embedding"):
        return
    import time

    from ..pipeline import memory_and_project

    tag_for_project = {
        "emotions": frag.get("emotions", []),
        "themes": frag.get("themes", []),
        "tags": frag.get("tags", []),
    }

    async def _reeval():
        try:
            await memory_and_project(
                db, user_id, fragment_id, frag["embedding"], tag_for_project, time.monotonic(),
            )
            await debounced_dna_update(user_id)
        except Exception:
            logger.exception("Project re-evaluation after comment failed for %s", fragment_id)

    task = asyncio.create_task(_reeval())
    _background_tasks.add(task)
    task.add_done_callback(lambda t: _background_tasks.discard(t))


@router.post("/{fragment_id}/comments")
@limiter.limit("30/minute")
async def add_fragment_comment(
    request: Request,
    fragment_id: str,
    body: CommentRequest,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    trimmed = body.text.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="Comment text is empty")
    if len(trimmed) > 2000:
        raise HTTPException(status_code=400, detail="Comment too long (max 2000 chars)")

    fragment = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": oid, "user_id": user_id},
        {"comments": 1},
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    if len(fragment.get("comments", [])) >= MAX_COMMENTS_PER_FRAGMENT:
        raise HTTPException(status_code=400, detail="Comment limit reached")

    cleaned_text, _ = sanitize_creator_text(trimmed)
    comment = {
        "id": uuid.uuid4().hex,
        "text": cleaned_text,
        "created_at": datetime.now(UTC),
    }
    await asyncio.to_thread(
        db["fragments"].update_one,
        {"_id": oid, "user_id": user_id},
        {"$push": {"comments": comment}},
    )

    await _schedule_project_reeval(db, user_id, oid, str(oid))

    comment["created_at"] = comment["created_at"].isoformat()
    return {"added": True, "comment": comment}


@router.post("/{fragment_id}/comments/{comment_id}/delete")
@limiter.limit("30/minute")
async def delete_fragment_comment(
    request: Request,
    fragment_id: str,
    comment_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    result = await asyncio.to_thread(
        db["fragments"].update_one,
        {"_id": oid, "user_id": user_id},
        {"$pull": {"comments": {"id": comment_id}}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"deleted": result.modified_count > 0}


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
    fragment = await asyncio.to_thread(
        db["fragments"].find_one, {"_id": oid, "user_id": user_id}
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    update = body.model_dump(exclude_none=True)
    if not update:
        return {"updated": False, "message": "No fields to update"}

    # What the user added to or removed from each list, so the app can take
    # their own vocabulary into account.
    tag_edits = []
    for field in ("tags", "emotions", "style"):
        if field in update:
            before = set(fragment.get(field) or [])
            after = set(update[field] or [])
            if before != after:
                tag_edits.append({
                    "field": field,
                    "added": sorted(after - before),
                    "removed": sorted(before - after),
                    "at": datetime.now(UTC),
                })
    operation = {"$set": update, "$addToSet": {"user_edited_fields": {"$each": list(update)}}}
    if tag_edits:
        operation["$push"] = {"tag_edits": {"$each": tag_edits, "$slice": -TAG_EDITS_LIMIT}}
    saved = await asyncio.to_thread(
        db["fragments"].find_one_and_update,
        {"_id": oid, "user_id": user_id}, operation,
        return_document=ReturnDocument.AFTER,
        projection={"user_edited_fields": 1},
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"updated": True, "user_edited_fields": saved["user_edited_fields"]}


def _delete_fragment_sync(db, oid, user_id, fragment_id):
    """Delete a fragment and clean up project references and GCS audio."""
    fragment = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id}, {"audio_url": 1}
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    result = db["fragments"].delete_one({"_id": oid, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")

    projects = db["projects"]
    affected_ids = [
        row["_id"] for row in projects.find({"user_id": user_id, "fragment_ids": fragment_id}, {"_id": 1})
    ]
    if affected_ids:
        affected = {"user_id": user_id, "_id": {"$in": affected_ids}}
        result = projects.update_many(
            affected,
            {"$pull": {"fragment_ids": fragment_id, "audiotool_insertions": {"fragment_id": fragment_id}}},
        )
        logger.info("Removed fragment %s from %d project(s)", fragment_id, result.modified_count)
        projects.delete_many({**affected, "fragment_ids": {"$size": 0}})

    audio_url = fragment.get("audio_url")
    if audio_url and audio_url.startswith("gs://"):
        try:
            bucket_name, blob_name = audio_url.replace("gs://", "").split("/", 1)
            from api._clients import get_gcs_client
            get_gcs_client().bucket(bucket_name).blob(blob_name).delete()
        except Exception:
            logger.warning("Failed to delete GCS object for fragment %s", fragment_id)


@router.post("/{fragment_id}/delete")
@limiter.limit("20/minute")
async def delete_fragment(
    request: Request,
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    await asyncio.to_thread(_delete_fragment_sync, db, oid, user_id, fragment_id)
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
    fragment = await asyncio.to_thread(
        db["fragments"].find_one, {"_id": oid, "user_id": user_id}
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    new_text, prompt_injection_flag = sanitize_creator_text(body.text)
    if not new_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    old_text = fragment.get("text", "")
    if old_text == new_text:
        return {"updated": False, "message": "No change"}

    if not await acquire_pipeline_slot():
        raise HTTPException(429, "Too many fragments processing, please try again shortly")

    revision = str(uuid.uuid4())
    try:
        while fragment:
            edited = fragment.get("user_edited_fields") or []
            if fragment.get("text") == new_text:
                await release_pipeline_slot()
                return {"updated": False, "message": "No change"}
            acoustic = _acoustic_estimates(fragment.get("audio_features") or {})
            history_entry = {
                "id": revision,
                "text": fragment.get("text") or "",
                "edited_at": datetime.now(UTC).isoformat(),
            }
            # If another edit wins, reread its text and tags before saving this one.
            result = await asyncio.to_thread(
                db["fragments"].update_one,
                {"_id": oid, "user_id": user_id, "text": fragment.get("text"),
                 "analysis_revision": fragment.get("analysis_revision"),
                 "user_edited_fields": fragment.get("user_edited_fields")},
                {
                    "$push": {"edit_history": {"$each": [history_entry], "$slice": -50}},
                    "$set": {
                        **{key: default for key, default in (_TEXT_TAG_DEFAULTS | acoustic).items()
                           if key not in edited},
                        "text": new_text,
                        "analysis_revision": revision,
                        "analysis_kind": "edited_text",
                        "status": "processing",
                        "pipeline_step": "Starting analysis...",
                        "analysis_started_at": datetime.now(UTC),
                        "prompt_injection_flag": prompt_injection_flag,
                        "user_edited_fields": list(dict.fromkeys([*edited, "text"])),
                    },
                    "$unset": {"embedding": ""},
                },
            )
            if result.matched_count:
                break
            fragment = await asyncio.to_thread(
                db["fragments"].find_one, {"_id": oid, "user_id": user_id},
            )
        else:
            raise HTTPException(status_code=404, detail="Fragment not found")
    except BaseException:
        await release_pipeline_slot()
        raise

    from ..pipeline import tag_fragment_direct

    def _on_task_done(t):
        _background_tasks.discard(t)
        if not t.cancelled() and t.exception():
            logger.error("Edit-text re-analysis failed: %s", t.exception())

    task = asyncio.create_task(
        _reanalyze_fragment_text(user_id, str(oid), new_text, tag_fragment_direct, revision, acoustic)
    )
    _background_tasks.add(task)
    task.add_done_callback(_on_task_done)

    return {"updated": True, "text": new_text}


_TEXT_TAG_DEFAULTS = {
    "tags": [], "emotions": [], "themes": [], "style": [],
    "structure_hint": None, "potential": None, "key": None, "bpm": None, "suggestion": None,
}


def _acoustic_estimates(features: dict) -> dict:
    values = {}
    if features.get("bpm"):
        values["bpm"] = features["bpm"]
    if features.get("estimated_key"):
        suffix = "m" if features.get("estimated_mode") == "minor" else ""
        values["key"] = features["estimated_key"] + suffix
    return values


async def _reanalyze_fragment_text(user_id, fragment_id, new_text, tag_fragment_direct, revision, acoustic):
    try:
        await _analyze_edited_text(user_id, fragment_id, new_text, tag_fragment_direct, revision, acoustic)
    finally:
        await release_pipeline_slot()


async def _analyze_edited_text(user_id, fragment_id, new_text, tagger, revision, acoustic):
    import time

    from tools.edit_context import user_edit_context
    from tools.embedding import generate_embedding

    from ..pipeline import memory_and_project
    from ..pipeline.processing import save_analysis_fields

    db = get_db()
    current = {"_id": ObjectId(fragment_id), "user_id": user_id, "analysis_revision": revision}
    try:
        context = await asyncio.to_thread(user_edit_context, db, user_id, "tagging")
        tags, embedding = await asyncio.gather(
            tagger(new_text, user_context=context),
            generate_embedding(new_text),
            return_exceptions=True,
        )
        fields = {k: tags[k] for k in _TEXT_TAG_DEFAULTS if isinstance(tags, dict) and k in tags}
        tagged = bool(fields)
        embedded = isinstance(embedding, list) and bool(embedding)
        fields.update(acoustic)
        if embedded:
            fields["embedding"] = embedding
        complete = tagged and embedded
        fields["status"] = "ready" if complete else "error"
        fields["pipeline_step"] = "done" if complete else "error"
        if not await asyncio.to_thread(save_analysis_fields, db, current, fields):
            return
    except Exception:
        logger.exception("Re-analysis failed for fragment %s", fragment_id)
        await asyncio.to_thread(
            db["fragments"].update_one, current,
            {"$set": {"status": "error", "pipeline_step": "error"}},
        )
        return

    if complete:
        try:
            await memory_and_project(db, user_id, fragment_id, embedding, tags, time.monotonic())
        except Exception:
            logger.exception("Project grouping after text edit failed for %s", fragment_id)
    await debounced_dna_update(user_id)


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
    result = await asyncio.to_thread(
        db["fragments"].update_one,
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
    db = get_db()
    oid = parse_object_id(fragment_id, "fragment_id")
    fragment = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": oid, "user_id": user_id},
        {"audio_url": 1},
    )
    if not fragment or not fragment.get("audio_url"):
        raise HTTPException(status_code=404, detail="Audio not found")

    return await gcs_audio_response(fragment["audio_url"], range)


def parse_byte_range(header: str, size: int) -> tuple[int, int]:
    """First and last byte of a single `bytes=` range, clamped to the file.

    Supports `start-end`, `start-` and the suffix form `-N` (the last N
    bytes). A range that starts past the end of the file, or ends before it
    starts, is unsatisfiable: 416 with `Content-Range: bytes */<size>`.
    """
    unsatisfiable = HTTPException(
        status_code=416,
        detail="Requested range not satisfiable",
        headers={"Content-Range": f"bytes */{size}"},
    )
    spec = header.strip()
    if not spec.startswith("bytes=") or "," in spec:
        raise unsatisfiable
    start_str, sep, end_str = spec[len("bytes="):].strip().partition("-")
    try:
        if not sep:
            raise ValueError
        if not start_str:
            suffix = int(end_str)
            if suffix <= 0:
                raise unsatisfiable
            return max(size - suffix, 0), size - 1
        start = int(start_str)
        end = int(end_str) if end_str else size - 1
    except ValueError:
        raise unsatisfiable from None
    if start < 0 or start >= size or end < start:
        raise unsatisfiable
    return start, min(end, size - 1)


async def gcs_audio_response(
    gcs_uri: str, range: str | None, cache_control: str = "private, max-age=3600"
):
    from fastapi.responses import StreamingResponse

    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name, blob_name = parts[0], parts[1]

    from api._clients import get_gcs_client
    blob = get_gcs_client().bucket(bucket_name).blob(blob_name)
    await asyncio.to_thread(blob.reload)
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
        range_start, range_end = parse_byte_range(range, file_size)
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
                "Cache-Control": cache_control,
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
            "Cache-Control": cache_control,
        },
    )


@router.post("/{fragment_id}/reanalyze")
@limiter.limit("6/minute")
async def reanalyze_fragment(
    request: Request,
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    from ..pipeline import process_fragment_background, tag_fragment_direct

    oid = parse_object_id(fragment_id, "fragment_id")

    db = get_db()
    frag = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": oid, "user_id": user_id},
        {"audio_url": 1, "audio_features": 1, "text": 1, "user_edited_fields": 1,
         "analysis_revision": 1, "analysis_kind": 1, "status": 1},
    )
    if not frag:
        raise HTTPException(404, "Fragment not found")

    if not await acquire_pipeline_slot():
        raise HTTPException(429, "Too many fragments processing, please try again shortly")

    # A failed note edit can reuse the recording's tempo and key on retry.
    retry_note = frag.get("status") == "error" and frag.get("analysis_kind") != "full"
    edited_text = "text" in (frag.get("user_edited_fields") or []) and (
        not frag.get("audio_url") or retry_note
    )
    revision = str(uuid.uuid4())
    current = {"_id": oid, "user_id": user_id, "analysis_revision": revision}
    try:
        claimed = await asyncio.to_thread(
            db["fragments"].update_one,
            {**current, "analysis_revision": frag.get("analysis_revision")},
            {"$set": {"status": "processing", "pipeline_step": "Starting analysis...",
                      "analysis_started_at": datetime.now(UTC),
                      "analysis_kind": "edited_text" if edited_text else "full",
                      "analysis_revision": revision}},
        )
        if not claimed.matched_count:
            raise HTTPException(409, "Fragment changed. Retry analysis.")
    except BaseException:
        await release_pipeline_slot()
        raise

    import json as _json

    from starlette.responses import StreamingResponse

    async def _stream():
        try:
            yield _json.dumps({"status": "processing", "fragment_id": fragment_id}) + "\n"
            if edited_text:
                analysis = _analyze_edited_text(
                    user_id, fragment_id, frag["text"], tag_fragment_direct, revision,
                    _acoustic_estimates(frag.get("audio_features") or {}),
                )
            else:
                analysis = process_fragment_background(user_id, fragment_id, frag.get("audio_url"),
                                                       frag.get("text"), revision)
            work = asyncio.ensure_future(analysis)
            try:
                while True:
                    try:
                        await asyncio.wait_for(asyncio.shield(work), timeout=10)
                        break
                    except TimeoutError:
                        yield _json.dumps({"status": "heartbeat"}) + "\n"
                if not edited_text:
                    await debounced_dna_update(user_id)
                saved = await asyncio.to_thread(db["fragments"].find_one, current, {"status": 1})
                status = "done" if saved and saved.get("status") == "ready" else "error"
                yield _json.dumps({"status": status, "fragment_id": fragment_id}) + "\n"
            except Exception:
                if not work.done():
                    work.cancel()
                await asyncio.to_thread(
                    db["fragments"].update_one, {**current, "status": "processing"},
                    {"$set": {"status": "error", "pipeline_step": "error"}},
                )
                logger.exception("Reanalyze failed for %s", fragment_id)
                yield _json.dumps({"status": "error", "fragment_id": fragment_id}) + "\n"
        finally:
            await release_pipeline_slot()

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
    fragment = await asyncio.to_thread(
        db["fragments"].find_one,
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
        "mcp_read_tools_enabled": os.environ.get("ENABLE_MCP_MEMORY_TOOLS") != "0",
        "result": result,
    }
