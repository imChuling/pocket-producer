import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.extension import _rate_limit_exceeded_handler

from .auth import verify_firebase_token
from .deps import get_db, limiter, sanitize_creator_text
from .pipeline import get_genai_client, process_fragment_background, validate_audio_upload
from .routes import admin_router, fragments_router, notifications_router, projects_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Warming up DB connection and Gemini client...")
    try:
        get_db()
        get_genai_client()
        logger.info("Warmup complete")
    except Exception:
        logger.exception("Warmup failed — will retry on first request")
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
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

# Mount route modules
app.include_router(fragments_router)
app.include_router(projects_router)
app.include_router(notifications_router)
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ingest — the core ingestion endpoint stays in main.py
# ---------------------------------------------------------------------------

_background_tasks: set[asyncio.Task] = set()


@app.post("/api/ingest", status_code=202)
@limiter.limit("12/minute")
async def ingest_fragment(
    request: Request,
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    user_id: str = Depends(verify_firebase_token),
):
    sanitized_text, prompt_injection_flag = sanitize_creator_text(text)
    if prompt_injection_flag:
        logger.warning("Prompt injection pattern detected user=%s text=%s", user_id, (sanitized_text or "")[:100])
    if not file and not text:
        raise HTTPException(status_code=400, detail="Either file or text required")
    if text is not None and not sanitized_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    audio_url = None
    upload_meta = None
    if file:
        upload_meta = await validate_audio_upload(file)
        gcs_client = storage.Client()
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
    result = db["fragments"].insert_one(fragment_doc)
    fragment_id = str(result.inserted_id)

    task = asyncio.create_task(
        process_fragment_background(user_id, fragment_id, audio_url, sanitized_text)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "fragment_id": fragment_id,
        "status": "processing",
        "message": "Fragment saved. Agent processing in background.",
    }
