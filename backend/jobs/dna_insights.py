"""Daily aggregation job — computes Creative DNA data. No LLM calls."""

import os
from datetime import UTC, datetime

from pymongo import MongoClient


def run(target_user_id: str | None = None):
    client = MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = client["pocketproducer"]
    fragments = db["fragments"]
    user_dna = db["user_dna"]

    try:
        user_ids = [target_user_id] if target_user_id else fragments.distinct("user_id")
        for user_id in user_ids:
            fragment_count = fragments.count_documents({"user_id": user_id})

            # Flat array fields: emotions, themes, style, structure_hint
            emotion_pipeline = [
                {"$match": {"user_id": user_id, "emotions": {"$exists": True}}},
                {"$unwind": "$emotions"},
                {"$group": {"_id": "$emotions", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            emotions = list(fragments.aggregate(emotion_pipeline))
            emotion_dist = {e["_id"]: e["count"] for e in emotions}
            dominant_emotion = emotions[0]["_id"] if emotions else None

            theme_pipeline = [
                {"$match": {"user_id": user_id, "themes": {"$exists": True}}},
                {"$unwind": "$themes"},
                {"$group": {"_id": "$themes", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
            themes = list(fragments.aggregate(theme_pipeline))

            style_pipeline = [
                {"$match": {"user_id": user_id, "style": {"$exists": True}}},
                {"$unwind": "$style"},
                {"$group": {"_id": "$style", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
            styles = list(fragments.aggregate(style_pipeline))

            structure_pipeline = [
                {"$match": {"user_id": user_id, "structure_hint": {"$exists": True, "$ne": None}}},
                {"$group": {"_id": "$structure_hint", "count": {"$sum": 1}}},
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

            # Emotion timeline — emotions aggregated by week (ISO week)
            emotion_timeline_pipeline = [
                {"$match": {"user_id": user_id, "emotions": {"$exists": True}}},
                {"$unwind": "$emotions"},
                {"$group": {
                    "_id": {
                        "week": {"$dateToString": {"format": "%Y-W%V", "date": "$created_at"}},
                        "emotion": "$emotions",
                    },
                    "count": {"$sum": 1},
                }},
                {"$sort": {"_id.week": 1}},
            ]
            timeline_raw = list(fragments.aggregate(emotion_timeline_pipeline))
            # Reshape: [{week, emotions: {name: count}}]
            weeks_map: dict[str, dict[str, int]] = {}
            for row in timeline_raw:
                wk = row["_id"]["week"]
                em = row["_id"]["emotion"]
                weeks_map.setdefault(wk, {})[em] = row["count"]
            emotion_timeline = [
                {"week": wk, "emotions": ems}
                for wk, ems in sorted(weeks_map.items())
            ]

            project_count = db["projects"].count_documents({"user_id": user_id})
            theme_dist = {t["_id"]: t["count"] for t in themes}
            hourly_dist = {str(h["_id"]): h["count"] for h in hours}

            user_dna.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "total_fragments": fragment_count,
                        "total_projects": project_count,
                        "emotions": emotion_dist,
                        "themes": theme_dist,
                        "hourly_distribution": hourly_dist,
                        "dominant_emotion": dominant_emotion,
                        "top_styles": styles,
                        "structure_distribution": structures,
                        "emotion_timeline": emotion_timeline,
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
