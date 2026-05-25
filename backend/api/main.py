import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from google.genai import types
from pymongo import MongoClient

from .auth import verify_firebase_token

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan: warm up runner + DB on startup so first request isn't cold
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Warming up runner and DB connection...")
    try:
        get_db()
        get_runner()
        logger.info("Warmup complete")
    except Exception:
        logger.exception("Warmup failed — will retry on first request")
    yield


app = FastAPI(title="Pocket Producer API", version="0.1.0", lifespan=lifespan)

_default_origins = [
    "https://pocketproducer.app",
    "http://localhost:3000",
    "https://pocket-producer-25253422868.us-central1.run.app",
]
_env_origins = os.environ.get("CORS_ORIGINS")
_cors_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

_mongo = None


def get_db():
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.environ["MONGODB_CONNECTION_STRING"], maxPoolSize=10)
    return _mongo["pocketproducer"]


_runner = None
_is_remote = False


def get_runner():
    global _runner, _is_remote
    if _runner is not None:
        return _runner

    resource_name = os.environ.get("PRODUCER_RESOURCE_NAME")
    if resource_name:
        import vertexai
        from vertexai import agent_engines

        vertexai.init(
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ.get("GOOGLE_CLOUD_REGION", "us-central1"),
        )
        _runner = agent_engines.get(resource_name)
        _is_remote = True
    else:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        from agents.producer import producer_agent

        _runner = Runner(
            agent=producer_agent,
            app_name="pocket_producer",
            session_service=InMemorySessionService(),
        )
        _is_remote = False
    return _runner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_object_id(value: str, label: str = "ID") -> ObjectId:
    """Parse and validate an ObjectId string."""
    try:
        return ObjectId(value)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail=f"Invalid {label}: {value}")


def _try_parse_agent_json(text: str) -> dict | None:
    """Try to extract a JSON object from the agent's response text."""
    import json
    import re

    if not text:
        return None
    # Agent may wrap JSON in ```json ... ``` markdown blocks
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1)
    # Try to find a JSON object in the text
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    return None


# Background task tracking (simple in-memory for MVP)
_background_tasks: dict[str, dict] = {}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ingest — decoupled: save immediately, process in background
# ---------------------------------------------------------------------------

@app.post("/api/ingest", status_code=202)
async def ingest_fragment(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    user_id: str = Depends(verify_firebase_token),
):
    """Ingest a new fragment. Saves to DB immediately, processes via Agent in background."""
    if not file and not text:
        raise HTTPException(status_code=400, detail="Either file or text required")

    audio_url = None
    if file:
        gcs_client = storage.Client()
        bucket = gcs_client.bucket(os.environ["GCS_BUCKET"])
        blob_name = f"{user_id}/{uuid.uuid4()}-{file.filename}"
        blob = bucket.blob(blob_name)
        await asyncio.to_thread(
            blob.upload_from_file, file.file, content_type=file.content_type
        )
        audio_url = f"gs://{os.environ['GCS_BUCKET']}/{blob_name}"

    # Save a minimal fragment immediately so the UI can show it
    db = get_db()
    frag_type = "audio" if audio_url else "text"

    # Generate title for audio fragments
    title = None
    if frag_type == "audio" and file:
        original_name = file.filename or ""
        # Uploaded file → use filename without extension
        # Recording → filename is like "recording.webm", give it a number
        if original_name.startswith("recording."):
            count = db["fragments"].count_documents(
                {"user_id": user_id, "type": "audio"}
            )
            title = f"Audio fragment {count + 1}"
        else:
            title = original_name.rsplit(".", 1)[0] if "." in original_name else original_name

    fragment_doc = {
        "user_id": user_id,
        "type": frag_type,
        "title": title,
        "text": text or None,
        "raw_text": text or None,
        "audio_url": audio_url,
        "tags": [],
        "emotions": [],
        "themes": [],
        "status": "processing",
        "created_at": datetime.now(UTC),
    }
    result = db["fragments"].insert_one(fragment_doc)
    fragment_id = str(result.inserted_id)

    # Fire-and-forget background Agent processing
    asyncio.create_task(
        _process_fragment_background(user_id, fragment_id, audio_url, text)
    )

    return {
        "fragment_id": fragment_id,
        "status": "processing",
        "message": "Fragment saved. Agent processing in background.",
    }


