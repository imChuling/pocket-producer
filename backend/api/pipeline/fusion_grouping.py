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

POCKET_GROUPING_MODE=hybrid runs the agent path as in "llm", and the
language model makes the final call, but it is shown the fusion pair scores:
the scores against the closest fragments in the library, the grouping that
decide_grouping would choose, and, on every neighbour the memory agent
considers, that neighbour's score (or "no score" without an audio vector).
The fragment records grouping_decided_by "llm_with_fusion", the scores
shown, and whether the final grouping agreed with what decide_grouping would
have chosen. That agreement is computed, not enforced.
"""

import asyncio
import json
import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from ranking.grouping import (
    GROUPING_THRESHOLD,
    MAX_CANDIDATES,
    GroupingDecision,
    Scorable,
    decide_grouping,
    pair_fusion_score,
    resolve_artifact,
)

logger = logging.getLogger(__name__)

MODES = ("llm", "fusion", "hybrid")
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


# --- hybrid mode -------------------------------------------------------------

SHOWN_TOP = 8
SHOWN_RECORDED = 20

SCORE_MEANING = (
    "Each score is the deployed fusion-5sig-v1 score between two fragments "
    "(MS-CLAP audio similarity, tempo, key and tags, with weights trained on "
    "loops filed in the same sample pack). The threshold is "
    f"{GROUPING_THRESHOLD:.2f}. On held-out packs, at this threshold about 94% of "
    "the pairs it flagged were from the same pack, while about two thirds of "
    "same-pack pairs scored below it and were missed. The score mostly reflects "
    "how alike two recordings sound, so a low score does not rule out parts that "
    "complement each other, such as a bass line and a drum loop from one song."
)


@dataclass
class HybridContext:
    """What the model was shown, and what decide_grouping would have chosen."""

    suggestion: GroupingDecision | None
    reason: str | None = None
    top_scores: list[dict] = field(default_factory=list)
    neighbour_scores: list[dict] = field(default_factory=list)
    existing_projects: set[str] = field(default_factory=set)


HYBRID: ContextVar[HybridContext | None] = ContextVar("hybrid_grouping", default=None)


def neighbour_score(source: dict, neighbour: dict) -> dict:
    """A neighbour's pair score for the memory agent, or "no score" without vectors."""
    me, other = _scorable({**source, "_id": source.get("_id", "")}), _scorable(
        {**neighbour, "_id": neighbour.get("_id", "")}
    )
    if me is None or other is None:
        return {"fusion_pair_score": "no score", "fusion_at_or_above_threshold": None}
    try:
        score = pair_fusion_score(
            fusion_weights(), me.vector, other.vector, me.bpm, other.bpm,
            me.key, other.key, me.tags, other.tags,
        )
    except ValueError:
        return {"fusion_pair_score": "no score", "fusion_at_or_above_threshold": None}
    return {
        "fusion_pair_score": round(score, 3),
        "fusion_at_or_above_threshold": score >= GROUPING_THRESHOLD,
    }


async def prepare_hybrid(db, user_id: str, fragment_id: str) -> HybridContext:
    """Score the library the way fusion mode would, without acting on it."""
    projects = await asyncio.to_thread(
        lambda: {str(p["_id"]) for p in db["projects"].find({"user_id": user_id}, {"_id": 1})}
    )
    source = await asyncio.to_thread(
        db["fragments"].find_one, {"_id": ObjectId(fragment_id), "user_id": user_id}, _FIELDS
    )
    if not source:
        return HybridContext(None, "fragment_missing", existing_projects=projects)
    source = await _wait_for_audio_vector(db, user_id, fragment_id, source)
    me = _scorable(source)
    if me is None:
        return HybridContext(None, "no_audio_vector", existing_projects=projects)

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
    weights = fusion_weights()
    titles = {str(d["_id"]): d.get("title") for d in others_docs}
    others = [o for o in (_scorable(d) for d in others_docs) if o is not None]
    scored = []
    for other in others:
        try:
            score = pair_fusion_score(
                weights, me.vector, other.vector, me.bpm, other.bpm,
                me.key, other.key, me.tags, other.tags,
            )
        except ValueError:
            continue
        scored.append({
            "fragment_id": other.fragment_id,
            "title": titles.get(other.fragment_id),
            "project_id": other.project_id,
            "fusion_pair_score": round(score, 3),
            "at_or_above_threshold": score >= GROUPING_THRESHOLD,
        })
    scored.sort(key=lambda r: -r["fusion_pair_score"])
    return HybridContext(
        decide_grouping(me, others, weights),
        top_scores=scored[:SHOWN_TOP],
        existing_projects=projects,
    )


