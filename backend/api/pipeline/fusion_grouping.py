"""Grouping decided by the fusion score, with the language model writing words only.

Selected with POCKET_GROUPING_MODE=fusion (default "llm", the agent path).
In fusion mode, for a newly processed fragment:

1. A creator note that explicitly says the fragment stands alone is
   followed: no group. A note that names where it belongs goes to the agent
   path, which reads the note and finds that place. Both are recorded as
   decided by the creator note. The language model only classifies what
   the note says; it does not judge the music. If that classification
   fails, the agent path runs and the fragment is recorded as llm_fallback.
2. A fragment without an audio vector (text-only, or uploaded before audio
   encoding) cannot be scored and goes to the agent path, recorded as
   llm_fallback.
3. Otherwise ranking.grouping.decide_grouping makes the call in code from
   the fusion score against GROUPING_THRESHOLD, and the code executes it.
   The language model then writes the narrative, the project title and the
   next action for that decision. Nothing it returns is read as a decision.

Each fragment records grouping_decided_by ("fusion", "creator_note" or
"llm_fallback") and grouping_decision (score, threshold, counts), so the
share of each can be counted later.
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from ranking.grouping import (
    MAX_CANDIDATES,
    GroupingDecision,
    Scorable,
    decide_grouping,
    resolve_artifact,
)

logger = logging.getLogger(__name__)

MODES = ("llm", "fusion")
CONNECTION_TYPE = "sound_match"
CLAP_WAIT_SECONDS = 90.0
_NOTE_READINGS = ("stands_alone", "names_a_home", "none")

_weights: list[float] | None = None


def grouping_mode() -> str:
    mode = os.environ.get("POCKET_GROUPING_MODE", "llm").strip().lower()
    if mode not in MODES:
        logger.warning("Unknown POCKET_GROUPING_MODE=%r; using llm", mode)
        return "llm"
    return mode


def fusion_weights() -> list[float]:
    """Deployed fusion weights, resolved like ranking/service.py resolves them."""
    global _weights
    if _weights is None:
        from ranking.fusion_ranker import load_weights

        path = resolve_artifact(
            os.environ.get("POCKET_FUSION_WEIGHTS", "artifacts/fusion-deploy/weights.json")
        )
        _weights = list(load_weights(path)["weights"])
    return _weights


def _scorable(doc: dict) -> Scorable | None:
    vector = ((doc.get("representations") or {}).get("audio_semantic") or {}).get("vector")
    if not vector:
        return None
    return Scorable(
        fragment_id=str(doc["_id"]),
        vector=vector,
        bpm=doc.get("bpm"),
        key=doc.get("key"),
        tags=doc.get("tags") or [],
        project_id=str(doc["project_id"]) if doc.get("project_id") else None,
    )


_FIELDS = {
    "title": 1, "text": 1, "notes": 1, "comments": 1, "tags": 1, "bpm": 1,
    "key": 1, "project_id": 1, "emotions": 1, "representations.audio_semantic.vector": 1,
}


def _creator_words(doc: dict) -> str:
    parts = []
    if doc.get("notes"):
        parts.append(f"note: {doc['notes']}")
    for comment in doc.get("comments") or []:
        if comment.get("text"):
            parts.append(f"comment: {comment['text']}")
    return "\n".join(parts)


async def read_creator_instruction(words: str) -> str:
    """Classify an explicit grouping instruction in the creator's own words.

    Returns stands_alone, names_a_home, none, or unread when the call fails.
    Only explicit statements count; the model is not asked about the music.
    """
    if not words.strip():
        return "none"
    from google.genai import types as genai_types

    from api._clients import get_genai_client

    prompt = (
        "A musician wrote these words about one of their recorded fragments "
        "(later comments reflect their current thinking):\n"
        f"{words[:2000]}\n\n"
        "Do the words EXPLICITLY say how this fragment should be grouped?\n"
        "- stands_alone: they say it is separate, a standalone idea, or should not "
        "be grouped with other material\n"
        "- names_a_home: they say it belongs with a specific song, project or "
        "other fragment\n"
        "- none: anything else, including descriptions of mood or sound\n"
        "Answer with one of the three labels."
    )
    try:
        client = get_genai_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=os.environ.get("PRODUCER_MODEL", "gemini-3-flash-preview"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {"reading": {"type": "string", "enum": list(_NOTE_READINGS)}},
                        "required": ["reading"],
                    },
                ),
            ),
            timeout=20,
        )
        reading = json.loads(response.text or "{}").get("reading")
        return reading if reading in _NOTE_READINGS else "unread"
    except Exception:
        logger.warning("Reading the creator note failed", exc_info=True)
        return "unread"


async def write_narrative(decision: GroupingDecision, source: dict, others: list[dict]) -> str:
    """A short message to the creator about a decision already made.

    Returns text only. On failure a plain sentence is used instead.
    """
    names = [o.get("title") for o in others if o.get("title")][:4]
    fallback = {
        "join_project": "This sounds close to the fragments already in this project, so I added it there.",
        "new_project": "These fragments sound close to each other, so I started a project with them.",
        "no_group": "Nothing in your library sounds close enough to this one yet, so it stays on its own for now.",
    }[decision.action]
    from google.genai import types as genai_types

    from api._clients import get_genai_client

    what = {
        "join_project": "It was added to an existing project with these fragments",
        "new_project": "It was grouped into a new project with these fragments",
        "no_group": "It was left ungrouped; nothing in the library sounded close enough",
    }[decision.action]
    prompt = (
        "Write 2-3 sentences to a musician, in the language of their fragment, "
        "about where their new fragment went. Address them as 'you'. Do not "
        "question or change the outcome; it is final.\n"
        f"New fragment: {json.dumps({k: source.get(k) for k in ('title', 'text', 'emotions', 'tags')}, ensure_ascii=False, default=str)[:800]}\n"
        f"Outcome: {what}: {json.dumps(names, ensure_ascii=False)}\n"
        "The outcome came from how similar the recordings sound (audio, tempo, "
        "key and tags). Output only the message."
    )
    try:
        client = get_genai_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=os.environ.get("PRODUCER_MODEL", "gemini-3-flash-preview"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=0.6),
            ),
            timeout=30,
        )
        text = (response.text or "").strip()
        return text[:1200] if text else fallback
    except Exception:
        logger.warning("Narrative generation failed; using the plain sentence", exc_info=True)
        return fallback


async def _wait_for_audio_vector(db, user_id: str, fragment_id: str, doc: dict) -> dict:
    """Give a just-uploaded fragment's audio encoding a bounded chance to finish."""
    if _scorable(doc) is not None:
        return doc
    from .processing import wait_for_clap

    if not await wait_for_clap(fragment_id, CLAP_WAIT_SECONDS):
        return doc
    fresh = await asyncio.to_thread(
        db["fragments"].find_one, {"_id": ObjectId(fragment_id), "user_id": user_id}, _FIELDS
    )
    return fresh or doc


