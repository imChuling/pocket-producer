import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from google.genai import types
from pydantic import BaseModel
from pymongo import MongoClient

from .auth import verify_firebase_token

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# Shared Gemini client (singleton)
_genai_client = None

def get_genai_client():
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(vertexai=True)
    return _genai_client

# ---------------------------------------------------------------------------
# Lifespan: warm up runner + DB on startup so first request isn't cold
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
    allow_methods=["*"],
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
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1)
    # Try json.loads on the full text first
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    # Find first '{' and try progressively larger slices
    start = text.find("{")
    if start == -1:
        return None
    for end in range(len(text), start, -1):
        if text[end - 1] == "}":
            try:
                result = json.loads(text[start:end])
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                continue
    return None


# ---------------------------------------------------------------------------
# Skill loader — injects music-tagging skill content as Gemini system context
# ---------------------------------------------------------------------------

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
_tagging_skill_cache: str | None = None


def _load_tagging_skill_context() -> str:
    """Load music-tagging skill files into a single system instruction string.

    Cached after first load. Includes:
    - SKILL.md (rules, principles, procedure)
    - emotion-taxonomy.md (20 emotion tags with definitions)
    - theme-taxonomy.md (24 theme categories with decision tree)
    - structure-hints.md (7 structure types with decision rules)
    - style-vocabulary.md (18 style tags with evidence criteria)
    - A selection of worked examples from tagging-examples.json
    """
    global _tagging_skill_cache
    if _tagging_skill_cache is not None:
        return _tagging_skill_cache

    skill_dir = _SKILLS_DIR / "music-tagging"
    parts: list[str] = []

    # Core rules and procedure
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8")
        # Strip the YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        parts.append(content)

    # Reference documents
    refs_dir = skill_dir / "references"
    for ref_name in [
        "emotion-taxonomy.md",
        "theme-taxonomy.md",
        "structure-hints.md",
        "style-vocabulary.md",
    ]:
        ref_path = refs_dir / ref_name
        if ref_path.exists():
            parts.append(ref_path.read_text(encoding="utf-8"))

    # Selected examples (include up to 10 representative ones)
    import json as _json

    examples_path = skill_dir / "assets" / "tagging-examples.json"
    if examples_path.exists():
        try:
            data = _json.loads(examples_path.read_text(encoding="utf-8"))
            examples = data.get("examples", [])
            # Pick a representative subset covering different categories
            selected_ids = [
                "ex-001",  # text lyric fragment (melancholy, hook)
                "ex-003",  # verse narrative (tenderness, family)
                "ex-005",  # pure humming, needs_user_input
                "ex-007",  # audio with lyrics (nostalgia, singer-songwriter)
                "ex-012",  # mixed signals ("I'm fine" in minor key)
                "ex-015",  # trap style hint
                "ex-018",  # anger/defiance, indie-rock
                "ex-022",  # non-English (Chinese)
                "ex-025",  # displacement theme
                "ex-028",  # anxiety, mental-health
            ]
            selected = [e for e in examples if e.get("id") in selected_ids]
            if selected:
                parts.append(
                    "# Worked Examples\n\n"
                    "These examples show how to apply the rules above. "
                    "Use them as calibration for ambiguous cases.\n\n"
                    + _json.dumps(selected, indent=2, ensure_ascii=False)
                )
        except Exception:
            pass  # Skip examples if loading fails

    _tagging_skill_cache = "\n\n---\n\n".join(parts)
    logger.info(
        "Loaded tagging skill context: %d chars", len(_tagging_skill_cache)
    )
    return _tagging_skill_cache


_background_tasks: set[asyncio.Task] = set()


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

    task = asyncio.create_task(
        _process_fragment_background(user_id, fragment_id, audio_url, text)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "fragment_id": fragment_id,
        "status": "processing",
        "message": "Fragment saved. Agent processing in background.",
    }


