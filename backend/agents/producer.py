"""Producer Agent (Action layer) — root orchestrator, actively running in the pipeline.

Responsibilities:
- Receives a newly tagged fragment
- Delegates to Memory Agent for relationship discovery
- Makes the final decision: join project / create project / skip
- Executes writes (create project, attach fragment, refresh rescue score)
- Generates one concrete next_action for the creator
"""

import asyncio
import json
import logging
import os
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from tools.rescue_score import compute_rescue_score

from ._skills_loader import get_skill_toolset
from .memory import memory_agent

logger = logging.getLogger(__name__)

_current_user_id: ContextVar[str] = ContextVar("producer_agent_user_id")
_current_db: ContextVar[Any] = ContextVar("producer_agent_db")


class _JSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def _to_json(value: Any) -> str:
    return json.dumps(value, cls=_JSONEncoder, ensure_ascii=False)


def _db():
    return _current_db.get()


def _user_id() -> str:
    return _current_user_id.get()


# ---------------------------------------------------------------------------
# Write tools for Producer Agent
# ---------------------------------------------------------------------------


async def create_project_from_fragments(
    title: str,
    fragment_ids: list[str],
    connection_reason: str,
    connection_types: list[str],
) -> str:
    """Create a new project from related fragments and attach them all.

    Args:
        title: Short descriptive title for the project (max 80 chars)
        fragment_ids: List of fragment IDs to include
        connection_reason: Why these fragments belong together
        connection_types: Relationship types (same_song_candidate, related_theme, etc.)
    """
    db = _db()
    user_id = _user_id()
    oids = [ObjectId(fid) for fid in fragment_ids]

    count = await asyncio.to_thread(
        db["fragments"].count_documents,
        {"_id": {"$in": oids}, "user_id": user_id},
    )
    if count != len(oids):
        return _to_json({"error": "one_or_more_fragments_not_found"})

    now = datetime.now(UTC)
    project = {
        "user_id": user_id,
        "title": title.strip()[:80] or "Untitled Project",
        "fragment_ids": [str(oid) for oid in oids],
        "connection_reasons": [connection_reason],
        "connection_types": sorted(set(connection_types)),
        "sections": [],
        "rescue_score": None,
        "last_activity_at": now,
        "created_at": now,
    }
    result = await asyncio.to_thread(db["projects"].insert_one, project)
    project_id = str(result.inserted_id)
    await asyncio.to_thread(
        db["fragments"].update_many,
        {"_id": {"$in": oids}, "user_id": user_id},
        {
            "$set": {
                "project_id": project_id,
                "project_title": project["title"],
                "connection_reason": connection_reason,
                "connection_types": sorted(set(connection_types)),
            }
        },
    )
    return _to_json({"project_id": project_id, "title": project["title"]})


async def attach_fragment_to_project(
    fragment_id: str,
    project_id: str,
    connection_reason: str,
    connection_types: list[str],
) -> str:
    """Attach a fragment to an existing project.

    Args:
        fragment_id: The fragment to attach
        project_id: The target project
        connection_reason: Why this fragment belongs in this project
        connection_types: Relationship types that justify the connection
    """
    db = _db()
    user_id = _user_id()
    fragment_oid = ObjectId(fragment_id)
    project_oid = ObjectId(project_id)

    project = await asyncio.to_thread(
        db["projects"].find_one,
        {"_id": project_oid, "user_id": user_id},
    )
    if not project:
        return _to_json({"error": "project_not_found"})

    fragment = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": fragment_oid, "user_id": user_id},
        {"_id": 1},
    )
    if not fragment:
        return _to_json({"error": "fragment_not_found"})

    reasons = project.get("connection_reasons", [])
    if connection_reason:
        reasons.append(connection_reason)
    merged_types = sorted(set(project.get("connection_types", []) + connection_types))

    await asyncio.to_thread(
        db["projects"].update_one,
        {"_id": project_oid, "user_id": user_id},
        {
            "$addToSet": {"fragment_ids": fragment_id},
            "$set": {
                "connection_reasons": reasons,
                "connection_types": merged_types,
                "last_activity_at": datetime.now(UTC),
            },
        },
    )
    await asyncio.to_thread(
        db["fragments"].update_one,
        {"_id": fragment_oid, "user_id": user_id},
        {
            "$set": {
                "project_id": project_id,
                "project_title": project.get("title", ""),
                "connection_reason": connection_reason,
                "connection_types": sorted(set(connection_types)),
            }
        },
    )
    return _to_json({"project_id": project_id, "attached": True})


