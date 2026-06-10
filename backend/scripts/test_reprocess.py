"""Quick reprocess test: reset projects and run memory_and_project for all fragments."""

import asyncio
import os
import sys
import pathlib
import time
import logging

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault("SIMILARITY_THRESHOLD", "0.55")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")


async def main():
    import pymongo
    from api.pipeline import memory_and_project

    mongo = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = mongo["pocketproducer"]
    user_id = "fc88td234WYWloPgVgzUtLEv1SP2"

    # Reset
    deleted = db["projects"].delete_many({"user_id": user_id})
    db["fragments"].update_many(
        {"user_id": user_id},
        {"$unset": {"project_id": "", "project_title": "", "connection_reason": "", "connection_types": ""}},
    )
    print(f"Reset done (deleted {deleted.deleted_count} projects)")

    fragments = list(db["fragments"].find(
        {"user_id": user_id, "embedding": {"$exists": True}, "status": "ready"},
        {"embedding": 1, "emotions": 1, "themes": 1, "tags": 1, "structure_hint": 1, "title": 1, "text": 1},
    ))
    print(f"{len(fragments)} fragments, threshold={os.environ.get('SIMILARITY_THRESHOLD')}")

    t0 = time.monotonic()
    for i, frag in enumerate(fragments, 1):
        frag_id = str(frag["_id"])
        embedding = frag.get("embedding")
        if not embedding:
            print(f"  [{i}/{len(fragments)}] SKIP no embedding")
            continue
        tag_result = {
            "emotions": frag.get("emotions", []),
            "themes": frag.get("themes", []),
            "tags": frag.get("tags", []),
        }
        try:
            await memory_and_project(db, user_id, frag_id, embedding, tag_result, t0)
            print(f"  [{i}/{len(fragments)}] OK")
        except Exception as e:
            print(f"  [{i}/{len(fragments)}] ERROR: {e}")
            import traceback
            traceback.print_exc()

    elapsed = time.monotonic() - t0
    projects = db["projects"].count_documents({"user_id": user_id})
    assigned = db["fragments"].count_documents({"user_id": user_id, "project_id": {"$exists": True}})
    print(f"\nDone in {elapsed:.1f}s: {projects} projects, {assigned} fragments assigned")
    mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
