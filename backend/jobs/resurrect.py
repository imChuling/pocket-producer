"""Weekly job — find sleeping projects that match new fragments."""

import os
from datetime import UTC, datetime, timedelta

from pymongo import MongoClient

SLEEP_THRESHOLD_DAYS = 30
SIMILARITY_THRESHOLD = 0.85


def run():
    client = MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = client["pocketproducer"]
    fragments = db["fragments"]
    projects = db["projects"]
    notifications = db["notifications"]

    try:
        cutoff = datetime.now(UTC) - timedelta(days=SLEEP_THRESHOLD_DAYS)

        recent_fragments = list(
            fragments.find(
                {"created_at": {"$gte": cutoff}, "embedding": {"$exists": True}},
                {"embedding": 1, "user_id": 1, "raw_input": 1, "_id": 1},
            )
        )

        user_ids = {f["user_id"] for f in recent_fragments if f.get("embedding")}
        sleeping_by_user: dict[str, list] = {}
        if user_ids:
            for proj in projects.find(
                {"user_id": {"$in": list(user_ids)}, "last_activity_at": {"$lt": cutoff}},
            ):
                sleeping_by_user.setdefault(proj["user_id"], []).append(proj)

        for frag in recent_fragments:
            if not frag.get("embedding"):
                continue

            user_sleeping = sleeping_by_user.get(frag["user_id"], [])
            if not user_sleeping:
                continue

            results = list(
                fragments.aggregate(
                    [
                        {
                            "$vectorSearch": {
                                "index": "fragment_vector_index",
                                "path": "embedding",
                                "queryVector": frag["embedding"],
                                "numCandidates": 100,
                                "limit": 10,
                                "filter": {"user_id": frag["user_id"]},
                            }
                        },
                        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
                        {"$match": {"score": {"$gte": SIMILARITY_THRESHOLD}}},
                    ]
                )
            )

            sleeping_project_ids = {str(p["_id"]) for p in user_sleeping}
            for match in results:
                if match.get("project_id") and match["project_id"] in sleeping_project_ids:
                    notifications.insert_one(
                        {
                            "user_id": frag["user_id"],
                            "type": "resurrect",
                            "new_fragment_id": str(frag["_id"]),
                            "sleeping_project_id": match["project_id"],
                            "similarity_score": match["score"],
                            "created_at": datetime.now(UTC),
                            "read": False,
                        }
                    )
    finally:
        client.close()


if __name__ == "__main__":
    run()
