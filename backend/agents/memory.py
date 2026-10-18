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
import re
import time
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlparse

import httpx
from bson import ObjectId
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ranking import features as ranking_features

from ._serialization import to_json as _to_json
from ._skills_loader import get_skill_toolset

logger = logging.getLogger(__name__)

_current_user_id: ContextVar[str] = ContextVar("memory_agent_user_id")
_current_db: ContextVar[Any] = ContextVar("memory_agent_db")



def _db():
    return _current_db.get()


def _user_id() -> str:
    return _current_user_id.get()


def _normalize_ejson(doc: Any) -> Any:
    """Convert EJSON types (e.g. {"$oid": "..."}) to plain Python values."""
    if isinstance(doc, dict):
        if "$oid" in doc and len(doc) == 1:
            return doc["$oid"]
        if "$date" in doc and len(doc) == 1:
            return doc["$date"]
        return {k: _normalize_ejson(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_normalize_ejson(item) for item in doc]
    return doc


# ---------------------------------------------------------------------------
# Read-only tools for Memory Agent
# ---------------------------------------------------------------------------


async def get_fragment_context(fragment_id: str) -> str:
    """Return a fragment's full metadata (excluding embedding vector)."""
    db = _db()
    user_id = _user_id()
    if not ObjectId.is_valid(str(fragment_id)):
        return _to_json({"fragment": None, "error": "invalid_fragment_id"})
    doc = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"embedding": 0},
    )
    return _to_json({"fragment": doc})


