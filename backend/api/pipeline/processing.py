"""Background fragment processing: tagging, embedding, agent grouping orchestrator."""

import asyncio
import json
import logging
import os

from bson import ObjectId

from ..deps import get_db
from .grouping import memory_and_project
from .tagging import build_fallback_tags, tag_fragment_direct

logger = logging.getLogger(__name__)

_clap_tasks: set[asyncio.Task] = set()


def _spawn_clap_encoding(db, user_id: str, fragment_id: str, gcs_uri: str) -> None:
    """Fire-and-forget CLAP encoding so new fragments become rank-ready
    without delaying the tagging pipeline."""

    async def _run():
        try:
            from ranking.ingest import encode_audio_representation

            outcome = await encode_audio_representation(db, user_id, fragment_id, gcs_uri)
            logger.info("CLAP encoding for %s: %s", fragment_id, outcome)
        except Exception:
            logger.warning("CLAP encoding failed for %s", fragment_id, exc_info=True)

    task = asyncio.create_task(_run())
    _clap_tasks.add(task)
    task.add_done_callback(lambda t: _clap_tasks.discard(t))


def _set_step(db, fragment_id: str, user_id: str, step: str):
    db["fragments"].update_one(
        {"_id": ObjectId(fragment_id), "user_id": user_id},
        {"$set": {"pipeline_step": step}},
    )


async def process_fragment_background(
    user_id: str, fragment_id: str, audio_url: str | None, text: str | None
):
    import time

    from tools.embedding import generate_embedding

    db = get_db()
    t0 = time.monotonic()
    try:
        features_task = None
        features = None
        if audio_url:
            from tools.audio_features import extract_audio_features
            _set_step(db, fragment_id, user_id, "Listening to your audio...")
            features_task = asyncio.create_task(extract_audio_features(audio_url))
            try:
                features = await asyncio.wait_for(asyncio.shield(features_task), timeout=25)
                logger.info("Audio features ready before tagging (%.1fs)", time.monotonic() - t0)
            except TimeoutError:
                logger.info("Audio features not ready after 25s — tagging without them")
            except Exception as e:
                logger.warning("Audio features extraction failed: %s", e)
                features_task = None

        _set_step(db, fragment_id, user_id, "Analyzing emotions and themes...")
        tag_task = tag_fragment_direct(
            text=text or "",
            audio_features=features,
            audio_gcs_uri=audio_url,
        )

        embed_task = generate_embedding(text) if text else None

        if embed_task:
            tag_result, embedding = await asyncio.gather(tag_task, embed_task)
        else:
            tag_result = await tag_task
            embedding = None

        logger.info("Gemini tagging done in %.1fs (result=%s)", time.monotonic() - t0, "yes" if tag_result else "none")

        if features is None and features_task:
            try:
                features = await features_task
                logger.info("Audio features done in %.1fs", time.monotonic() - t0)
            except Exception as e:
                logger.warning("Audio features extraction failed: %s", e)

        if not tag_result and features:
            logger.info("Gemini failed — building fallback tags from librosa features")
            tag_result = build_fallback_tags(features, text)

        transcript = None
        if tag_result and tag_result.get("transcript"):
            transcript = tag_result.pop("transcript")

        if not embedding:
            _set_step(db, fragment_id, user_id, "Building memory fingerprint...")
            embed_source = transcript
            if not embed_source and tag_result:
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

        final_update: dict = {
            "status": "ready",
            "tags": [],
            "emotions": [],
            "themes": [],
            "style": [],
            "key": None,
            "bpm": None,
            "suggestion": None,
            "structure_hint": None,
            "potential": None,
            "transcript": None,
        }
        if transcript:
            final_update["raw_text"] = transcript
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
            for key in ("key", "bpm", "suggestion", "structure_hint", "potential", "transcript"):
                if tag_result.get(key):
                    final_update[key] = tag_result[key]
        if features:
            if features.get("bpm"):
                final_update["bpm"] = features["bpm"]
            if not final_update.get("key") and features.get("estimated_key"):
                mode = features.get("estimated_mode", "")
                fkey = features["estimated_key"]
                final_update["key"] = f"{fkey}m" if mode == "minor" else fkey

        db["fragments"].update_one(
            {"_id": ObjectId(fragment_id), "user_id": user_id},
            {"$set": final_update},
        )

        ai_title = (tag_result or {}).get("title")
        if isinstance(ai_title, str) and 0 < len(ai_title.strip()) <= 80:
            db["fragments"].update_one(
                {
                    "_id": ObjectId(fragment_id),
                    "user_id": user_id,
                    "$or": [
                        {"title": None},
                        {"title": {"$regex": r"^Audio fragment \d+$"}},
                    ],
                },
                {"$set": {"title": ai_title.strip()}},
            )

        if (
            audio_url
            and audio_url.startswith("gs://")
            and os.environ.get("POCKET_ENABLE_CLAP") == "1"
        ):
            _spawn_clap_encoding(db, user_id, fragment_id, audio_url)

        logger.info(
            "Fragment %s tagged in %.1fs — update=%s",
            fragment_id, time.monotonic() - t0,
            json.dumps({k: v for k, v in final_update.items() if k not in ("embedding", "audio_features")}, ensure_ascii=False, default=str)[:600],
        )

        if embedding:
            _set_step(db, fragment_id, user_id, "Searching memory for connections...")
            for _retry in range(3):
                try:
                    await memory_and_project(
                        db, user_id, fragment_id, embedding, tag_result, t0,
                        skip_if_grouped=True,
                    )
                    break
                except Exception as exc:
                    is_rate_limit = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
                    if _retry < 2:
                        delay = (10 if is_rate_limit else 2) * (_retry + 1)
                        logger.warning(
                            "Memory/project phase failed for %s (%s), retry %d in %ds...",
                            fragment_id, "rate-limited" if is_rate_limit else "error", _retry + 1, delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.exception("Memory/project phase failed for %s after 3 attempts", fragment_id)

        _set_step(db, fragment_id, user_id, "done")

    except Exception:
        logger.exception("Processing failed for fragment %s", fragment_id)
        frag_check = db["fragments"].find_one(
            {"_id": ObjectId(fragment_id), "user_id": user_id},
            {"tags": 1, "emotions": 1, "status": 1},
        )
        has_data = frag_check and (frag_check.get("tags") or frag_check.get("emotions"))
        db["fragments"].update_one(
            {"_id": ObjectId(fragment_id), "user_id": user_id},
            {"$set": {
                "status": "ready" if has_data else "error",
                "pipeline_step": "done" if has_data else "error",
            }},
        )
