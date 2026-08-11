"""ADK Runner for the Producer → Memory agent pipeline.

Entry point: group_fragment_with_agents(db, user_id, fragment_id)

Producer (root) delegates to Memory (sub_agent) for relationship discovery,
then executes project decisions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from bson import ObjectId

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .memory import _current_db as memory_db_var
from .memory import _current_user_id as memory_user_var
from .producer import _current_db as producer_db_var
from .producer import _current_user_id as producer_user_var
from .producer import producer_agent

logger = logging.getLogger(__name__)

_runner: Runner | None = None


def _get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=producer_agent,
            app_name="pocket_producer",
            session_service=InMemorySessionService(),
        )
    return _runner


def _try_parse_json(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1])
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(stripped[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


async def group_fragment_with_agents(
    db: Any,
    user_id: str,
    fragment_id: str,
) -> dict[str, Any] | None:
    """Run the Producer → Memory agent pipeline for a processed fragment.

    Sets ContextVars for both agents so their tools can access the DB
    and enforce user_id scoping.
    """
    # Set context for both Memory and Producer tools
    mem_user_token = memory_user_var.set(user_id)
    mem_db_token = memory_db_var.set(db)
    prod_user_token = producer_user_var.set(user_id)
    prod_db_token = producer_db_var.set(db)

    session = None
    try:
        runner = _get_runner()
        session = await runner.session_service.create_session(
            app_name="pocket_producer",
            user_id=user_id,
        )

        frag_doc = await asyncio.to_thread(
            db["fragments"].find_one,
            {"_id": ObjectId(fragment_id), "user_id": user_id},
            {"title": 1, "text": 1, "notes": 1, "comments": 1, "tags": 1, "emotions": 1, "themes": 1, "key": 1, "bpm": 1},
        )
        context_parts = [f"fragment_id={fragment_id}"]
        if frag_doc:
            if frag_doc.get("title"):
                context_parts.append(f"title: {frag_doc['title']}")
            if frag_doc.get("text"):
                context_parts.append(f"text: {frag_doc['text']}")
            if frag_doc.get("notes"):
                context_parts.append(f"creator_notes: {frag_doc['notes']}")
            if frag_doc.get("comments"):
                lines = []
                for c in frag_doc["comments"]:
                    stamp = c.get("created_at")
                    stamp_str = stamp.strftime("%Y-%m-%d") if hasattr(stamp, "strftime") else str(stamp)[:10]
                    lines.append(f"  [{stamp_str}] {c.get('text', '')}")
                context_parts.append("creator_comments (thoughts over time, newest last):\n" + "\n".join(lines))
            if frag_doc.get("tags"):
                context_parts.append(f"tags: {', '.join(frag_doc['tags'])}")
            if frag_doc.get("emotions"):
                context_parts.append(f"emotions: {', '.join(frag_doc['emotions'])}")

        settings_doc = await asyncio.to_thread(
            db["user_settings"].find_one,
            {"user_id": user_id},
            {"match_mode": 1},
        )
        match_mode = (settings_doc or {}).get("match_mode", "balanced")
        match_mode_hints = {
            "strict": (
                "Match mode: STRICT. Only group fragments on high-confidence "
                "same_song_candidate evidence. When uncertain, prefer no_group "
                "over speculative connections."
            ),
            "balanced": "Match mode: BALANCED. Apply the default grouping guidance.",
            "loose": (
                "Match mode: LOOSE. The creator wants to see more speculative "
                "connections — related_theme or similar_emotion with medium "
                "confidence may justify grouping. Still never group against "
                "explicit creator intent."
            ),
        }

        prompt = (
            f"Process this newly tagged fragment.\n"
            f"{chr(10).join(context_parts)}\n\n"
            "Call the memory tool for relationship discovery, "
            "then decide on project grouping. "
            "If the creator left notes or comments, weigh them heavily — they "
            "express intent. Comments are timestamped thoughts; later comments "
            "reflect the creator's most current thinking.\n"
            f"{match_mode_hints.get(match_mode, match_mode_hints['balanced'])}"
        )

        message = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        async def _run():
            _final = None
            _count = 0
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=message,
            ):
                _count += 1
                author = getattr(event, "author", "?")
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "function_call", None):
                            logger.info(
                                "Agent tool call: agent=%s tool=%s",
                                author,
                                part.function_call.name,
                            )
                        if event.is_final_response() and getattr(part, "text", None):
                            _final = part.text
            return _final, _count

        try:
            final_text, event_count = await asyncio.wait_for(_run(), timeout=150)
        except asyncio.TimeoutError:
            logger.warning("Agent pipeline timed out (150s) for fragment %s", fragment_id)
            return None

        result = _try_parse_json(final_text)
        logger.info(
            "Producer pipeline completed for %s: events=%d result=%s",
            fragment_id,
            event_count,
            result,
        )
        return result

    finally:
        if session is not None:
            try:
                await runner.session_service.delete_session(
                    app_name="pocket_producer",
                    user_id=user_id,
                    session_id=session.id,
                )
            except Exception:
                pass
        memory_db_var.reset(mem_db_token)
        memory_user_var.reset(mem_user_token)
        producer_db_var.reset(prod_db_token)
        producer_user_var.reset(prod_user_token)