def _describe(decision: GroupingDecision | None) -> str:
    if decision is None:
        return "none"
    if decision.action == "join_project":
        return f"join project {decision.project_id} (project score {decision.score:.2f})"
    if decision.action == "new_project":
        return f"new project with fragments {decision.fragment_ids} (best score {decision.score:.2f})"
    best = "n/a" if decision.score is None else f"{decision.score:.2f}"
    return f"no group (best score {best}, below the threshold)"


def hybrid_prompt_block(ctx: HybridContext | None) -> str:
    """The fusion evidence for the deciding agent, or "" outside hybrid mode."""
    if ctx is None:
        return ""
    if ctx.suggestion is None:
        evidence = (
            "This fragment has no audio vector, so it has no fusion score against any "
            "fragment: no score."
        )
    else:
        lines = [
            f"- {r['fragment_id']} ({r.get('title') or 'untitled'}; project "
            f"{r.get('project_id') or 'none'}): {r['fusion_pair_score']:.2f}"
            f"{' (at or above threshold)' if r.get('at_or_above_threshold') else ''}"
            for r in ctx.top_scores
        ]
        evidence = (
            "Highest fusion scores against this user's fragments with an audio vector "
            "(fragments without one have no score):\n"
            + ("\n".join(lines) if lines else "- none")
            + f"\nWhat the fusion rule alone would choose: {_describe(ctx.suggestion)}."
        )
    return (
        "\n\nFusion model evidence (computed in code):\n"
        f"{SCORE_MEANING}\n{evidence}\n"
        "The memory tool also reports `fusion_pair_score` for each neighbour "
        "(\"no score\" when a fragment has no audio vector). Treat a score at or above "
        "the threshold as strong evidence that the two fragments belong in the same "
        "project. You make the final decision. If your decision goes against the "
        "score, say so in the narrative and why. Explicit creator notes still win."
    )


def record_hybrid_outcome(db, user_id: str, fragment_id: str, ctx: HybridContext) -> None:
    """Store what was shown and whether the final grouping matched the fusion rule."""
    oid = ObjectId(fragment_id)
    doc = db["fragments"].find_one({"_id": oid, "user_id": user_id}, {"project_id": 1})
    if doc is None:
        return
    project_id = str(doc["project_id"]) if doc.get("project_id") else None
    if project_id is None:
        final = "no_group"
    elif project_id in ctx.existing_projects:
        final = "join_project"
    else:
        final = "new_project"

    suggestion = ctx.suggestion
    agrees: bool | None = None
    if suggestion is not None:
        if suggestion.action != final:
            agrees = False
        elif final == "join_project":
            agrees = project_id == suggestion.project_id
        elif final == "new_project":
            members = (db["projects"].find_one(
                {"_id": ObjectId(project_id), "user_id": user_id}, {"fragment_ids": 1}
            ) or {}).get("fragment_ids", [])
            agrees = suggestion.fragment_ids[1] in {str(m) for m in members}
        else:
            agrees = True

    shown = (ctx.top_scores + ctx.neighbour_scores)[:SHOWN_RECORDED]
    db["fragments"].update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {
            "grouping_decided_by": "llm_with_fusion",
            "grouping_decision": {
                "decided_by": "llm_with_fusion",
                "mode": "hybrid",
                "at": datetime.now(UTC),
                "threshold": GROUPING_THRESHOLD,
                "model_suggestion": suggestion.record() if suggestion else None,
                "reason": ctx.reason,
                "final": {"action": final, "project_id": project_id},
                "agrees_with_fusion_rule": agrees,
                "scores_shown": shown,
            },
        }},
    )