async def _process_fragment_background(
    user_id: str, fragment_id: str, audio_url: str | None, text: str | None
):
    """Fast path: direct Gemini call + embedding, no multi-agent overhead."""
    import json
    import time

    from tools.embedding import generate_embedding

    db = get_db()
    t0 = time.monotonic()
    try:
        # --- Phase 1: audio pre-processing (parallel, skip for text) ---
        transcript = None
        features = None
        if audio_url:
            from tools.audio_features import extract_audio_features
            from tools.transcription import transcribe_audio

            logger.info("Pre-processing audio for %s", fragment_id)
            transcript_result, features_result = await asyncio.gather(
                transcribe_audio(audio_url),
                extract_audio_features(audio_url),
                return_exceptions=True,
            )
            if not isinstance(transcript_result, Exception):
                transcript = transcript_result
            else:
                logger.warning("Transcription failed: %s", transcript_result)
            if not isinstance(features_result, Exception):
                features = features_result
            else:
                logger.warning("Audio features failed: %s", features_result)
            logger.info("Audio pre-processing done in %.1fs", time.monotonic() - t0)

        fragment_text = text or transcript or ""

        # --- Phase 2: single Gemini call for tagging + embedding in parallel ---
        tag_task = _tag_fragment_direct(fragment_text, features)
        embed_task = generate_embedding(fragment_text) if fragment_text else None

        if embed_task:
            tag_result, embedding = await asyncio.gather(tag_task, embed_task)
        else:
            tag_result = await tag_task
            embedding = None

        # If no text was available (pure audio, transcription failed), build
        # an embedding from the tag result so Memory phase can still work.
        if not embedding and tag_result:
            tag_text_parts = []
            for k in ("emotions", "themes", "tags", "style"):
                vals = tag_result.get(k, [])
                if isinstance(vals, list) and vals:
                    tag_text_parts.extend(vals)
            if tag_result.get("suggestion"):
                tag_text_parts.append(tag_result["suggestion"])
            if tag_text_parts:
                try:
                    embedding = await generate_embedding(" ".join(tag_text_parts))
                    logger.info("Generated embedding from tags for %s", fragment_id)
                except Exception:
                    logger.warning("Tag-based embedding failed for %s", fragment_id)

        # --- Phase 3: write everything back to the fragment ---
        final_update: dict = {"status": "ready"}
        if transcript:
            final_update["raw_text"] = transcript
            # Only set text for text-type fragments, not audio
            # Audio fragments show as "Audio fragment" with key/BPM in the UI
        if text:
            final_update["text"] = text
        if features:
            final_update["audio_features"] = features
        if embedding:
            final_update["embedding"] = embedding
        if tag_result:
            for key in ("tags", "emotions", "themes", "style"):
                if key in tag_result and isinstance(tag_result[key], list):
                    final_update[key] = tag_result[key]
            if tag_result.get("key"):
                final_update["key"] = tag_result["key"]
            if tag_result.get("bpm"):
                final_update["bpm"] = tag_result["bpm"]
            if tag_result.get("suggestion"):
                final_update["suggestion"] = tag_result["suggestion"]
            if tag_result.get("structure_hint"):
                final_update["structure_hint"] = tag_result["structure_hint"]
            if tag_result.get("potential"):
                final_update["potential"] = tag_result["potential"]

        db["fragments"].update_one(
            {"_id": ObjectId(fragment_id)}, {"$set": final_update}
        )
        logger.info(
            "Fragment %s tagged in %.1fs (tags=%s)",
            fragment_id, time.monotonic() - t0,
            tag_result.get("tags") if tag_result else "none",
        )

        # --- Phase 4: Memory + Project auto-grouping ---
        if embedding:
            try:
                await _memory_and_project(
                    db, user_id, fragment_id, embedding, tag_result, t0
                )
            except Exception:
                logger.exception("Memory/project phase failed for %s", fragment_id)

    except Exception:
        logger.exception("Processing failed for fragment %s", fragment_id)
        db["fragments"].update_one(
            {"_id": ObjectId(fragment_id)},
            {"$set": {"status": "error"}},
        )


