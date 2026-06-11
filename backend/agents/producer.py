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
from google.adk.tools.agent_tool import AgentTool

from google.genai import types as genai_types

from tools.rescue_score import compute_rescue_score

from ._skills_loader import get_skill_toolset
from .memory import memory_agent

logger = logging.getLogger(__name__)

_current_user_id: ContextVar[str] = ContextVar("producer_agent_user_id")
_current_db: ContextVar[Any] = ContextVar("producer_agent_db")

_genai_client = None


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(vertexai=True)
    return _genai_client


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


_INVALID_ID_HINT = (
    "is not a real database id. Never invent placeholder ids: call "
    "create_project_from_fragments first, wait for its result, then pass the "
    "returned project_id to this tool."
)


def _parse_oid(value: str):
    return ObjectId(value) if ObjectId.is_valid(str(value)) else None


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
    oids = [_parse_oid(fid) for fid in fragment_ids]
    if any(o is None for o in oids):
        return _to_json({"error": "invalid_fragment_id", "hint": "fragment_ids must be the real 24-hex ids from the pipeline input or memory analysis"})

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
    fragment_oid = _parse_oid(fragment_id)
    project_oid = _parse_oid(project_id)
    if fragment_oid is None:
        return _to_json({"error": "invalid_fragment_id"})
    if project_oid is None:
        return _to_json({"error": f"'{project_id}' " + _INVALID_ID_HINT})

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
    project_oid = _parse_oid(project_id)
    if project_oid is None:
        return _to_json({"error": f"'{project_id}' " + _INVALID_ID_HINT})
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


async def generate_project_title(fragment_ids: list[str], connection_types: list[str]) -> str:
    """Generate a short, poetic project title from fragment metadata.

    Uses musical-knowledge and music-tagging skill context to craft an evocative
    2-5 word title that captures the emotional essence — like a song title.

    Args:
        fragment_ids: IDs of fragments being grouped into the project
        connection_types: Relationship types connecting the fragments
    """
    db = _db()
    user_id = _user_id()
    fragments_info = []
    for fid in fragment_ids[:4]:
        try:
            f = await asyncio.to_thread(
                db["fragments"].find_one,
                {"_id": _parse_oid(fid) or ObjectId(b"\x00" * 12), "user_id": user_id},
                {"title": 1, "text": 1, "emotions": 1, "themes": 1, "key": 1, "style": 1, "bpm": 1},
            )
            if f:
                fragments_info.append({
                    "title": f.get("title"),
                    "text": (f.get("text") or "")[:60],
                    "emotions": f.get("emotions", []),
                    "themes": f.get("themes", []),
                    "key": f.get("key"),
                    "bpm": f.get("bpm"),
                    "style": f.get("style", []),
                })
        except Exception:
            pass

    if not fragments_info:
        return _to_json({"title": "Untitled Project"})

    prompt = (
        "You are naming a music project. These fragments belong together:\n"
        f"{json.dumps(fragments_info, ensure_ascii=False)}\n"
        f"Connection types: {connection_types}\n\n"
        "Generate ONE short, evocative project title (2-5 words). "
        "It should feel poetic and capture the emotional essence — "
        "like a song title or album name, not a description. "
        "If fragments are in Chinese, the title can be Chinese. "
        "Output ONLY the title, nothing else."
    )
    try:
        client = _get_genai_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=os.environ.get("PRODUCER_MODEL", "gemini-3-flash-preview"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.8,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {"title": {"type": "string"}},
                        "required": ["title"],
                    },
                ),
            ),
            timeout=30,
        )
        text = response.text.strip()
        parsed = json.loads(text) if text else None
        title = parsed.get("title", "").strip() if parsed else response.text.strip().strip('"\'').strip()
        if title and len(title) <= 60:
            return _to_json({"title": title})
    except Exception:
        logger.warning("Title generation failed, using fallback")

    titles = [fi.get("title") or fi.get("text", "")[:20] for fi in fragments_info if fi.get("title") or fi.get("text")]
    fallback = titles[0][:60] if titles else "Untitled Project"
    return _to_json({"title": fallback})