async def _process_fragment_background(
    user_id: str, fragment_id: str, audio_url: str | None, text: str | None
):
    """Fast path: direct Gemini multimodal call + embedding, no multi-agent overhead.

    For audio fragments: Gemini receives the actual audio file (multimodal) plus
    librosa-extracted features as supplementary numbers. No separate transcription
    step needed — Gemini hears the audio directly.

    For text fragments: Gemini receives text only with skill context.
    """
    import json
    import time

    from tools.embedding import generate_embedding

    db = get_db()
    t0 = time.monotonic()
    try:
        # --- Phase 1: audio feature extraction (skip transcription — Gemini hears directly) ---
        features = None
        if audio_url:
            from tools.audio_features import extract_audio_features

            logger.info("Extracting audio features for %s", fragment_id)
            try:
                features = await extract_audio_features(audio_url)
            except Exception as e:
                logger.warning("Audio features extraction failed: %s", e)
            logger.info("Audio pre-processing done in %.1fs", time.monotonic() - t0)

        # --- Phase 2: Gemini tagging (multimodal for audio) + embedding in parallel ---
        # For audio: pass GCS URI so Gemini hears the actual recording
        # For text: pass text directly
        tag_task = _tag_fragment_direct(
            text=text or "",
            audio_features=features,
            audio_gcs_uri=audio_url,  # Gemini will listen to this directly
        )

        # Start embedding generation in parallel if we have text
        embed_task = generate_embedding(text) if text else None

        if embed_task:
            tag_result, embedding = await asyncio.gather(tag_task, embed_task)
        else:
            tag_result = await tag_task
            embedding = None

        # For audio fragments: use Gemini's transcript (if returned) for embedding
        transcript = None
        if tag_result and tag_result.get("transcript"):
            transcript = tag_result.pop("transcript")  # Remove from tags, store separately

        # Generate embedding from transcript or tag-derived text if we don't have one yet
        if not embedding:
            embed_source = transcript  # Gemini's heard transcript
            if not embed_source and tag_result:
                # Fallback: build embedding from tag metadata
                tag_text_parts = []
                for k in ("emotions", "themes", "tags", "style"):
                    vals = tag_result.get(k, [])
                    if isinstance(vals, list) and vals:
                        tag_text_parts.extend(vals)
                if tag_result.get("suggestion"):
                    tag_text_parts.append(tag_result["suggestion"])
                embed_source = " ".join(tag_text_parts) if tag_text_parts else None

            if embed_source:
                try:
                    embedding = await generate_embedding(embed_source)
                    logger.info("Generated embedding from %s for %s",
                                "transcript" if transcript else "tags", fragment_id)
                except Exception:
                    logger.warning("Embedding generation failed for %s", fragment_id)

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


def _guess_audio_mime_type(gcs_uri: str) -> str:
    """Guess MIME type from GCS URI file extension."""
    ext = gcs_uri.rsplit(".", 1)[-1].lower() if "." in gcs_uri else ""
    mime_map = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
        "aac": "audio/aac",
        "opus": "audio/opus",
    }
    return mime_map.get(ext, "audio/webm")  # Default to webm (MediaRecorder default)


