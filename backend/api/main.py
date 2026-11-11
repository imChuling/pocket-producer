import asyncio
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

from .auth import verify_firebase_token
from .deps import (
    acquire_pipeline_slot,
    consume_daily_quota,
    debounced_dna_update,
    get_db,
    limiter,
    release_pipeline_slot,
    sanitize_creator_text,
)
from .pipeline import get_genai_client, process_fragment_background, validate_audio_upload
from .routes import (
    admin_router,
    demo_router,
    fragments_router,
    notifications_router,
    projects_router,
    ranking_router,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

def _warm_clap_in_background() -> None:
    # Loading msclap (torch import + 658 MB of weights) takes double-digit
    # seconds; doing it here keeps the first /session-embed request fast.
    # A daemon thread so startup readiness never waits on it.
    if os.environ.get("POCKET_ENABLE_CLAP") != "1":
        return

    def _load() -> None:
        try:
            from ranking.adapters import shared as clap

            if clap.get_msclap() is None:
                return
            clap.encode_text(["warmup"])
            logger.info("CLAP warmup complete")
            # role-gap-v1 encodes its role prompts on first use; do it now so
            # the first request does not pay for it inside the rank timeout.
            from api.routes.ranking import _service

            for adapter in _service._registry.adapters():
                ensure = getattr(adapter, "_ensure_probe", None)
                if ensure is not None:
                    ensure()
            logger.info("role probe warmup complete")
        except Exception:
            logger.exception("CLAP warmup failed — will retry on first request")

    threading.Thread(target=_load, name="clap-warmup", daemon=True).start()


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Warming up DB connection and Gemini client...")
    try:
        get_db()
        get_genai_client()
        logger.info("Warmup complete")
    except Exception:
        logger.exception("Warmup failed — will retry on first request")
    _warm_clap_in_background()
    yield


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Pocket Producer API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

_default_origins = [
    "https://pocketproducer.app",
    "https://pocketproducer.vercel.app",
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Mount route modules
app.include_router(fragments_router)
app.include_router(projects_router)
app.include_router(notifications_router)
app.include_router(admin_router)
app.include_router(ranking_router)
app.include_router(demo_router)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Dependency-level readiness: Mongo reachable, CLAP state, rankers registered.

    /health stays shallow for the startup probe; this is what monitoring and a
    human checking a deploy should look at. CLAP "loading" or "disabled" is
    reported, not treated as unready, because rules-v1 serves without it.
    """
    from api.routes.ranking import registered_models
    from ranking.adapters import shared as clap

    try:
        await asyncio.wait_for(asyncio.to_thread(get_db().command, "ping"), timeout=3.0)
        mongo = "ok"
    except Exception as error:
        mongo = f"error: {type(error).__name__}"
    models = registered_models()
    payload = {
        "mongo": mongo,
        "clap": clap.status(),
        "models": models,
        "fusion_registered": "fusion-5sig-v1" in models,
    }
    status_code = 200 if mongo == "ok" else 503
    return JSONResponse(payload, status_code=status_code)


# ---------------------------------------------------------------------------
# Ingest — the core ingestion endpoint stays in main.py
# ---------------------------------------------------------------------------

_background_tasks: set[asyncio.Task] = set()
PIPELINE_QUEUE_SECONDS = 900


@app.post("/api/ingest", status_code=202)
@limiter.limit("60/minute")
async def ingest_fragment(
    request: Request,
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    user_id: str = Depends(verify_firebase_token),
):
    sanitized_text, prompt_injection_flag = sanitize_creator_text(text)
    if prompt_injection_flag:
        logger.warning("Prompt injection pattern detected user=%s", user_id)
    if not file and not text:
        raise HTTPException(status_code=400, detail="Either file or text required")
    if text is not None and not sanitized_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    await asyncio.to_thread(consume_daily_quota, get_db(), user_id, "ingest")

    audio_url = None
    upload_meta = None
    if file:
        upload_meta = await validate_audio_upload(file)
        from ._clients import get_gcs_client
        gcs_client = get_gcs_client()
        bucket = gcs_client.bucket(os.environ["GCS_BUCKET"])
        safe_name = Path(file.filename or "audio.webm").name
        blob_name = f"{user_id}/{uuid.uuid4()}-{safe_name}"
        blob = bucket.blob(blob_name)
        await asyncio.to_thread(
            blob.upload_from_file, file.file, content_type=file.content_type
        )
        audio_url = f"gs://{os.environ['GCS_BUCKET']}/{blob_name}"

    db = get_db()
    frag_type = "audio" if audio_url else "text"

    title = None
    if frag_type == "audio" and file:
        original_name = file.filename or ""
        if original_name.startswith("recording."):
            count = await asyncio.to_thread(
                db["fragments"].count_documents,
                {"user_id": user_id, "type": "audio"},
            )
            title = f"Audio fragment {count + 1}"
        else:
            title = original_name.rsplit(".", 1)[0] if "." in original_name else original_name

    fragment_doc = {
        "user_id": user_id,
        "type": frag_type,
        "title": title,
        "text": sanitized_text or None,
        "raw_text": sanitized_text or None,
        "audio_url": audio_url,
        "upload": upload_meta,
        "prompt_injection_flag": prompt_injection_flag,
        "tags": [],
        "emotions": [],
        "themes": [],
        "status": "processing",
        "created_at": datetime.now(UTC),
    }
    result = await asyncio.to_thread(db["fragments"].insert_one, fragment_doc)
    fragment_id = str(result.inserted_id)

    async def _ingest_pipeline():
        # A batch import can queue dozens of fragments behind the pipeline
        # slots; waiting is cheap, so queue for a long time and say so in
        # the status instead of failing the upload.
        queued_note_written = False
        for elapsed in range(PIPELINE_QUEUE_SECONDS):
            if await acquire_pipeline_slot():
                break
            if elapsed == 3 and not queued_note_written:
                queued_note_written = True
                await asyncio.to_thread(
                    db["fragments"].update_one,
                    {"_id": result.inserted_id},
                    {"$set": {"pipeline_step": "Queued behind other uploads..."}},
                )
            await asyncio.sleep(1)
        else:
            logger.error("Pipeline slot timeout for fragment %s", fragment_id)
            await asyncio.to_thread(
                db["fragments"].update_one,
                {"_id": result.inserted_id},
                {"$set": {"status": "error", "pipeline_step": "error"}},
            )
            return
        try:
            await process_fragment_background(user_id, fragment_id, audio_url, sanitized_text)
        finally:
            await release_pipeline_slot()
        await debounced_dna_update(user_id)

    def _on_task_done(t):
        _background_tasks.discard(t)
        if not t.cancelled() and t.exception():
            logger.error("Ingest pipeline failed: %s", t.exception())

    task = asyncio.create_task(_ingest_pipeline())
    _background_tasks.add(task)
    task.add_done_callback(_on_task_done)

    return {
        "fragment_id": fragment_id,
        "status": "processing",
        "message": "Fragment saved. Agent processing in background.",
    }
