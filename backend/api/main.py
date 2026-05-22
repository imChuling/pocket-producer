import asyncio
import logging
import os
import uuid

from bson import ObjectId
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from google.genai import types
from pymongo import MongoClient

from tools.embedding import generate_embedding

from .auth import verify_firebase_token

logger = logging.getLogger(__name__)

app = FastAPI(title="Pocket Producer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pocketproducer.app",
        "http://localhost:3000",
        "https://pocket-producer-25253422868.us-central1.run.app",
    ],
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/ingest")
async def ingest_fragment(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    user_id: str = Depends(verify_firebase_token),
):
    """Ingest a new fragment (audio and/or text)."""
    if not file and not text:
        raise HTTPException(status_code=400, detail="Either file or text required")

    audio_url = None
    if file:
        client = storage.Client()
        bucket = client.bucket(os.environ["GCS_BUCKET"])
        blob_name = f"{user_id}/{uuid.uuid4()}-{file.filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.file, content_type=file.content_type)
        audio_url = f"gs://{os.environ['GCS_BUCKET']}/{blob_name}"

    embed_text = text or ""
    if embed_text:
        embedding = generate_embedding(embed_text)
    else:
        embedding = None

    runner = get_runner()

    message = f"Process fragment for user_id={user_id}. "
    if audio_url:
        message += f"audio_url={audio_url}. "
    if text:
        message += f"text={text!r}. "

    try:
        result = await asyncio.wait_for(
            _run_agent(runner, user_id, message),
            timeout=120.0,
        )
        result["embedding_generated"] = embedding is not None
        return result
    except TimeoutError:
        logger.error("Agent processing timed out for user %s", user_id)
        raise HTTPException(status_code=504, detail="Agent processing timed out")
    except Exception as exc:
        logger.exception("Agent processing failed: %s", exc)
        raise HTTPException(status_code=502, detail="Agent processing failed")


async def _run_agent(runner, user_id: str, message: str) -> dict:
    if _is_remote:
        events = []
        async for event in runner.async_stream_query(
            user_id=user_id, message=message,
        ):
            events.append(event)
        return {"events": events}

    session = await runner.session_service.create_session(
        app_name="pocket_producer", user_id=user_id,
    )
    content = types.Content(
        role="user", parts=[types.Part(text=message)],
    )
    result = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            result = event.content.parts[0].text
    return {"result": result}


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
    fragment = db["fragments"].find_one(
        {"_id": ObjectId(fragment_id), "user_id": user_id}, {"embedding": 0}
    )
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    fragment["_id"] = str(fragment["_id"])
    return fragment


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
    project = db["projects"].find_one({"_id": ObjectId(project_id), "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["_id"] = str(project["_id"])

    fragment_ids = [ObjectId(f) for f in project.get("fragment_ids", [])]
    fragments = list(db["fragments"].find({"_id": {"$in": fragment_ids}}, {"embedding": 0}))
    for f in fragments:
        f["_id"] = str(f["_id"])
    project["fragments"] = fragments
    return project


@app.get("/api/dna")
async def get_dna(user_id: str = Depends(verify_firebase_token)):
    """Get Creative DNA insights for the current user."""
    db = get_db()
    dna = db["user_dna"].find_one({"user_id": user_id})
    if dna:
        dna["_id"] = str(dna["_id"])
    return dna or {}


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
    if authorization and authorization.startswith("Bearer "):
        try:
            from google.auth.transport import requests as gauth_requests
            from google.oauth2 import id_token

            token = authorization[7:]
            id_token.verify_oauth2_token(
                token, gauth_requests.Request(),
            )
            return
        except Exception:
            pass
    raise HTTPException(status_code=403, detail="Unauthorized")
