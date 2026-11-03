"""Re-encode stored fragments so every rank-ready representation exists.

Fragments uploaded while CLAP was disabled have no audio_semantic vector;
fragments uploaded before chroma was added have no chroma vector. Both make
their rankers (fusion, mean-session, role-gap, harmonic-fit) silently skip
the fragment. This walks every audio fragment and runs the same encoder the
ingest path uses, which writes both representations and skips fragments that
are already current.

Runs from the repo's backend/ directory with .env loaded:

  cd backend && POCKET_ENABLE_CLAP=1 .venv/bin/python -m scripts.backfill_representations
  cd backend && POCKET_ENABLE_CLAP=1 .venv/bin/python -m scripts.backfill_representations --dry-run
"""

import argparse
import logging
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("backfill")


def _load_env() -> None:
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="list what would be encoded")
    parser.add_argument("--user", help="restrict to one Firebase uid")
    args = parser.parse_args()

    _load_env()
    from api.deps import get_db
    from ranking.ingest import CHROMA_REVISION, _encode_sync

    db = get_db()
    query: dict = {"type": "audio", "audio_url": {"$regex": "^gs://"}}
    if args.user:
        query["user_id"] = args.user
    docs = list(db["fragments"].find(
        query,
        {"user_id": 1, "audio_url": 1, "representations.audio_semantic.revision": 1,
         "representations.chroma.revision": 1},
    ))
    todo = []
    for doc in docs:
        reps = doc.get("representations") or {}
        needs_audio = not (reps.get("audio_semantic") or {}).get("revision")
        needs_chroma = (reps.get("chroma") or {}).get("revision") != CHROMA_REVISION
        if needs_audio or needs_chroma:
            todo.append((doc, needs_audio, needs_chroma))
    logger.info("%d audio fragments, %d need encoding", len(docs), len(todo))
    if args.dry_run:
        for doc, a, c in todo:
            logger.info("  %s audio=%s chroma=%s", doc["_id"], "missing" if a else "ok",
                        "missing" if c else "ok")
        return 0

    counts = {"encoded": 0, "skipped": 0, "missing": 0, "failed": 0}
    for doc, _, _ in todo:
        try:
            outcome = _encode_sync(db, doc["user_id"], str(doc["_id"]), doc["audio_url"])
            counts[outcome] += 1
            logger.info("%s: %s", doc["_id"], outcome)
        except Exception:
            counts["failed"] += 1
            logger.warning("%s: failed", doc["_id"], exc_info=True)
    logger.info("done: %s", counts)
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
