"""ADK Runner for the Producer → Memory agent pipeline.

Entry point: group_fragment_with_agents(db, user_id, fragment_id)

Producer (root) delegates to Memory (sub_agent) for relationship discovery,
then executes project decisions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

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

    try:
        runner = _get_runner()
        session = await runner.session_service.create_session(
            app_name="pocket_producer",
            user_id=user_id,
        )

        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        f"Process this newly tagged fragment. fragment_id={fragment_id}\n"
                        "Delegate to Memory Agent for relationship discovery, "
                        "then decide on project grouping."
                    )
                )
            ],
        )

        final_text = None
        event_count = 0
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=message,
        ):
            event_count += 1
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
                        final_text = part.text

        result = _try_parse_json(final_text)
        logger.info(
            "Producer pipeline completed for %s: events=%d result=%s",
            fragment_id,
            event_count,
            result,
        )
        return result

    finally:
        memory_db_var.reset(mem_db_token)
        memory_user_var.reset(mem_user_token)
        producer_db_var.reset(prod_db_token)
        producer_user_var.reset(prod_user_token)