async def _tag_fragment_direct(
    text: str,
    audio_features: object = None,
    audio_gcs_uri: str | None = None,
) -> dict | None:
    """Gemini tagging with full skill context. Multimodal for audio fragments.

    When audio_gcs_uri is provided, Gemini receives the actual audio file and
    can hear melody, timbre, dynamics, vocal style — far richer than text alone.
    """
    import json

    # Load skill knowledge as system instruction (cached after first call)
    system_context = _load_tagging_skill_context()

    # Build the supplementary info string with interpretation hints
    features_str = ""
    if audio_features:
        features_str = (
            f"\nLibrosa-detected audio features: {json.dumps(audio_features, default=str)}"
            "\nInterpretation guide for enriched features:"
            "\n- energy_curve: RMS loudness over time segments (low→high = build-up, high→low = fade-out, spike = drop/climax)"
            "\n- brightness: spectral centroid in Hz (low <1500 = warm/dark/mellow, high >3000 = bright/harsh/crisp)"
            "\n- onset_density: note attacks per second (low <2 = sustained/ambient, high >6 = rhythmically dense/percussive)"
            "\n- estimated_mode: major/minor from chroma correlation (use YOUR ears to override if the audio tells you differently)"
        )

    # Construct the prompt based on whether we have audio
    if audio_gcs_uri:
        # Multimodal: Gemini will listen to the audio directly
        prompt_text = f"""Tag this music fragment. You are receiving the ACTUAL AUDIO recording — listen to it carefully.

Follow the tagging procedure from your system instructions exactly. Pay attention to:
- What you HEAR: melody, timbre, vocal style, dynamics, arrangement, rhythm feel
- Any lyrics or vocals you can make out
- The overall energy and emotional arc of the recording
{features_str}
{f'Additional text context from the creator: {text!r}' if text else ''}

Return ONLY a JSON object with these fields (flat structure, not nested):
- "emotions": list of 1-3 emotion tags from the emotion taxonomy. Order strongest first.
- "themes": list of 1-3 theme tags from the theme taxonomy. Empty [] if no discernible subject.
- "tags": list of 2-4 descriptive content tags (e.g. "melody", "chord progression", "lyric", "hook idea", "vocal riff", "beat sketch", "piano motif", "guitar riff").
- "structure_hint": one value from the structure hints reference, or null.
- "style": list of 0-2 style tags from the style vocabulary. Empty [] if not confident.
- "potential": "high", "medium", or "low" per the potential rating rules.
- "key": musical key you detect from the audio (e.g. "Em", "C#m"), null if unclear. Prefer your own hearing over librosa if they conflict.
- "bpm": BPM you detect, null if unclear. Prefer librosa's value if provided.
- "suggestion": a concrete, actionable next-step for the creator (1-2 sentences, same language as any lyrics/text). Be specific to what you HEARD.
- "transcript": if you can make out any sung/spoken words, include them here as a string. null if purely instrumental.

ONLY output the JSON object. No markdown wrapping, no explanation outside the JSON."""
    else:
        # Text-only: no audio to listen to
        prompt_text = f"""Tag this music fragment. Follow the tagging procedure from your system instructions exactly.

Fragment text: {text!r}{features_str}

Return ONLY a JSON object with these fields (flat structure, not nested):
- "emotions": list of 1-3 emotion tags from the emotion taxonomy. Order strongest first.
- "themes": list of 1-3 theme tags from the theme taxonomy. Empty [] if no discernible subject.
- "tags": list of 2-4 descriptive content tags (e.g. "melody", "chord progression", "lyric", "hook idea", "vocal riff", "beat sketch").
- "structure_hint": one value from the structure hints reference, or null.
- "style": list of 0-2 style tags from the style vocabulary. Empty [] if not confident.
- "potential": "high", "medium", or "low" per the potential rating rules.
- "key": musical key if detectable (e.g. "Em", "C#m"), null otherwise.
- "bpm": BPM if detectable, null otherwise.
- "suggestion": a concrete, actionable next-step for the creator (1-2 sentences, same language as the fragment). Be specific to THIS fragment's content and potential.

ONLY output the JSON object. No markdown wrapping, no explanation outside the JSON."""

    try:
        client = get_genai_client()

        # Build content parts — multimodal if audio available
        if audio_gcs_uri:
            mime_type = _guess_audio_mime_type(audio_gcs_uri)
            contents = [
                types.Part.from_uri(file_uri=audio_gcs_uri, mime_type=mime_type),
                types.Part.from_text(prompt_text),
            ]
        else:
            contents = prompt_text

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_context,
                temperature=0.3,  # Lower temperature for more consistent tagging
            ),
        )
        result_text = response.text.strip()
        parsed = _try_parse_agent_json(result_text)
        if not parsed:
            logger.warning("Failed to parse tagging response: %s", result_text[:200])
            return None

        # Handle case where model returns nested format from skill examples
        # (skill examples use {"tags": {"emotion": ...}} but we need flat)
        if "tags" in parsed and isinstance(parsed["tags"], dict):
            nested = parsed["tags"]
            flat: dict = {}
            flat["emotions"] = nested.get("emotion", [])
            flat["themes"] = nested.get("theme", [])
            flat["structure_hint"] = nested.get("structure_hint")
            flat["style"] = nested.get("style", [])
            flat["potential"] = nested.get("potential", "medium")
            flat["tags"] = []  # No content tags in nested format
            # Preserve key/bpm/suggestion/transcript from outer level
            flat["key"] = parsed.get("key")
            flat["bpm"] = parsed.get("bpm")
            flat["suggestion"] = parsed.get("suggestion")
            flat["transcript"] = parsed.get("transcript")
            parsed = flat

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
    context = f"themes: {themes}, emotions: {emotions}"
    prompt = f"""Generate a short, evocative project title (2-4 words) for a music project with these characteristics:
{context}

The title should feel like a working album/song title — poetic but not pretentious.
Return ONLY the title, nothing else."""

    try:
        client = get_genai_client()
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
        client = get_genai_client()
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
        .find({"user_id": user_id}, {"embedding": 0, "edit_history": 0})
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