async def _tag_fragment_direct(text: str, audio_features: object = None) -> dict | None:
    """Single Gemini call for tagging — no agent overhead."""
    import json

    from google import genai

    features_str = ""
    if audio_features:
        features_str = f"\nAudio features: {json.dumps(audio_features, default=str)}"

    prompt = f"""You are an experienced music producer assistant. Analyze this music fragment and return ONLY a JSON object.

Fragment text: {text!r}{features_str}

Return JSON with these fields:
- "emotions": list of 1-3 emotions from: [wonder, transcendence, tenderness, nostalgia, peacefulness, joyful_activation, power, tension, sadness, bittersweet, defiance, longing, melancholy, energetic, dreamy, hopeful]. Order strongest first.
- "themes": list of 1-3 themes (noun-phrase topics, e.g. "love", "night city", "journey", "solitude", "freedom", "identity", "heartbreak")
- "tags": list of 2-4 descriptive tags (e.g. "melody", "chord progression", "beat", "lyric", "hook idea", "vocal riff")
- "structure_hint": one of ["verse_candidate", "chorus_candidate", "hook_candidate", "bridge_candidate", "intro_candidate", "outro_candidate", "interlude_candidate", "near_complete_demo"] or null. Infer from text patterns (repetition=chorus, narrative=verse, tonal shift=bridge) and audio duration if available.
- "style": list of 0-2 style tags ONLY if confident (e.g. "lo-fi", "indie folk", "trap", "R&B", "ambient"). Empty list if unsure.
- "potential": "high" (specific imagery + structural clarity + emotional coherence), "medium" (clear emotion but lacks specificity), or "low" (generic/very short/vague)
- "key": musical key if detectable (e.g. "Em", "C#m", "Bb"), null otherwise
- "bpm": BPM if detectable, null otherwise
- "suggestion": a concrete, actionable next-step for the creator (1-2 sentences in the same language as the fragment). Be specific to THIS fragment. Examples: "Try layering a soft pad underneath to fill out the low end", "This lyric has strong imagery — consider building a verse melody in Am around it".

ONLY output the JSON object, no markdown, no explanation."""

    try:
        client = genai.Client(vertexai=True)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        result_text = response.text.strip()
        parsed = _try_parse_agent_json(result_text)
        return parsed
    except Exception:
        logger.exception("Direct tagging failed")
        return None