async def vector_search_fragment_neighbors(fragment_id: str, limit: int = 6) -> str:
    """Find semantically similar fragments via MongoDB Atlas Vector Search.

    Routes through the MongoDB MCP server when available, falling back to
    direct pymongo if MCP is unreachable.
    """
    db = _db()
    user_id = _user_id()
    if not ObjectId.is_valid(str(fragment_id)):
        return _to_json({"neighbors": [], "reason": "invalid_fragment_id"})
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

    mcp_url = os.environ.get("MCP_SERVER_URL")
    if mcp_url:
        try:
            neighbors = await _mcp_vector_search(
                fragment["embedding"], fragment_id, user_id, threshold, limit, mcp_url,
            )
            logger.info(
                "Vector search via MCP: %d neighbors for %s (threshold=%.2f)",
                len(neighbors), fragment_id, threshold,
            )
            neighbors = await enrich_neighbors_with_signals(fragment_id, neighbors)
            return _to_json({"neighbors": neighbors, "threshold_applied": threshold, "via": "mcp"})
        except Exception:
            logger.warning(
                "MCP vector search failed for %s, falling back to direct pymongo",
                fragment_id, exc_info=True,
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
    neighbors = await enrich_neighbors_with_signals(fragment_id, neighbors)
    return _to_json({"neighbors": neighbors, "threshold_applied": threshold})


# mongodb-mcp-server wraps result documents in untrusted-user-data tags and
# prepends a human-readable summary block — extract only the JSON payload.
_MCP_UNTRUSTED_RE = re.compile(
    r"<untrusted-user-data-[0-9a-f-]+>\s*(.*?)\s*</untrusted-user-data-[0-9a-f-]+>",
    re.DOTALL,
)


def _collect_docs(parsed: Any, docs: list[dict]) -> None:
    if isinstance(parsed, list):
        docs.extend(p for p in parsed if isinstance(p, dict))
    elif isinstance(parsed, dict) and "documents" in parsed:
        docs.extend(p for p in parsed["documents"] if isinstance(p, dict))
    elif isinstance(parsed, dict):
        docs.append(parsed)


def _parse_mcp_documents(content: list[Any]) -> list[dict]:
    docs: list[dict] = []
    for block in content:
        text = getattr(block, "text", None)
        if not text:
            continue
        # The warning preamble itself mentions the tags, so several matches
        # exist per block — only the JSON-parsable one carries the payload.
        candidates = _MCP_UNTRUSTED_RE.findall(text) or [text]
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            _collect_docs(parsed, docs)
    return docs


class _GoogleIdTokenAuth(httpx.Auth):
    """Cloud Run service-to-service auth: attach a Google-signed ID token.

    Fails open when no ambient credentials can mint an ID token (local dev
    against a localhost MCP server stays unauthenticated).
    """

    def __init__(self, audience: str):
        self._audience = audience
        self._token: str | None = None
        self._expires_at = 0.0
        self._unavailable = False

    def auth_flow(self, request):
        if not self._unavailable and (self._token is None or time.time() >= self._expires_at):
            try:
                from google.auth.transport.requests import Request as _GAuthRequest
                from google.oauth2 import id_token as _gauth_id_token

                self._token = _gauth_id_token.fetch_id_token(_GAuthRequest(), self._audience)
                self._expires_at = time.time() + 45 * 60
            except Exception:
                self._unavailable = True
                logger.warning(
                    "No ambient credentials for MCP ID token — calling %s unauthenticated",
                    self._audience,
                )
        if self._token:
            request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


_mcp_auth_cache: dict[str, _GoogleIdTokenAuth] = {}
_LOCAL_MCP_HOSTS = {"localhost", "127.0.0.1", "mongodb-mcp"}


def _get_mcp_auth(mcp_url: str) -> httpx.Auth | None:
    """ID-token auth for a Cloud Run-hosted MCP server; None for local servers."""
    parsed = urlparse(mcp_url)
    if parsed.hostname in _LOCAL_MCP_HOSTS:
        return None
    audience = f"{parsed.scheme}://{parsed.netloc}"
    if audience not in _mcp_auth_cache:
        _mcp_auth_cache[audience] = _GoogleIdTokenAuth(audience)
    return _mcp_auth_cache[audience]


async def _mcp_vector_search(
    embedding: list[float],
    fragment_id: str,
    user_id: str,
    threshold: float,
    limit: int,
    mcp_url: str,
) -> list[dict]:
    """Execute vector search through the MongoDB MCP server."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    pipeline = [
        {
            "$vectorSearch": {
                "index": "fragment_vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 100,
                "limit": max(2, min(limit, 10)),
                "filter": {"user_id": user_id},
            }
        },
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$match": {
            "score": {"$gte": threshold},
            "status": "ready",
        }},
        {"$project": {"embedding": 0}},
    ]

    async with streamablehttp_client(url=mcp_url, auth=_get_mcp_auth(mcp_url)) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "aggregate",
                arguments={
                    "database": "pocketproducer",
                    "collection": "fragments",
                    "pipeline": pipeline,
                },
            )

    if result and result.isError:
        err_text = next(
            (getattr(b, "text", "") for b in result.content if getattr(b, "text", None)),
            "unknown MCP error",
        )
        raise RuntimeError(f"MCP aggregate failed: {err_text[:300]}")

    docs = _parse_mcp_documents(result.content if result else [])

    normalized = [_normalize_ejson(d) for d in docs]
    return [n for n in normalized if str(n.get("_id", "")) != fragment_id]


async def get_project_context(project_id: str) -> str:
    """Return a project and all its member fragments (excluding embeddings)."""
    db = _db()
    user_id = _user_id()
    if not ObjectId.is_valid(str(project_id)):
        return _to_json({"project": None, "fragments": [], "error": "invalid_project_id"})
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
# MCP query tool (user-scoped at the tool layer)
# ---------------------------------------------------------------------------

_ALLOWED_MCP_COLLECTIONS = {"fragments", "projects", "user_settings", "notifications"}


def _mcp_enabled() -> bool:
    return (
        bool(os.environ.get("MCP_SERVER_URL"))
        and os.environ.get("ENABLE_MCP_MEMORY_TOOLS") != "0"
    )


async def mongo_mcp_find(collection: str, filter: dict, limit: int = 10) -> str:
    """Query MongoDB through the MCP server (read-only).

    Every query is scoped to the authenticated user at the tool layer:
    user_id is injected after the model-supplied filter, so neither the
    model nor injected fragment content can read another user's data.
    """
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        return _to_json({"error": "mcp_unavailable"})
    if collection not in _ALLOWED_MCP_COLLECTIONS:
        return _to_json({"error": f"collection_not_allowed: {collection}"})

    if isinstance(filter, str):
        try:
            filter = json.loads(filter)
        except json.JSONDecodeError:
            return _to_json({"error": "invalid_filter_json"})
    scoped_filter = dict(filter or {})
    scoped_filter["user_id"] = _user_id()

    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url=mcp_url, auth=_get_mcp_auth(mcp_url)) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "find",
                arguments={
                    "database": "pocketproducer",
                    "collection": collection,
                    "filter": scoped_filter,
                    "limit": max(1, min(int(limit), 20)),
                    "projection": {"embedding": 0},
                },
            )

    if result and result.isError:
        err_text = next(
            (getattr(b, "text", "") for b in result.content if getattr(b, "text", None)),
            "unknown MCP error",
        )
        return _to_json({"error": f"mcp_find_failed: {err_text[:200]}"})

    docs = [_normalize_ejson(d) for d in _parse_mcp_documents(result.content if result else [])]
    return _to_json({"documents": docs, "via": "mcp", "scoped_to_user": True})


# ---------------------------------------------------------------------------
# Deterministic pairwise signal computation
# ---------------------------------------------------------------------------


def _jaccard(a: list[str], b: list[str]) -> float:
    left = {t.lower() for t in a if t}
    right = {t.lower() for t in b if t}
    union = left | right
    return len(left & right) / len(union) if union else 0.0


_STRUCTURE_COMPLEMENTS = {
    "verse_candidate": {"chorus_candidate", "hook_candidate", "bridge_candidate"},
    "chorus_candidate": {"verse_candidate", "bridge_candidate"},
    "hook_candidate": {"verse_candidate", "chorus_candidate"},
    "bridge_candidate": {"verse_candidate", "chorus_candidate"},
    "melodic_motif": {"verse_candidate", "chorus_candidate", "lyric_fragment"},
    "lyric_fragment": {"melodic_motif", "verse_candidate"},
}


def _feature_proximity(a: float | None, b: float | None, tolerance: float) -> float:
    if a is None or b is None:
        return 0.0
    ref = max(abs(a), abs(b), 1e-6)
    return max(0.0, 1.0 - abs(a - b) / (ref * tolerance))


def _temporal_proximity(src_created: Any, nbr_created: Any) -> float:
    from datetime import datetime
    def _to_dt(v: Any) -> datetime | None:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                return None
        if isinstance(v, dict) and "$date" in v:
            return _to_dt(v["$date"])
        return None
    a, b = _to_dt(src_created), _to_dt(nbr_created)
    if a is None or b is None:
        return 0.0
    days_apart = abs((a - b).total_seconds()) / 86400.0
    return 1.0 / (1.0 + days_apart / 7.0)


def _recency(nbr_created: Any, src_created: Any) -> float:
    from datetime import datetime
    def _to_iso(v: Any) -> str | None:
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, str):
            return v
        if isinstance(v, dict) and "$date" in v:
            return _to_iso(v["$date"])
        return None
    nbr_iso = _to_iso(nbr_created)
    src_iso = _to_iso(src_created)
    if not nbr_iso or not src_iso:
        return 0.0
    return ranking_features.recency(nbr_iso, src_iso)


def _structure_complement(src_hint: str | None, nbr_hint: str | None) -> float:
    if not src_hint or not nbr_hint:
        return 0.0
    if src_hint == nbr_hint:
        return 0.5
    complements = _STRUCTURE_COMPLEMENTS.get(src_hint, set())
    return 1.0 if nbr_hint in complements else 0.0


def _compute_pairwise_signals(
    source: dict, neighbor: dict,
) -> dict[str, float]:
    """Compute deterministic ranking signals between two fragments.

    Reuses the same feature functions as the Audiotool ranker and adds
    tag-level overlap signals so that the Memory Agent gets hard numbers
    instead of having to infer compatibility from raw metadata.
    """
    src_bpm = source.get("bpm")
    nbr_bpm = neighbor.get("bpm")
    src_key = source.get("key")
    nbr_key = neighbor.get("key")
    src_tags = source.get("tags") or []
    nbr_tags = neighbor.get("tags") or []
    src_emotions = source.get("emotions") or []
    nbr_emotions = neighbor.get("emotions") or []
    src_themes = source.get("themes") or []
    nbr_themes = neighbor.get("themes") or []
    src_style = source.get("style") or []
    nbr_style = neighbor.get("style") or []

    src_af = source.get("audio_features") or {}
    nbr_af = neighbor.get("audio_features") or {}

    return {
        # --- from ranking/features.py (shared with Audiotool ranker) ---
        "tempo_match": round(ranking_features.tempo_match(src_bpm, nbr_bpm), 3),
        "key_match_exact": round(ranking_features.key_match(src_key, nbr_key, mode="exact"), 3),
        "key_match_relative": round(ranking_features.key_match(src_key, nbr_key, mode="relative"), 3),
        "key_match_fifth": round(ranking_features.key_match(src_key, nbr_key, mode="fifth"), 3),
        "tag_overlap": round(ranking_features.tag_overlap(src_tags, nbr_tags), 3),
        "track_gap": round(ranking_features.track_gap([], nbr_tags, src_tags), 3),
        "novelty": round(ranking_features.novelty(nbr_tags, [], source.get("notes") or "", src_tags), 3),
        "intent_match": round(ranking_features.intent_match(
            source.get("notes") or "", nbr_tags,
        ), 3),
        "recency": round(_recency(neighbor.get("created_at"), source.get("created_at")), 3),
        # --- tag-level overlaps ---
        "emotion_overlap": round(_jaccard(src_emotions, nbr_emotions), 3),
        "theme_overlap": round(_jaccard(src_themes, nbr_themes), 3),
        "style_overlap": round(_jaccard(src_style, nbr_style), 3),
        # --- structural complementarity ---
        "structure_complement": round(_structure_complement(
            source.get("structure_hint"), neighbor.get("structure_hint"),
        ), 3),
        # --- audio feature proximity (timbral compatibility) ---
        "brightness_proximity": round(_feature_proximity(
            src_af.get("brightness"), nbr_af.get("brightness"), 0.5,
        ), 3),
        "onset_density_proximity": round(_feature_proximity(
            src_af.get("onset_density"), nbr_af.get("onset_density"), 0.5,
        ), 3),
        "energy_proximity": round(_feature_proximity(
            src_af.get("energy_mean"), nbr_af.get("energy_mean"), 0.5,
        ), 3),
        # --- temporal proximity (same creative session) ---
        "temporal_proximity": round(_temporal_proximity(
            source.get("created_at"), neighbor.get("created_at"),
        ), 3),
    }


async def enrich_neighbors_with_signals(
    fragment_id: str, neighbors: list[dict],
) -> list[dict]:
    """Attach pre-computed pairwise signals to each neighbor document."""
    db = _db()
    user_id = _user_id()
    source = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"embedding": 0},
    )
    if not source:
        return neighbors

    for nbr in neighbors:
        nbr["computed_signals"] = _compute_pairwise_signals(source, nbr)

    return neighbors


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

MEMORY_INSTRUCTION = """\
You are the Memory Agent (Grounding layer) of Pocket Producer.

Your ONLY job: given a new fragment, find related past fragments and classify
their relationships. You NEVER write to the database.

## Workflow

1. Call get_fragment_context for the new fragment to understand its content.
   Pay special attention to `notes` and `comments` — the creator's own words
   about intent. An explicit connection stated there (e.g. "this goes with
   the rain song") overrides embedding similarity; an explicit separation
   ("standalone idea") caps the relationship at related_theme.
2. Call vector_search_fragment_neighbors to find semantically similar fragments.
   Each neighbor now includes a `computed_signals` object with pre-computed
   deterministic scores (all normalized 0-1):

   Musical signals (shared with the Audiotool ranker):
   - `tempo_match`: how close the BPMs are (1.0 = identical, 0.0 = >25% apart)
   - `key_match_exact`: 1.0 if same key and mode, else 0.0
   - `key_match_relative`: 1.0 if exact OR relative major/minor (Am=C), else 0.0
   - `key_match_fifth`: adds 0.5 for tonic a fifth apart (Camelot neighbors)
   - `tag_overlap`: Jaccard overlap of tag sets (1.0 = identical tags)
   - `track_gap`: 1.0 if neighbor adds a role (drums/bass/melody/vocal/etc.)
     the source fragment lacks; 0.0 otherwise
   - `novelty`: fraction of the neighbor's tags that are NOT in the source
     (1.0 = entirely new material, 0.0 = nothing new)
   - `intent_match`: overlap between the source fragment's notes (creator's
     stated intent) and the neighbor's tags (1.0 = notes keywords fully
     matched by neighbor tags, 0.0 = no match or no notes)
   - `recency`: how recently the neighbor was created relative to the source
     fragment (1.0 = same time, 0.5 = ~30 days older, decaying with a
     30-day half-life)

   Semantic signals (computed from Gemini tagging results):
   - `emotion_overlap`: Jaccard overlap of emotion tags (1.0 = identical emotions)
   - `theme_overlap`: Jaccard overlap of theme tags (1.0 = identical themes)
   - `style_overlap`: Jaccard overlap of style tags
   - `structure_complement`: 1.0 if structure hints are complementary
     (e.g. verse + chorus), 0.5 if same hint, 0.0 if unrelated or missing

   Audio feature proximity (timbral compatibility from librosa analysis):
   - `brightness_proximity`: how close the spectral centroids are (1.0 = same
     brightness/warmth, 0.0 = very different tonal character)
   - `onset_density_proximity`: how similar the rhythmic density is (1.0 =
     same attack rate, 0.0 = sparse vs dense mismatch)
   - `energy_proximity`: how close the RMS energy levels are (1.0 = same
     loudness range)

   Temporal signal:
   - `temporal_proximity`: 1.0 if created at the same time, 0.5 if ~7 days
     apart, decaying further. High values suggest the same creative session.

   USE THESE SCORES directly in your evaluation:
   - musical_compatibility: tempo_match >= 0.6 AND key_match_relative >= 0.5
     means "strong"; both at 0.0 means "conflicting"
   - emotional_alignment: emotion_overlap >= 0.3 supports "strong"
   - thematic_alignment: theme_overlap >= 0.3 supports "strong"
   - structure_complement = 1.0 is strong evidence for same_song_candidate
   - track_gap = 1.0 means the neighbor fills a missing role (valuable for
     project composition)
   - novelty >= 0.5 means the neighbor brings mostly new tags (diversity)
   - intent_match >= 0.5 means the creator's notes describe what this
     neighbor offers (strong evidence for deliberate connection)
   - recency >= 0.5 means the neighbor is relatively recent (current work)
   - brightness_proximity >= 0.7 AND energy_proximity >= 0.7 means the
     fragments have compatible timbral character (supports same_song_candidate)
   - temporal_proximity >= 0.8 suggests the fragments were created in the
     same creative burst (supports grouping into the same project)
