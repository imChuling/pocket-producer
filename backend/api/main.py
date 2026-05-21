import os
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from google.genai import types
from pymongo import MongoClient

from .auth import verify_firebase_token

app = FastAPI(title="Pocket Producer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pocketproducer.app",
        "http://localhost:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

_mongo = None


def get_db():
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
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

    runner = get_runner()

    message = f"Process fragment for user_id={user_id}. "
    if audio_url:
        message += f"audio_url={audio_url}. "
    if text:
        message += f"text={text!r}. "

    try:
        if _is_remote:
            events = []
            async for event in runner.async_stream_query(
                user_id=user_id,
                message=message,
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
    except Exception:
        raise HTTPException(status_code=502, detail="Agent processing failed")


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
    from bson import ObjectId

    project = db["projects"].find_one({"_id": ObjectId(project_id), "user_id": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["_id"] = str(project["_id"])

    fragment_ids = [ObjectId(fid) for fid in project.get("fragment_ids", [])]
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