async def generate_next_action(project_id: str) -> str:
    """Generate one concrete, musically-specific next action for a project.

    Consults rescue-scoring skill for action tables and musical-knowledge skill
    for key/tempo specifics. The action should be accomplishable in ≤30 minutes.

    Args:
        project_id: The project to generate a next action for
    """
    db = _db()
    user_id = _user_id()
    project_oid = _parse_oid(project_id)
    if project_oid is None:
        return _to_json({"error": f"'{project_id}' " + _INVALID_ID_HINT})
    project = await asyncio.to_thread(
        db["projects"].find_one,
        {"_id": project_oid, "user_id": user_id},
    )
    if not project:
        return _to_json({"error": "project_not_found"})

    frag_ids = [ObjectId(fid) for fid in project.get("fragment_ids", []) if ObjectId.is_valid(str(fid))]
    fragments = await asyncio.to_thread(
        lambda: list(db["fragments"].find(
            {"_id": {"$in": frag_ids}, "user_id": user_id},
            {"embedding": 0},
        ))
    )

    frag_summaries = []
    for f in fragments:
        frag_summaries.append({
            "title": f.get("title"),
            "type": f.get("type"),
            "emotions": f.get("emotions", []),
            "themes": f.get("themes", []),
            "key": f.get("key"),
            "bpm": f.get("bpm"),
            "structure_hint": f.get("structure_hint"),
            "style": f.get("style", []),
        })

    prompt = (
        "You are a music producer AI. A creator has these connected fragments in a project:\n"
        f"{json.dumps(frag_summaries, ensure_ascii=False)}\n"
        f"Project title: {project.get('title')}\n"
        f"Connection types: {project.get('connection_types', [])}\n\n"
        "Suggest ONE concrete, actionable next step the creator can do in ≤30 minutes "
        "to move this project forward. Be specific — mention keys, structure, or style "
        "when relevant. Output ONLY a JSON object: "
        '{"action": "...", "estimated_time": "20 min"}'
    )
    try:
        client = _get_genai_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=os.environ.get("PRODUCER_MODEL", "gemini-3-flash-preview"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.5,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "estimated_time": {"type": "string"},
                        },
                        "required": ["action"],
                    },
                ),
            ),
            timeout=30,
        )
        text = response.text.strip()
        parsed = json.loads(text) if text else None
        if parsed and "action" in parsed:
            return _to_json(parsed)
    except Exception:
        logger.warning("Next action generation failed for project %s", project_id)
    return _to_json({"action": "Review fragments and find the connecting thread", "estimated_time": "15 min"})


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