3. DISCARD any neighbor with similarity_score below the threshold returned by vector_search_fragment_neighbors.
4. For each remaining neighbor, you MUST consult the relationship-rules skill
   tool to get the 4-signal fusion rules, classification thresholds, and
   worked examples. The skill defines exactly how to evaluate:
   - emotional_alignment, thematic_alignment, musical_compatibility, temporal_pattern
   Integrate the computed_signals into your evaluation: use tag_overlap for
   thematic evidence, tempo_match + key_match for musical_compatibility.
5. If a neighbor already belongs to a project, call get_project_context to
   understand that project's scope before recommending joining it.

## Hard rejection rules (ALWAYS apply, even before consulting skills)

REJECT a connection (classify as "unrelated") if:
- Similarity score is below the threshold returned by vector_search_fragment_neighbors.

NOTE on musical compatibility: Key and tempo differences are NOT rejection
criteria. Creators routinely transpose keys and adjust tempos when combining
ideas. Use the pre-computed `computed_signals` to evaluate musical_compatibility:
- tempo_match >= 0.6 AND key_match_relative >= 0.5 → "strong"
- tempo_match >= 0.3 OR key_match_fifth >= 0.5 → "weak"
- tempo_match == 0.0 AND all key_match variants == 0.0 → "conflicting"
- Both fragments lack audio_features (scores all 0.0) → "n/a"
Never use musical_compatibility alone to reject a connection.

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


