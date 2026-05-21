"""Weekly job — find sleeping projects that match new fragments."""

import os
from datetime import datetime, timedelta

from pymongo import MongoClient

SLEEP_THRESHOLD_DAYS = 30
SIMILARITY_THRESHOLD = 0.85


def run():
    client = MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = client["pocketproducer"]
    fragments = db["fragments"]
    projects = db["projects"]
    notifications = db["notifications"]

    cutoff = datetime.utcnow() - timedelta(days=SLEEP_THRESHOLD_DAYS)

    sleeping_projects = list(projects.find({"last_activity_at": {"$lt": cutoff}}))
    if not sleeping_projects:
        return

    recent_fragments = list(
        fragments.find(
            {"created_at": {"$gte": cutoff}, "embedding": {"$exists": True}},
            {"embedding": 1, "user_id": 1, "raw_text": 1, "_id": 1},
        )
    )

    for frag in recent_fragments:
        if not frag.get("embedding"):
            continue

        results = list(
            fragments.aggregate(
                [
                    {
                        "$vectorSearch": {
                            "index": "fragment_semantic_idx",
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

        sleeping_project_ids = {str(p["_id"]) for p in sleeping_projects}
        for match in results:
            if match.get("project_id") and match["project_id"] in sleeping_project_ids:
                notifications.insert_one(
                    {
                        "user_id": frag["user_id"],
                        "type": "resurrect",
                        "new_fragment_id": str(frag["_id"]),
                        "sleeping_project_id": match["project_id"],
                        "similarity_score": match["score"],
                        "created_at": datetime.utcnow(),
                        "read": False,
                    }
                )


if __name__ == "__main__":
    run()
