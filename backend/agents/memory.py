"""Memory Agent (Grounding layer) — real, actively running in the pipeline.

Responsibilities:
- Vector search for similar past fragments (via MongoDB MCP or direct tools)
- Relationship classification using relationship-rules + musical-knowledge skills
- Returns structured analysis to Producer Agent (never writes to DB)
"""

import asyncio
import json
import logging
import os
from contextvars import ContextVar
from typing import Any

from bson import ObjectId
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ._skills_loader import get_skill_toolset

logger = logging.getLogger(__name__)

_current_user_id: ContextVar[str] = ContextVar("memory_agent_user_id")
_current_db: ContextVar[Any] = ContextVar("memory_agent_db")


class _JSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        from datetime import datetime
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
# Read-only tools for Memory Agent
# ---------------------------------------------------------------------------


async def get_fragment_context(fragment_id: str) -> str:
    """Return a fragment's full metadata (excluding embedding vector)."""
    db = _db()
    user_id = _user_id()
    doc = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"embedding": 0},
    )
    return _to_json({"fragment": doc})


async def vector_search_fragment_neighbors(fragment_id: str, limit: int = 6) -> str:
    """Find semantically similar fragments using MongoDB Atlas Vector Search.

    Uses the fragment's embedding to find neighbors. Returns documents with
    cosine similarity scores. Excludes the query fragment itself.
    """
    db = _db()
    user_id = _user_id()
    fragment = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"embedding": 1},
    )
    if not fragment or not fragment.get("embedding"):
        return _to_json({"neighbors": [], "reason": "fragment_missing_or_no_embedding"})

    default_threshold = float(os.environ.get("SIMILARITY_THRESHOLD", "0.55"))
    user_settings = await asyncio.to_thread(
        db["user_settings"].find_one,
        {"user_id": user_id},
        {"sensitivity": 1},
    )
    threshold = (
        user_settings["sensitivity"]["threshold"]
        if user_settings and "sensitivity" in user_settings
        else default_threshold
    )

    pipeline = [
        {
            "$vectorSearch": {
                "index": "fragment_vector_index",
                "path": "embedding",
                "queryVector": fragment["embedding"],
                "numCandidates": 100,
                "limit": max(2, min(limit, 10)),
                "filter": {"user_id": user_id},
            }
        },
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$match": {
            "_id": {"$ne": ObjectId(fragment_id)},
            "score": {"$gte": threshold},
            "status": "ready",
        }},
        {"$project": {"embedding": 0}},
    ]
    neighbors = await asyncio.to_thread(lambda: list(db["fragments"].aggregate(pipeline)))
    return _to_json({"neighbors": neighbors, "threshold_applied": threshold})


async def get_project_context(project_id: str) -> str:
    """Return a project and all its member fragments (excluding embeddings)."""
    db = _db()
    user_id = _user_id()
    project = await asyncio.to_thread(
        db["projects"].find_one,
        {"_id": ObjectId(project_id), "user_id": user_id},
    )
    if not project:
        return _to_json({"project": None, "fragments": []})

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
    return _to_json({"project": project, "fragments": fragments})


# ---------------------------------------------------------------------------
# MCP toolset (optional, for demo visibility)
# ---------------------------------------------------------------------------


def _build_mcp_toolset():
    """Attach read-only MongoDB MCP tools when enabled."""
    if os.environ.get("ENABLE_MCP_MEMORY_TOOLS") != "1":
        return None
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        return None
    try:
        from google.adk.tools.mcp_tool import McpToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            SseConnectionParams,
            StreamableHTTPConnectionParams,
        )
        params = (
            SseConnectionParams(url=mcp_url)
            if mcp_url.endswith("/sse")
            else StreamableHTTPConnectionParams(url=mcp_url)
        )
        logger.info("MemoryAgent: mounting read-only MongoDB MCP from %s", mcp_url)
        return McpToolset(
            connection_params=params,
            tool_filter=[
                "find", "aggregate", "vector-search",
                "mongodb.find", "mongodb.aggregate", "mongodb.vector-search",
            ],
            tool_name_prefix="mongo_mcp",
        )
    except Exception:
        logger.exception("Failed to configure MongoDB MCP toolset for MemoryAgent")
        return None


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