MEMORY_MCP_ADDENDUM = """

## MongoDB MCP Integration

This agent is connected to the MongoDB MCP server for database reads.
The vector_search_fragment_neighbors tool already routes through MCP internally.

You also have the **mongo_mcp_find** tool — a read-only query routed through
the MCP server. Every query is automatically scoped to the current user at
the tool layer; you do not need to (and cannot) set user_id yourself.

When a neighbor belongs to a project (has a project_id), use **mongo_mcp_find**
to look up the project context:

  mongo_mcp_find(collection="projects", filter={"_id": {"$oid": "<project_id>"}})

This gives you the full project document (title, fragment_ids, connection_types,
rescue_score, etc.) so you can evaluate whether the new fragment belongs there.

Collections available: fragments, projects, user_settings, notifications
"""


def build_memory_agent() -> LlmAgent:
    """Build the Memory Agent with all tools and skills."""
    tools: list[Any] = [
        get_skill_toolset(["relationship-rules", "musical-knowledge", "refusal-rules"]),
        FunctionTool(get_fragment_context),
        FunctionTool(vector_search_fragment_neighbors),
    ]

    if _mcp_enabled():
        tools.append(FunctionTool(mongo_mcp_find))
        instruction = MEMORY_INSTRUCTION + MEMORY_MCP_ADDENDUM
        logger.info("Memory Agent: MCP enabled, project lookups will use mongo_mcp_find (user-scoped)")
    else:
        tools.append(FunctionTool(get_project_context))
        instruction = MEMORY_INSTRUCTION
        logger.info("Memory Agent: MCP not available, using direct pymongo tools")

    return LlmAgent(
        name="memory",
        model=os.environ.get("MEMORY_MODEL", "gemini-3-flash-preview"),
        instruction=instruction,
        tools=tools,
    )


memory_agent = build_memory_agent()
