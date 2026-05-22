"""Daily aggregation job — computes Creative DNA data. No LLM calls."""

import os
from datetime import UTC, datetime

from pymongo import MongoClient


def run():
    client = MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = client["pocketproducer"]
    fragments = db["fragments"]
    user_dna = db["user_dna"]

    try:
        for user_id in fragments.distinct("user_id"):
            fragment_count = fragments.count_documents({"user_id": user_id})

            emotion_pipeline = [
                {"$match": {"user_id": user_id}},
                {"$unwind": "$tags.emotion"},
                {"$group": {"_id": "$tags.emotion", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            emotions = list(fragments.aggregate(emotion_pipeline))
            emotion_dist = {e["_id"]: e["count"] for e in emotions}
            dominant_emotion = emotions[0]["_id"] if emotions else None

            theme_pipeline = [
                {"$match": {"user_id": user_id}},
                {"$unwind": "$tags.theme"},
                {"$group": {"_id": "$tags.theme", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
            themes = list(fragments.aggregate(theme_pipeline))

            style_pipeline = [
                {"$match": {"user_id": user_id}},
                {"$unwind": "$tags.style"},
                {"$group": {"_id": "$tags.style", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
            styles = list(fragments.aggregate(style_pipeline))

            structure_pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": "$tags.structure_hint", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            structures = list(fragments.aggregate(structure_pipeline))

            time_pipeline = [
                {"$match": {"user_id": user_id}},
                {"$project": {"hour": {"$hour": "$created_at"}}},
                {"$group": {"_id": "$hour", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
            hours = list(fragments.aggregate(time_pipeline))
            peak = max(hours, key=lambda x: x["count"]) if hours else None

            user_dna.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "fragment_count": fragment_count,
                        "emotion_distribution": emotion_dist,
                        "dominant_emotion": dominant_emotion,
                        "top_themes": themes,
                        "top_styles": styles,
                        "structure_distribution": structures,
                        "hourly_distribution": hours,
                        "peak_hours": (
                            f"{peak['_id']}:00 - {(peak['_id'] + 2) % 24}:00"
                            if peak
                            else "N/A"
                        ),
                        "updated_at": datetime.now(UTC),
                    }
                },
                upsert=True,
            )
    finally:
        client.close()


if __name__ == "__main__":
    run()