def _record(db, user_id: str, fragment_id: str, decided_by: str, detail: dict) -> None:
    db["fragments"].update_one(
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"$set": {
            "grouping_decided_by": decided_by,
            "grouping_decision": {
                "decided_by": decided_by,
                "mode": "fusion",
                "at": datetime.now(UTC),
                **detail,
            },
        }},
    )


async def group_by_fusion(db, user_id: str, fragment_id: str) -> bool:
    """Decide and execute grouping in fusion mode.

    Returns True when this function settled the fragment, False when the
    caller should run the agent path (the reason is already recorded).
    """
    source = await asyncio.to_thread(
        db["fragments"].find_one, {"_id": ObjectId(fragment_id), "user_id": user_id}, _FIELDS
    )
    if not source:
        return True

    reading = await read_creator_instruction(_creator_words(source))
    if reading == "stands_alone":
        _record(db, user_id, fragment_id, "creator_note", {
            "action": "no_group", "note_reading": reading,
        })
        db["fragments"].update_one(
            {"_id": ObjectId(fragment_id), "user_id": user_id},
            {"$set": {"pipeline_step": "Kept on its own, as your note asks"}},
        )
        return True
    if reading in ("names_a_home", "unread"):
        # The agent path reads the note itself and finds the place it names.
        decided_by = "creator_note" if reading == "names_a_home" else "llm_fallback"
        _record(db, user_id, fragment_id, decided_by, {
            "note_reading": reading, "executed_by": "agent",
        })
        return False

    source = await _wait_for_audio_vector(db, user_id, fragment_id, source)
    me = _scorable(source)
    if me is None:
        _record(db, user_id, fragment_id, "llm_fallback", {
            "reason": "no_audio_vector", "executed_by": "agent",
        })
        return False

    others_docs = await asyncio.to_thread(lambda: list(
        db["fragments"].find(
            {
                "user_id": user_id,
                "_id": {"$ne": ObjectId(fragment_id)},
                "status": "ready",
                "representations.audio_semantic.vector": {"$exists": True},
            },
            _FIELDS,
        ).sort("created_at", -1).limit(MAX_CANDIDATES)
    ))
    others = [s for s in (_scorable(d) for d in others_docs) if s is not None]
    weights = fusion_weights()
    decision = decide_grouping(me, others, weights)
    logger.info("Fusion grouping for %s: %s", fragment_id, decision.record())

    involved = set(decision.fragment_ids)
    if decision.project_id:
        involved |= {o.fragment_id for o in others if o.project_id == decision.project_id}
    involved.discard(fragment_id)
    narrative = await write_narrative(
        decision, source, [d for d in others_docs if str(d["_id"]) in involved]
    )
    await _execute(db, user_id, fragment_id, decision, narrative)
    _record(db, user_id, fragment_id, "fusion", {
        **decision.record(), "model_id": "fusion-5sig-v1",
    })
    return True