async def _memory_and_project(
    db, user_id: str, fragment_id: str,
    embedding: list[float], tag_result: dict | None, t0: float,
):
    """Phase 4: vector search → relationship classification → project grouping."""
    import json
    import time

    from google import genai
    from tools.rescue_score import compute_rescue_score

    # 4a. Vector search for similar fragments (skip self)
    pipeline = [
        {
            "$vectorSearch": {
                "index": "fragment_vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 100,
                "limit": 6,
                "filter": {"user_id": user_id},
            }
        },
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"embedding": 0}},
    ]
    neighbors = list(db["fragments"].aggregate(pipeline))
    # Remove self from results
    neighbors = [n for n in neighbors if str(n["_id"]) != fragment_id]

    if not neighbors:
        logger.info("No neighbors for %s — creating solo project later if needed", fragment_id)
        return

    # 4b. Check if any high-scoring neighbor already belongs to a project
    best = neighbors[0]
    best_score = best.get("score", 0)

    # If similarity is too low, skip project grouping
    if best_score < 0.75:
        logger.info(
            "Best neighbor score %.3f < 0.75 for %s — no project match",
            best_score, fragment_id,
        )
        return

    # 4c. Decide: join existing project or create new one
    target_project_id = best.get("project_id")
    project_fragments = []

    if target_project_id:
        # Join existing project
        project = db["projects"].find_one({"_id": ObjectId(target_project_id)})
        if project:
            # Add fragment to project
            db["projects"].update_one(
                {"_id": ObjectId(target_project_id)},
                {
                    "$addToSet": {"fragment_ids": fragment_id},
                    "$set": {"last_activity_at": datetime.now(UTC)},
                },
            )
            db["fragments"].update_one(
                {"_id": ObjectId(fragment_id)},
                {"$set": {
                    "project_id": target_project_id,
                    "project_title": project.get("title", ""),
                }},
            )
            # Load all project fragments for rescue score
            frag_ids = [ObjectId(fid) for fid in project.get("fragment_ids", [])]
            frag_ids.append(ObjectId(fragment_id))
            project_fragments = list(db["fragments"].find(
                {"_id": {"$in": frag_ids}}, {"embedding": 0}
            ))
            logger.info(
                "Fragment %s joined project %s (score=%.3f)",
                fragment_id, target_project_id, best_score,
            )
    else:
        # Best neighbor has no project — create a new project with both
        neighbor_id = str(best["_id"])
        # Use Gemini to generate a project title from the two fragments
        frag_text = tag_result.get("themes", []) if tag_result else []
        neighbor_themes = best.get("themes", [])
        all_themes = frag_text + neighbor_themes
        all_emotions = (tag_result.get("emotions", []) if tag_result else []) + best.get("emotions", [])

        project_title = await _generate_project_title(all_themes, all_emotions)

        new_project = {
            "user_id": user_id,
            "title": project_title,
            "fragment_ids": [neighbor_id, fragment_id],
            "sections": [],
            "rescue_score": None,
            "last_activity_at": datetime.now(UTC),
            "created_at": datetime.now(UTC),
        }
        result = db["projects"].insert_one(new_project)
        new_project_id = str(result.inserted_id)

        # Tag both fragments with project info
        db["fragments"].update_many(
            {"_id": {"$in": [ObjectId(neighbor_id), ObjectId(fragment_id)]}},
            {"$set": {
                "project_id": new_project_id,
                "project_title": project_title,
            }},
        )

        project_fragments = list(db["fragments"].find(
            {"_id": {"$in": [ObjectId(neighbor_id), ObjectId(fragment_id)]}},
            {"embedding": 0},
        ))
        target_project_id = new_project_id
        logger.info(
            "Created project '%s' (%s) from fragments %s + %s (score=%.3f)",
            project_title, new_project_id, fragment_id, neighbor_id, best_score,
        )

    # 4d. Compute rescue score + sections + next_action
    if project_fragments and target_project_id:
        score_data = compute_rescue_score(
            project_fragments, target_project_id
        )
        # Collect sections from structure_hints
        sections = list({
            f.get("structure_hint", "").replace("_candidate", "").replace("_", " ")
            for f in project_fragments
            if f.get("structure_hint")
        })
        # Generate next_action via quick Gemini call
        next_action = await _generate_next_action(
            project_fragments, score_data, sections
        )
        project_update = {
            "rescue_score": score_data.get("rescue_score"),
            "score_breakdown": score_data.get("components"),
            "sections": sections,
        }
        if next_action:
            project_update["next_action"] = next_action
        db["projects"].update_one(
            {"_id": ObjectId(target_project_id)},
            {"$set": project_update},
        )
        logger.info(
            "Project %s updated: score=%s sections=%s (total %.1fs)",
            target_project_id,
            score_data.get("rescue_score"),
            sections,
            time.monotonic() - t0,
        )


async def _generate_project_title(
    themes: list[str], emotions: list[str]
) -> str:
    """Generate a short creative project title from themes and emotions."""
    from google import genai

    context = f"themes: {themes}, emotions: {emotions}"
    prompt = f"""Generate a short, evocative project title (2-4 words) for a music project with these characteristics:
{context}

The title should feel like a working album/song title — poetic but not pretentious.
Return ONLY the title, nothing else."""

    try:
        client = genai.Client(vertexai=True)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        title = response.text.strip().strip('"').strip("'")
        return title[:60] if title else "Untitled Project"
    except Exception:
        logger.exception("Project title generation failed")
        # Fallback: use first theme or emotion
        if themes:
            return themes[0].title()
        if emotions:
            return emotions[0].title()
        return "Untitled Project"


