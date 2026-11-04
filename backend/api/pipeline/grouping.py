"""Memory/project agent grouping and next-action generation."""

import asyncio
import json
import logging

from bson import ObjectId

logger = logging.getLogger(__name__)


def _set_step(db, fragment_id: str, user_id: str, step: str):
    db["fragments"].update_one(
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"$set": {"pipeline_step": step}},
    )


async def memory_and_project(
    db, user_id: str, fragment_id: str,
    embedding: list[float], tag_result: dict | None, t0: float,
    skip_if_grouped: bool = False,
):
    if not embedding:
        logger.info("Fragment %s has no embedding — skipping agent pipeline", fragment_id)
        return

    from ..deps import get_user_agent_lock
    user_lock = await get_user_agent_lock(user_id)
    async with user_lock:
        await _memory_and_project_locked(db, user_id, fragment_id, tag_result, t0, skip_if_grouped)


async def _memory_and_project_locked(
    db, user_id: str, fragment_id: str, tag_result: dict | None, t0: float,
    skip_if_grouped: bool = False,
):
    import time

    from agents import group_fragment_with_agents
    from agents.producer import (
        _current_db as producer_db_var,
    )
    from agents.producer import (
        _current_user_id as producer_user_var,
    )
    from agents.producer import (
        attach_fragment_to_project,
        create_project_from_fragments,
        generate_next_action,
        generate_project_title,
        refresh_project_score,
    )

    existing = await asyncio.to_thread(
        db["fragments"].find_one,
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"_id": 1, "project_id": 1},
    )
    old_project_id = existing.get("project_id") if existing else None
    if old_project_id and skip_if_grouped:
        _set_step(db, fragment_id, user_id, "Grouped into a project")
        logger.info("Fragment %s already grouped into %s by a sibling run — skipping", fragment_id, old_project_id)
        return
    if old_project_id:
        logger.info("Fragment %s removing from project %s for re-evaluation", fragment_id, old_project_id)
        db["fragments"].update_one(
            {"_id": ObjectId(fragment_id), "user_id": user_id},
            {"$unset": {"project_id": "", "project_title": "", "connection_reason": "", "connection_types": "", "agent_narrative": ""}},
        )
        remaining = db["fragments"].count_documents({"user_id": user_id, "project_id": old_project_id})
        if remaining < 2:
            db["projects"].delete_one({"_id": ObjectId(old_project_id), "user_id": user_id})
            if remaining == 1:
                db["fragments"].update_many(
                    {"user_id": user_id, "project_id": old_project_id},
                    {"$unset": {"project_id": "", "project_title": "", "connection_reason": "", "connection_types": "", "agent_narrative": ""}},
                )
            logger.info("Dissolved project %s (only %d fragments left)", old_project_id, remaining)

    result = await group_fragment_with_agents(db, user_id, fragment_id)
    logger.info(
        "Producer->Memory pipeline result for %s after %.1fs: %s",
        fragment_id, time.monotonic() - t0, result,
    )

    narrative = (result.get("narrative") or "") if result else ""
    if narrative:
        db["fragments"].update_one(
            {"_id": ObjectId(fragment_id), "user_id": user_id},
            {"$set": {"agent_narrative": narrative}},
        )

    post_run = db["fragments"].find_one(
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"project_id": 1, "project_title": 1},
    )
    if post_run and post_run.get("project_id"):
        ptitle = post_run.get("project_title", "")
        _set_step(db, fragment_id, user_id, f"Joined project: {ptitle}" if ptitle else "Grouped into a project")
        logger.info("Agent tools already handled fragment %s → project %s", fragment_id, post_run["project_id"])
        pid = str(post_run["project_id"])
        proj = db["projects"].find_one(
            {"_id": ObjectId(pid), "user_id": user_id}, {"rescue_score": 1}
        ) if ObjectId.is_valid(pid) else None
        if proj and proj.get("rescue_score") is None:
            db_token = producer_db_var.set(db)
            user_token = producer_user_var.set(user_id)
            try:
                na = (result or {}).get("next_action")
                await refresh_project_score(
                    project_id=pid,
                    next_action=json.dumps(na, ensure_ascii=False) if na else None,
                )
                logger.info("Backstop rescue score computed for project %s", pid)
            except Exception:
                logger.warning("Backstop rescue score failed for %s", pid, exc_info=True)
            finally:
                producer_db_var.reset(db_token)
                producer_user_var.reset(user_token)
        return

    if not result:
        return

    rec = result.get("recommendation", {})
    action = result.get("decision") or rec.get("action") or "no_group"
    group_ids = rec.get("group_with_ids", [])
    connection_types = result.get("connection_types") or rec.get("connection_types") or []
    reasoning = result.get("reasoning") or rec.get("reasoning") or ""
    target_project_id = result.get("project_id") or rec.get("target_project_id")

    if action == "bridge_projects":
        bridge_pids = {e.get("project_id") for e in result.get("analysis", []) if e.get("project_id")}
        if len(bridge_pids) >= 2:
            all_fids = {fragment_id}
            for pid in bridge_pids:
                proj = db["projects"].find_one({"_id": ObjectId(pid), "user_id": user_id})
                if proj:
                    all_fids.update(proj.get("fragment_ids", []))
            for pid in bridge_pids:
                db["projects"].delete_one({"_id": ObjectId(pid), "user_id": user_id})
                db["fragments"].update_many(
                    {"user_id": user_id, "project_id": pid},
                    {"$unset": {"project_id": "", "project_title": "", "connection_reason": "", "connection_types": "", "agent_narrative": ""}},
                )
            group_ids = list(all_fids)
            logger.info("Bridge: merged %d projects → %d fragments", len(bridge_pids), len(group_ids))
        action = "new_project"

    if action in ("needs_user_confirmation",):
        action = "new_project"

    if action == "new_project":
        if fragment_id not in group_ids:
            group_ids = [fragment_id] + group_ids
        assigned_docs = db["fragments"].find(
            {"_id": {"$in": [ObjectId(gid) for gid in group_ids]}, "user_id": user_id, "project_id": {"$exists": True}},
            {"_id": 1},
        )
        assigned = {str(d["_id"]) for d in assigned_docs}
        if assigned:
            group_ids = [gid for gid in group_ids if gid not in assigned]

    if action == "no_group" or (action == "new_project" and len(group_ids) < 2):
        logger.info("Pipeline: no grouping for %s (action=%s, ids=%d)", fragment_id, action, len(group_ids))
        return

    logger.info("Pipeline fallback: action=%s ids=%d target=%s", action, len(group_ids), target_project_id)

    db_token = producer_db_var.set(db)
    user_token = producer_user_var.set(user_id)
    try:
        project_id = None
        conn = connection_types or ["similar_emotion"]
        reason = narrative or reasoning

        if action == "new_project":
            _set_step(db, fragment_id, user_id, "Creating a new project...")
            title_resp = await generate_project_title(fragment_ids=group_ids, connection_types=conn)
            title_parsed = json.loads(title_resp) if isinstance(title_resp, str) else title_resp
            title = title_parsed.get("title", "Untitled Project")
            resp = await create_project_from_fragments(
                title=title, fragment_ids=group_ids,
                connection_reason=reason, connection_types=conn,
            )
            parsed = json.loads(resp) if isinstance(resp, str) else resp
            project_id = parsed.get("project_id")
            logger.info("Created project %s: %s", project_id, title)
        elif action == "join_project" and target_project_id:
            _set_step(db, fragment_id, user_id, "Found a matching project...")
            await attach_fragment_to_project(
                fragment_id=fragment_id, project_id=target_project_id,
                connection_reason=reason, connection_types=conn,
            )
            project_id = target_project_id
            logger.info("Attached %s to project %s", fragment_id, project_id)

        if project_id:
            try:
                na_resp, score_resp = await asyncio.gather(
                    generate_next_action(project_id=project_id),
                    refresh_project_score(project_id=project_id, next_action=None),
                    return_exceptions=True,
                )
                if not isinstance(na_resp, Exception):
                    na_parsed = json.loads(na_resp) if isinstance(na_resp, str) else na_resp
                    if na_parsed and "action" in na_parsed:
                        await refresh_project_score(
                            project_id=project_id,
                            next_action=json.dumps(na_parsed, ensure_ascii=False),
                        )
            except Exception:
                logger.warning("Rescue score failed for %s", project_id)
    finally:
        producer_db_var.reset(db_token)
        producer_user_var.reset(user_token)


async def generate_next_action_for_project(db, user_id: str, project_id: str) -> dict | None:
    from agents.producer import (
        _current_db as producer_db_var,
    )
    from agents.producer import (
        _current_user_id as producer_user_var,
    )
    from agents.producer import (
        generate_next_action,
    )

    db_token = producer_db_var.set(db)
    user_token = producer_user_var.set(user_id)
    try:
        resp = await generate_next_action(project_id=project_id)
        parsed = json.loads(resp) if isinstance(resp, str) else resp
        return parsed if parsed and "action" in parsed else None
    except Exception:
        logger.exception("Failed to generate next action for project %s", project_id)
        return None
    finally:
        producer_db_var.reset(db_token)
        producer_user_var.reset(user_token)