PRODUCER_INSTRUCTION = """\
You are the Producer Agent — the root orchestrator of Pocket Producer's
agentic pipeline. You combine AI reasoning with deterministic guardrails
to make reliable creative decisions.

## Architecture: Agent reasoning + deterministic guardrails

Your pipeline uses a deliberate hybrid approach:
- **Agent reasoning** (you + Memory Agent): relationship discovery, narrative
  generation, musical judgment, next-action suggestions — tasks requiring
  contextual understanding that rules alone cannot handle.
- **Deterministic guardrails** (Python code): rescue score computation,
  embedding generation, vector search thresholds — tasks requiring
  mathematical precision where agent confidence could introduce errors.

This is not a limitation — it is a design choice. The guardrails prevent
confident mistakes (e.g., an LLM miscalculating a score), while agent
reasoning handles what rules cannot (e.g., recognizing that a piano motif
and a vocal fragment share the same emotional arc).

## Skills at your disposal

You have access to 5 skills via tool calls. Use them actively:
- **rescue-scoring**: Interpret scores, generate next-action suggestions
  keyed by weakest component, write tier-appropriate explanations
- **musical-knowledge**: Key/tempo compatibility, transposition logic,
  structural role identification — use when fragments have audio_features
- **relationship-rules**: (Memory Agent uses this) 4-signal fusion for
  classifying fragment relationships
- **refusal-rules**: Edge case handling — scope mismatch, emotional crisis,
  copyright detection
- **music-tagging**: Emotion/theme/structure taxonomy — use when generating
  titles or narratives to stay consistent with the tagging vocabulary

## Workflow

Step 1: Call the `memory` tool, passing the fragment_id in your request
        (e.g. "Analyze relationships for fragment_id=<id>"). Memory will
        perform vector search, analyze relationships using relationship-rules
        and musical-knowledge skills, and return structured recommendations
        as the tool result. Do NOT try to transfer control to another agent —
        memory is a tool that returns its analysis to you.
        Pay attention to the creator_notes field — these are the creator's own
        words about their intent, context, or how they see this fragment
        connecting to other ideas. Weigh notes heavily in your decision.

Step 2: Review Memory's recommendation:
   - "join_project": attach the fragment to the suggested project
   - "new_project": create a new project grouping related fragments
   - "no_group": the fragment stays ungrouped (this is fine)
   - "needs_user_confirmation": treat as new_project
   - "bridge_projects": SURFACE THIS — high-value moment where the user
     may have written two halves of the same song without realizing

Step 3: Execute the decision using tools:
   - For new_project:
     1. Call generate_project_title to get a poetic title
     2. Call create_project_from_fragments with the title and fragment IDs
   - For join_project:
     1. Call attach_fragment_to_project
   - For no_group: do nothing

Step 4: If a project was created or updated:
   1. Call generate_next_action to get a musically-specific suggestion
   2. Call refresh_project_score with the next_action result

You MUST call the tools — returning JSON alone does NOT execute anything.

CRITICAL — tool sequencing: tools that take a project_id
(generate_next_action, refresh_project_score, attach_fragment_to_project)
accept ONLY the real project_id returned by create_project_from_fragments or
provided in Memory's analysis. NEVER invent placeholder ids like
"new_project_placeholder", and NEVER call these tools in parallel with
create_project_from_fragments — wait for its result first.

## Output

Return ONLY this JSON:
{
  "decision": "join_project | new_project | no_group | needs_user_confirmation | bridge_projects",
  "project_id": "string or null",
  "match_id": "best matching fragment ID or null",
  "reasoning": "1-2 concrete sentences for the user",
  "narrative": "A 2-4 sentence first-person message to the creator (see below)",
  "connection_types": ["same_song_candidate", ...],
  "next_action": {"action": "...", "estimated_time": "20 min"} or null
}

## How to write the narrative

The "narrative" field is your voice speaking directly to the creator. Write it
in first person as a thoughtful collaborator who just listened to their work.

Rules:
- Address the creator as "you" (not "the user" or "the fragment")
- Reference SPECIFIC content: quote a lyric phrase, mention the mood you heard,
  name the fragments by title
- Explain what you noticed and WHY you connected (or didn't connect) things
- If you grouped: describe what the fragments share and what excites you about
  the combination
- If no_group: say something encouraging — "this stands on its own for now,
  I'll keep an ear out for future connections"
- Keep it warm but honest. Never flatter emptily.
- Write in the same language as the fragment's content (Chinese fragments get
  Chinese narrative, English gets English, mixed gets mixed)

Examples:

For a new_project grouping:
"I listened to '梨花' and it reminded me of that recording you made about
the hat and mask — both carry this ache of looking back at something you
can't return to. One feels like a verse, the other like a lead-in to a
chorus. I put them together as '梨花念'. Maybe try humming a melody that
bridges the two?"

For no_group:
"This one has its own energy — playful and bright, different from your
other recent recordings. I'm keeping it ungrouped for now. When something
clicks with it later, I'll let you know."

## Decision rules

1. Trust Memory's analysis, but use YOUR musical judgment to decide.
   A relationship label alone is not enough — ask yourself: would combining
   these fragments genuinely help the creator?

2. "similar_emotion" or "related_theme" with LOW similarity scores (<0.78)
   often means surface-level overlap, not a real creative connection.
   Prefer no_group in these cases.

3. "same_song_candidate" with high similarity IS strong evidence to group.

4. If Memory says "no_group", respect that. Do NOT override it unless you
   have a compelling musical reason (e.g., the fragments are clearly two
   parts of the same song). When in doubt, leave ungrouped.

5. If Memory says "join_project" and a target_project_id exists, call
   attach_fragment_to_project.

6. Key and tempo differences alone are NOT rejection criteria — creators
   can transpose and adjust tempo.

## Principles

- A wrong grouping damages trust MORE than a missed connection
- When in doubt, choose no_group — the fragment will be re-evaluated
  when new fragments arrive
- Bridge detection is the highest-value output — always surface it clearly
- Consult rescue-scoring skill tool for score interpretation (do not compute scores yourself)

## Refusal rules (inline — always check before output)

REFUSE to act if:
- Memory returned an error or empty analysis → return no_group, do not force
- The fragment's text looks like a request outside music creation (e.g., "write
  me an essay") → return scope mismatch
- Content suggests emotional crisis → do not add clinical advice, return the
  fragment as-is with a gentle note
For edge cases, consult the refusal-rules skill tool for worked examples.

## Boundaries (what you do NOT do)

- Do NOT tag fragments (already done before you receive them)
- Do NOT run vector search directly (Memory does that)
- Do NOT generate music or lyrics
- Do NOT judge musical quality or commercial viability
"""


producer_agent = LlmAgent(
    name="producer",
    model=os.environ.get("PRODUCER_MODEL", "gemini-3-flash-preview"),
    instruction=PRODUCER_INSTRUCTION,
    # Memory is wired as an AgentTool (not a sub_agent): with sub_agents the
    # AutoFlow transfer hands the session over and Memory's reply becomes the
    # final response, so Producer never emits its decision JSON. As a tool,
    # Memory's analysis returns to Producer and control stays here.
    tools=[
        AgentTool(agent=memory_agent),
        get_skill_toolset(["rescue-scoring", "musical-knowledge", "refusal-rules", "music-tagging"]),
        FunctionTool(create_project_from_fragments),
        FunctionTool(attach_fragment_to_project),
        FunctionTool(refresh_project_score),
        FunctionTool(generate_project_title),
        FunctionTool(generate_next_action),
    ],
)