async def _generate_next_action(
    fragments: list[dict], score_data: dict, sections: list[str]
) -> dict | None:
    """Generate a concrete next action for the project."""
    from google import genai

    frag_summary = []
    for f in fragments[:6]:
        info = f.get("type", "text")
        if f.get("text"):
            info += f': "{f["text"][:80]}"'
        if f.get("emotions"):
            info += f" [{', '.join(f['emotions'][:2])}]"
        if f.get("structure_hint"):
            info += f" ({f['structure_hint']})"
        frag_summary.append(info)

    tier = score_data.get("tier", "low")
    score = score_data.get("rescue_score")

    prompt = f"""You are a music producer. A creator has a project with these fragments:
{chr(10).join('- ' + s for s in frag_summary)}

Sections so far: {sections if sections else 'none'}
Rescue score: {score}/100 (tier: {tier})

Give ONE specific, actionable next step the creator can do in ≤30 minutes to move this project forward. Consider what's missing structurally.

Return ONLY a JSON object: {{"action": "...", "estimated_time": "15 min"}}
The action should be 1-2 sentences, specific and practical. Use the same language as the fragment content."""

    try:
        client = genai.Client(vertexai=True)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        parsed = _try_parse_agent_json(response.text.strip())
        if parsed and "action" in parsed:
            return parsed
    except Exception:
        logger.exception("Next action generation failed")
    return None


async def _run_agent(runner, user_id: str, message: str) -> dict:
    import time

    if _is_remote:
        result = None
        async for event in runner.async_stream_query(
            user_id=user_id, message=message,
        ):
            if isinstance(event, dict):
                content = event.get("content")
                if content:
                    parts = content.get("parts", [])
                    result = parts[0].get("text") if parts else str(content)
            elif hasattr(event, "content") and event.content:
                result = event.content
        if result is None:
            logger.warning("Agent produced no response for user %s (remote)", user_id)
        return {"result": result}

    t0 = time.monotonic()
    logger.info("Creating session for user %s", user_id)
    session = await runner.session_service.create_session(
        app_name="pocket_producer", user_id=user_id,
    )
    logger.info("Session created in %.1fs, starting agent run", time.monotonic() - t0)

    content = types.Content(
        role="user", parts=[types.Part(text=message)],
    )
    result = None
    event_count = 0
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=content,
    ):
        event_count += 1
        elapsed = time.monotonic() - t0
        # Log agent/tool events for debugging
        agent_name = getattr(event, "author", "?")
        is_final = event.is_final_response() if hasattr(event, "is_final_response") else False
        has_content = bool(event.content and event.content.parts) if hasattr(event, "content") else False
        actions = ""
        if hasattr(event, "content") and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    actions += f" call:{part.function_call.name}"
                if hasattr(part, "function_response") and part.function_response:
                    actions += f" resp:{part.function_response.name}"
        logger.info(
            "Event #%d [%.1fs] agent=%s final=%s content=%s%s",
            event_count, elapsed, agent_name, is_final, has_content, actions,
        )
        if is_final and has_content:
            result = event.content.parts[0].text

    logger.info(
        "Agent run complete: %d events in %.1fs, result=%s",
        event_count, time.monotonic() - t0, "yes" if result else "no",
    )
    if result is None:
        logger.warning("Agent produced no response for user %s (local)", user_id)
    return {"result": result}


# ---------------------------------------------------------------------------
# Fragment endpoints
# ---------------------------------------------------------------------------