async def refresh_project_score(project_id: str, next_action: str | None = None) -> str:
    """Compute Rescue Score for a project and update it.

    Args:
        project_id: The project to score
        next_action: JSON string with one concrete next action for the creator,
                     e.g. {"action": "Record vocals over the piano motif", "estimated_time": "20 min"}
    """
    db = _db()
    user_id = _user_id()
    project_oid = ObjectId(project_id)
    project = await asyncio.to_thread(
        db["projects"].find_one,
        {"_id": project_oid, "user_id": user_id},
    )
    if not project:
        return _to_json({"error": "project_not_found"})

    fragment_ids = [
        ObjectId(fid) for fid in project.get("fragment_ids", [])
        if ObjectId.is_valid(str(fid))
    ]
    fragments = await asyncio.to_thread(
        lambda: list(
            db["fragments"].find(
                {"_id": {"$in": fragment_ids}, "user_id": user_id},
                {"embedding": 0},
            )
        )
    )
    score_data = compute_rescue_score(fragments, project_id)
    sections = sorted(
        {
            f.get("structure_hint", "").replace("_candidate", "").replace("_", " ")
            for f in fragments
            if f.get("structure_hint")
        }
    )
    update: dict[str, Any] = {
        "rescue_score": score_data.get("rescue_score"),
        "score_breakdown": score_data.get("components"),
        "sections": sections,
        "last_activity_at": datetime.now(UTC),
    }

    parsed_action = None
    if next_action:
        try:
            parsed_action = json.loads(next_action) if isinstance(next_action, str) else next_action
        except (json.JSONDecodeError, TypeError):
            parsed_action = {"action": str(next_action), "estimated_time": "30 min"}
    if parsed_action:
        update["next_action"] = parsed_action

    await asyncio.to_thread(
        db["projects"].update_one,
        {"_id": project_oid, "user_id": user_id},
        {"$set": update},
    )
    return _to_json({"project_id": project_id, **update})


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

PRODUCER_INSTRUCTION = """\
You are the Producer Agent (Action layer) — root orchestrator of Pocket Producer.

You receive a newly tagged fragment and make grounded decisions about how it
connects to the user's creative history.

## Workflow

Step 1: Delegate to Memory Agent by passing the fragment_id. Memory will
        perform vector search, analyze relationships, and return structured
        recommendations.

Step 2: Review Memory's recommendation:
   - "join_project": attach the fragment to the suggested project
   - "new_project": create a new project grouping related fragments
   - "no_group": the fragment stays ungrouped (this is fine)
   - "needs_user_confirmation": flag for user review
   - "bridge_projects": SURFACE THIS — high-value moment where the user
     may have written two halves of the same song without realizing

Step 3: Execute the decision:
   - For join_project: call attach_fragment_to_project
   - For new_project: call create_project_from_fragments with a descriptive title
   - For no_group: do nothing, return the decision

Step 4: If a project was created or updated, call refresh_project_score with
        one concrete next_action that the creator can accomplish in 30 minutes.
        Use musical-knowledge skill to make the suggestion specific (mention
        key, tempo, or structural role when relevant).

## Output

Return ONLY this JSON:
{
  "decision": "join_project | new_project | no_group | needs_user_confirmation | bridge_projects",
  "project_id": "string or null",
  "match_id": "best matching fragment ID or null",
  "reasoning": "1-2 concrete sentences for the user",
  "connection_types": ["same_song_candidate", ...],
  "next_action": {"action": "...", "estimated_time": "20 min"} or null
}

## Gatekeeping rules (ALWAYS apply before executing)

BEFORE executing Memory's recommendation, verify these gates:

1. If Memory says "no_group" → accept it. This is the expected outcome for
   most fragments. Return no_group without calling any write tools.

2. If Memory says "join_project" or "new_project", check the signals:
   - At least ONE analysis entry must have relationship = "same_song_candidate"
   - That entry must have at least 2 signals rated "strong"
   - If both fragments have audio features, musical_compatibility must NOT
     be "conflicting"
   → If any gate fails, DOWNGRADE to "no_group" (not needs_user_confirmation).

3. If Memory says "needs_user_confirmation" → return it as-is. Do not
   auto-resolve ambiguity.

4. If Memory says "bridge_projects" → verify both source projects exist
   before surfacing. This is the highest-value output.

## The default is no_group

A creator with 15 fragments should have roughly 3-5 projects, not 10-15.
Ungrouped fragments are NOT a failure — they are ideas waiting for their match.
Only group when the connection is obvious and specific.

Do NOT group fragments just because they share a mood (e.g., both "melancholy").
Do NOT group fragments just because they share a generic theme (e.g., both "love").
DO group when there is lyrical continuity, structural complement (verse + chorus),
shared distinctive imagery, or strong musical compatibility with emotional alignment.

## Principles

- Trust Memory's analysis but verify through the gates above
- Bridge detection is the highest-value output — always surface it clearly
- The user's trust depends on NOT making confident mistakes
- A wrong confident grouping damages trust more than a missed connection
- Use rescue-scoring skill logic: a project needs richness + structure + coherence + freshness

## Boundaries (what you do NOT do)

- Do NOT tag fragments (already done before you receive them)
- Do NOT run vector search directly (Memory does that)
- Do NOT generate music or lyrics
- Do NOT judge musical quality or commercial viability
"""


producer_agent = LlmAgent(
    name="producer",
    model=os.environ.get("PRODUCER_MODEL", "gemini-2.5-flash"),
    instruction=PRODUCER_INSTRUCTION,
    sub_agents=[memory_agent],
    tools=[
        get_skill_toolset(["rescue-scoring", "musical-knowledge", "refusal-rules"]),
        FunctionTool(create_project_from_fragments),
        FunctionTool(attach_fragment_to_project),
        FunctionTool(refresh_project_score),
    ],
)