class TagUpdateRequest(BaseModel):
    tags: list[str] | None = None
    emotions: list[str] | None = None
    potential: str | None = None
    structure_hint: str | None = None
    style: list[str] | None = None


@app.post("/api/fragments/{fragment_id}/tags")
async def update_fragment_tags(
    fragment_id: str,
    body: TagUpdateRequest,
    user_id: str = Depends(verify_firebase_token),
):
    """Update user-editable fields on a fragment. Tracks which fields were manually edited."""
    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
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
    db["fragments"].update_one({"_id": oid}, {"$set": update})
    return {"updated": True, "user_edited_fields": edited_fields}


@app.post("/api/fragments/{fragment_id}/delete")
async def delete_fragment(fragment_id: str, user_id: str = Depends(verify_firebase_token)):
    """Delete a single fragment by ID."""
    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
    result = db["fragments"].delete_one({"_id": oid, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"deleted": True}


class TextEditRequest(BaseModel):
    text: str


@app.post("/api/fragments/{fragment_id}/edit-text")
async def edit_fragment_text(
    fragment_id: str,
    body: TextEditRequest,
    user_id: str = Depends(verify_firebase_token),
):
    """Edit a fragment's text content. Saves previous version to edit_history and triggers AI re-analysis."""
    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
    fragment = db["fragments"].find_one({"_id": oid, "user_id": user_id})
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    new_text = body.text.strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    old_text = fragment.get("text", "")
    if old_text == new_text:
        return {"updated": False, "message": "No change"}

    # Build history entry for the previous version
    history_entry = {
        "id": str(uuid.uuid4()),
        "text": old_text,
        "edited_at": datetime.now(UTC).isoformat(),
    }

    edited_fields = list(fragment.get("user_edited_fields", []))
    if "text" not in edited_fields:
        edited_fields.append("text")

    db["fragments"].update_one(
        {"_id": oid},
        {
            "$push": {"edit_history": {"$each": [history_entry], "$slice": -50}},
            "$set": {
                "text": new_text,
                "status": "processing",
                "user_edited_fields": edited_fields,
            },
        },
    )

    # Trigger AI re-analysis in background
    task = asyncio.create_task(_reanalyze_fragment_text(user_id, str(oid), new_text))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"updated": True, "text": new_text}