@app.get("/api/fragments")
async def list_fragments(
    user_id: str = Depends(verify_firebase_token),
    limit: int = 50,
):
    """List recent fragments for the current user."""
    db = get_db()
    fragments = list(
        db["fragments"]
        .find({"user_id": user_id}, {"embedding": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    for f in fragments:
        f["_id"] = str(f["_id"])
    return {"fragments": fragments}


@app.get("/api/fragments/{fragment_id}")
async def get_fragment(fragment_id: str, user_id: str = Depends(verify_firebase_token)):
    """Get a single fragment by ID."""
    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id}, {"embedding": 0}
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    fragment["_id"] = str(fragment["_id"])
    return fragment


@app.post("/api/fragments/{fragment_id}/title")
async def update_fragment_title(
    fragment_id: str,
    title: str = Form(...),
    user_id: str = Depends(verify_firebase_token),
):
    """Update a fragment's title."""
    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
    result = db["fragments"].update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"title": title.strip()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"updated": True}


@app.post("/api/fragments/{fragment_id}/delete")
async def delete_fragment(fragment_id: str, user_id: str = Depends(verify_firebase_token)):
    """Delete a single fragment by ID."""
    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
    result = db["fragments"].delete_one({"_id": oid, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"deleted": True}


@app.get("/api/fragments/{fragment_id}/audio")
async def stream_audio(fragment_id: str, user_id: str = Depends(verify_firebase_token)):
    """Stream audio file from GCS for playback."""
    from fastapi.responses import StreamingResponse

    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id}, {"audio_url": 1}
    )
    if not fragment or not fragment.get("audio_url"):
        raise HTTPException(status_code=404, detail="Audio not found")

    gcs_uri = fragment["audio_url"]  # gs://bucket/path
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name, blob_name = parts[0], parts[1]

    gcs_client = storage.Client()
    blob = gcs_client.bucket(bucket_name).blob(blob_name)
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Audio file not found in storage")

    # Guess content type from extension
    ext = blob_name.rsplit(".", 1)[-1].lower() if "." in blob_name else ""
    content_types = {
        "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4",
        "webm": "audio/webm", "ogg": "audio/ogg", "flac": "audio/flac",
    }
    content_type = content_types.get(ext, "audio/mpeg")

    def stream():
        with blob.open("rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------

@app.get("/api/projects")
async def list_projects(user_id: str = Depends(verify_firebase_token)):
    """List all projects for the current user."""
    db = get_db()
    projects = list(
        db["projects"].find({"user_id": user_id}).sort("rescue_score", -1).limit(50)
    )
    for p in projects:
        p["_id"] = str(p["_id"])
    return {"projects": projects}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str, user_id: str = Depends(verify_firebase_token)):
    """Get a single project with its fragments."""
    db = get_db()
    oid = _parse_object_id(project_id, "project_id")
    project = db["projects"].find_one({"_id": oid, "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["_id"] = str(project["_id"])

    fragment_ids = [ObjectId(f) for f in project.get("fragment_ids", [])]
    fragments = list(db["fragments"].find({"_id": {"$in": fragment_ids}}, {"embedding": 0}))
    for f in fragments:
        f["_id"] = str(f["_id"])
    project["fragments"] = fragments
    return project


# ---------------------------------------------------------------------------
# DNA / Jobs
# ---------------------------------------------------------------------------

@app.get("/api/dna")
async def get_dna(user_id: str = Depends(verify_firebase_token)):
    """Get Creative DNA insights for the current user."""
    db = get_db()
    dna = db["user_dna"].find_one({"user_id": user_id})
    if dna:
        dna["_id"] = str(dna["_id"])
    return dna or {}


@app.post("/api/reprocess-projects")
async def reprocess_projects(user_id: str = Depends(verify_firebase_token)):
    """One-time: run Memory+Project phase on existing fragments that have embeddings but no project."""
    import time

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
    processed = 0
    for frag in fragments:
        frag_id = str(frag["_id"])
        embedding = frag.get("embedding")
        if not embedding:
            continue
        tag_result = {
            "emotions": frag.get("emotions", []),
            "themes": frag.get("themes", []),
            "tags": frag.get("tags", []),
        }
        try:
            await _memory_and_project(db, user_id, frag_id, embedding, tag_result, t0)
            processed += 1
        except Exception:
            logger.exception("Reprocess failed for %s", frag_id)

    # Also run DNA insights inline
    from jobs.dna_insights import run as run_dna
    await asyncio.to_thread(run_dna)

    return {"message": f"Processed {processed} fragments", "processed": processed}


@app.post("/api/jobs/dna")
async def trigger_dna_job(
    authorization: str = Header(None),
):
    """Trigger DNA insights aggregation. Called by Cloud Scheduler or manually."""
    _verify_job_auth(authorization)
    from jobs.dna_insights import run
    run()
    return {"status": "completed"}


@app.post("/api/jobs/resurrect")
async def trigger_resurrect_job(
    authorization: str = Header(None),
):
    """Trigger resurrect notifier. Called by Cloud Scheduler or manually."""
    _verify_job_auth(authorization)
    from jobs.resurrect import run
    run()
    return {"status": "completed"}


def _verify_job_auth(authorization: str | None):
    """Verify job trigger auth via shared secret or OIDC token."""
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