async def _execute(db, user_id: str, fragment_id: str, decision: GroupingDecision,
                   narrative: str) -> str | None:
    """Carry out a decision with the same write tools the agent path uses."""
    from agents.producer import _current_db as producer_db_var
    from agents.producer import _current_user_id as producer_user_var
    from agents.producer import (
        attach_fragment_to_project,
        create_project_from_fragments,
        generate_next_action,
        generate_project_title,
        refresh_project_score,
    )

    oid = ObjectId(fragment_id)
    db["fragments"].update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"agent_narrative": narrative}}
    )
    if decision.action == "no_group":
        db["fragments"].update_one(
            {"_id": oid, "user_id": user_id},
            {"$set": {"pipeline_step": "Nothing close enough yet; kept on its own"}},
        )
        return None

    db_token = producer_db_var.set(db)
    user_token = producer_user_var.set(user_id)
    try:
        types = [CONNECTION_TYPE]
        project_id: str | None = None
        if decision.action == "join_project":
            resp = json.loads(await attach_fragment_to_project(
                fragment_id=fragment_id, project_id=decision.project_id,
                connection_reason=narrative, connection_types=types,
            ))
            project_id = decision.project_id if resp.get("attached") else None
        elif decision.action == "new_project":
            title = json.loads(await generate_project_title(
                fragment_ids=decision.fragment_ids, connection_types=types,
            )).get("title") or "Untitled Project"
            resp = json.loads(await create_project_from_fragments(
                title=title, fragment_ids=decision.fragment_ids,
                connection_reason=narrative, connection_types=types,
            ))
            project_id = resp.get("project_id")
        if not project_id:
            logger.warning("Fusion grouping for %s could not be written: %s", fragment_id, resp)
            return None

        next_action: Any = None
        try:
            na = json.loads(await generate_next_action(project_id=project_id))
            if isinstance(na, dict) and "action" in na:
                next_action = json.dumps(na, ensure_ascii=False)
        except Exception:
            logger.warning("Next action failed for project %s", project_id, exc_info=True)
        await refresh_project_score(project_id=project_id, next_action=next_action)
        db["fragments"].update_one(
            {"_id": oid, "user_id": user_id},
            {"$set": {"pipeline_step": "Grouped into a project"}},
        )
        return project_id
    finally:
        producer_db_var.reset(db_token)
        producer_user_var.reset(user_token)