async def _reanalyze_fragment_text(user_id: str, fragment_id: str, new_text: str):
    """Re-run AI tagging and embedding on edited text."""
    from tools.embedding import generate_embedding

    db = get_db()
    oid = ObjectId(fragment_id)
    try:
        tag_task = _tag_fragment_direct(new_text)
        embed_task = generate_embedding(new_text)
        tag_result, embedding = await asyncio.gather(tag_task, embed_task, return_exceptions=True)

        update: dict = {"status": "ready"}

        if isinstance(tag_result, dict):
            fragment = db["fragments"].find_one({"_id": oid})
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


@app.post("/api/fragments/{fragment_id}/edit-history/{entry_id}/delete")
async def delete_edit_history_entry(
    fragment_id: str,
    entry_id: str,
    user_id: str = Depends(verify_firebase_token),
):
    """Delete a single edit history entry."""
    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
    result = db["fragments"].update_one(
        {"_id": oid, "user_id": user_id},
        {"$pull": {"edit_history": {"id": entry_id}}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"deleted": True}


@app.get("/api/fragments/{fragment_id}/audio")
async def stream_audio(
    fragment_id: str,
    user_id: str = Depends(verify_firebase_token),
    range: str | None = Header(None),
):
    """Stream audio file from GCS with Range support for seeking."""
    from fastapi.responses import Response, StreamingResponse

    db = get_db()
    oid = _parse_object_id(fragment_id, "fragment_id")
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


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------

@app.get("/api/projects")
async def list_projects(user_id: str = Depends(verify_firebase_token)):
    """List all projects for the current user."""
    db = get_db()
    projects = list(
        db["projects"].find({"user_id": user_id}).sort([("rescue_score", -1), ("_id", -1)]).limit(50)
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
# Notifications
# ---------------------------------------------------------------------------

@app.get("/api/notifications")
async def list_notifications(user_id: str = Depends(verify_firebase_token)):
    """List unread + recent notifications for the current user."""
    db = get_db()
    notifications = list(
        db["notifications"]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(20)
    )
    for n in notifications:
        n["_id"] = str(n["_id"])
        # Resolve sleeping project title if missing
        if not n.get("sleeping_project_title") and n.get("sleeping_project_id"):
            proj = db["projects"].find_one(
                {"_id": ObjectId(n["sleeping_project_id"])},
                {"title": 1},
            )
            if proj:
                n["sleeping_project_title"] = proj.get("title", "")
    unread = sum(1 for n in notifications if not n.get("read"))
    return {"notifications": notifications, "unread_count": unread}


@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str, user_id: str = Depends(verify_firebase_token)
):
    """Mark a single notification as read."""
    db = get_db()
    oid = _parse_object_id(notification_id, "notification_id")
    result = db["notifications"].update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"updated": True}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(user_id: str = Depends(verify_firebase_token)):
    """Mark all notifications as read for the current user."""
    db = get_db()
    db["notifications"].update_many(
        {"user_id": user_id, "read": False}, {"$set": {"read": True}}
    )
    return {"updated": True}


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


@app.post("/api/reanalyze-all")
async def reanalyze_all_fragments(user_id: str = Depends(verify_firebase_token)):
    """Re-run the full Gemini multimodal pipeline on all user fragments."""
    db = get_db()
    fragments = list(
        db["fragments"].find(
            {"user_id": user_id},
            {"_id": 1, "audio_url": 1, "text": 1, "type": 1},
        )
    )
    if not fragments:
        return {"message": "No fragments found", "processed": 0}

    db["fragments"].update_many(
        {"user_id": user_id},
        {"$set": {"status": "processing"}},
    )

    tasks = set()
    for frag in fragments:
        frag_id = str(frag["_id"])
        audio_url = frag.get("audio_url")
        text = frag.get("text")
        task = asyncio.create_task(
            _process_fragment_background(user_id, frag_id, audio_url, text)
        )
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    return {
        "message": f"Reanalyzing {len(fragments)} fragments in background",
        "processing": len(fragments),
    }


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