MEMORY_INSTRUCTION = """\
You are the Memory Agent (Grounding layer) of Pocket Producer.

Your ONLY job: given a new fragment, find related past fragments and classify
their relationships. You NEVER write to the database.

## Workflow

1. Call get_fragment_context for the new fragment to understand its content.
2. Call vector_search_fragment_neighbors to find semantically similar fragments.
3. DISCARD any neighbor with similarity_score below the threshold returned by vector_search_fragment_neighbors.
4. For each remaining neighbor, you MUST consult the relationship-rules skill
   tool to get the 4-signal fusion rules, classification thresholds, and
   worked examples. The skill defines exactly how to evaluate:
   - emotional_alignment, thematic_alignment, musical_compatibility, temporal_pattern
5. When both fragments have audio_features (key, BPM), consult the
   musical-knowledge skill tool for key/tempo compatibility algorithms.
6. If a neighbor already belongs to a project, call get_project_context to
   understand that project's scope before recommending joining it.

## Hard rejection rules (ALWAYS apply, even before consulting skills)

REJECT a connection (classify as "unrelated") if:
- Similarity score is below the threshold returned by vector_search_fragment_neighbors.

NOTE on musical compatibility: Key and tempo differences are NOT rejection
criteria. Creators routinely transpose keys and adjust tempos when combining
ideas. A melody in Am at 72 BPM and a vocal in C at 140 BPM can absolutely
be part of the same song. Evaluate musical_compatibility as a SIGNAL (strong/
weak/n/a), but never use it alone to reject a connection.

For ALL other classification decisions (same_song_candidate vs related_theme
vs similar_emotion vs unrelated), you MUST follow the thresholds and
multi-signal fusion logic defined in the relationship-rules skill. Do not
guess — call the skill tool to load the rules.

## Output

Return ONLY this JSON structure:
{
  "analysis": [
    {
      "neighbor_id": "...",
      "neighbor_title": "...",
      "similarity_score": 0.82,
      "relationship": "same_song_candidate | related_theme | similar_emotion | unrelated",
      "signals": {
        "emotional_alignment": "strong | weak | conflicting | unknown",
        "thematic_alignment": "strong | weak | conflicting | unknown",
        "musical_compatibility": "strong | weak | conflicting | n/a",
        "temporal_pattern": "active_project | dormant | unrelated_in_time"
      },
      "evidence": "specific reasons with concrete details from both fragments",
      "project_id": "... or null",
      "project_title": "... or null"
    }
  ],
  "recommendation": {
    "action": "join_project | new_project | no_group | needs_user_confirmation",
    "target_project_id": "... or null",
    "group_with_ids": ["fragment IDs to group together"],
    "connection_types": ["same_song_candidate", ...],
    "reasoning": "1-2 concrete sentences explaining WHY"
  }
}

## Grouping guidance

When fragments share emotional, thematic, or musical connections, group them.
A creator with 15 fragments might have 3-8 projects. Lean toward grouping when
there is reasonable evidence — creators benefit from seeing connections.

Relationship types and when to recommend grouping:
- "same_song_candidate": shared imagery, lyrical continuity, structural complement → new_project or join_project
- "related_theme": overlapping themes or subject matter → new_project or join_project
- "similar_emotion": shared emotional tone → new_project or join_project
- "unrelated": no meaningful connection → no_group

When recommending "new_project", ALWAYS include the current fragment AND at least
one neighbor in "group_with_ids". The Producer Agent needs these IDs to create the project.

## Refusal rules (inline — always check before output)

REFUSE to classify (return "unrelated" with explanation) if:
- Input fragment has no text AND no audio_features → insufficient data
- Fragment text looks like published copyrighted lyrics (exact match to known song)
- You are uncertain between two relationship types → choose the weaker one
For edge cases, consult the refusal-rules skill tool for worked examples.

## Boundaries (what you do NOT do)

- Do NOT write to the database
- Do NOT create or modify projects
- Do NOT generate creative suggestions or next actions
- Do NOT communicate directly with the user
"""


def build_memory_agent() -> LlmAgent:
    """Build the Memory Agent with all tools and skills."""
    tools: list[Any] = [
        get_skill_toolset(["relationship-rules", "musical-knowledge", "refusal-rules"]),
        FunctionTool(get_fragment_context),
        FunctionTool(vector_search_fragment_neighbors),
        FunctionTool(get_project_context),
    ]
    mcp = _build_mcp_toolset()
    if mcp is not None:
        tools.append(mcp)

    return LlmAgent(
        name="memory",
        model=os.environ.get("MEMORY_MODEL", "gemini-2.5-flash"),
        instruction=MEMORY_INSTRUCTION,
        tools=tools,
    )


memory_agent = build_memory_agent()
