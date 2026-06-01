"""Test clustering quality with 35 seeded fragments across 5 projects.

Verifies that vector search correctly groups related fragments and
separates unrelated ones. Uses Voyage AI for query embeddings +
MongoDB Atlas vector search. No Gemini calls needed.

Run: .venv/bin/python tests/test_clustering_quality.py
"""

import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import pytest  # noqa: E402

# Integration test — requires live MongoDB / Voyage. Skip cleanly when absent.
pymongo = pytest.importorskip("pymongo")
voyageai = pytest.importorskip("voyageai")

USER_ID = "test_30plus"

QUERIES = [
    {
        "query": "walking in the rain feeling lonely",
        "expected_cluster": "proj_rain_walk",
        "description": "rain/walking theme",
    },
    {
        "query": "bass pumping at the club, everyone dancing and jumping",
        "expected_cluster": "proj_club_energy",
        "description": "club/party theme",
    },
    {
        "query": "I miss you so much, your side of the bed is empty",
        "expected_cluster": "proj_heartbreak",
        "description": "heartbreak/missing someone",
    },
    {
        "query": "driving down the old dirt road back to where I grew up",
        "expected_cluster": "proj_hometown",
        "description": "hometown nostalgia",
    },
    {
        "query": "can't sleep, thoughts won't stop, anxiety at 3am",
        "expected_cluster": "proj_anxiety",
        "description": "anxiety/mental health",
    },
    {
        "query": "neon lights reflecting in puddles on the wet sidewalk at night",
        "expected_cluster": "proj_rain_walk",
        "description": "rain/urban imagery → rain_walk cluster",
    },
    {
        "query": "strobe lights and synth drops, the crowd goes wild",
        "expected_cluster": "proj_club_energy",
        "description": "club/electronic energy",
    },
    {
        "query": "keeping your old voicemails just to hear your voice again",
        "expected_cluster": "proj_heartbreak",
        "description": "heartbreak/memory of ex",
    },
    {
        "query": "mama's cooking and sunday morning gospel music",
        "expected_cluster": "proj_hometown",
        "description": "hometown/home cooking",
    },
    {
        "query": "heart racing, walls closing in, panic attack breathing",
        "expected_cluster": "proj_anxiety",
        "description": "anxiety/panic",
    },
]


def vector_search(db, query_emb):
    return list(
        db.fragments.aggregate(
            [
                {
                    "$vectorSearch": {
                        "index": "fragment_vector_index",
                        "path": "embedding",
                        "queryVector": query_emb,
                        "numCandidates": 50,
                        "limit": 5,
                        "filter": {"user_id": USER_ID},
                    }
                },
                {
                    "$project": {
                        "raw_input": 1,
                        "project_id": 1,
                        "tags": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]
        )
    )


def main():
    mongo = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = mongo["pocketproducer"]
    vc = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    count = db.fragments.count_documents({"user_id": USER_ID})
    print(f"Fragments in DB: {count}")
    if count < 30:
        print("ERROR: Need 30+ fragments. Run seed_30_fragments.py first.")
        sys.exit(1)

    query_texts = [q["query"] for q in QUERIES]
    print(f"Embedding {len(query_texts)} queries...")
    all_embeddings = []
    batch_size = 3
    for i in range(0, len(query_texts), batch_size):
        if i > 0:
            time.sleep(22)
        batch = query_texts[i : i + batch_size]
        for attempt in range(3):
            try:
                result = vc.embed(batch, model="voyage-3", input_type="query")
                all_embeddings.extend(result.embeddings)
                break
            except Exception:
                if attempt < 2:
                    print("  Rate limited, waiting 30s...")
                    time.sleep(30)
                else:
                    raise
        print(f"  Embedded {min(i + batch_size, len(query_texts))}/{len(query_texts)}")

    print(f"\n{'=' * 70}")
    print(f"{'Query':<55} {'Top-1 Cluster':>15}")
    print(f"{'=' * 70}")

    correct = 0
    total = len(QUERIES)

    for idx, q in enumerate(QUERIES):
        neighbors = vector_search(db, all_embeddings[idx])
        if not neighbors:
            print(f"  {q['description']:<55} {'NO RESULTS':>15}")
            continue

        top1 = neighbors[0]
        top1_project = top1.get("project_id", "none")
        top1_score = top1["score"]

        top3_projects = [n.get("project_id", "none") for n in neighbors[:3]]
        match = top1_project == q["expected_cluster"]
        top3_match = q["expected_cluster"] in top3_projects

        if match:
            correct += 1
            status = "OK"
        elif top3_match:
            correct += 0.5
            status = "~OK (top3)"
        else:
            status = "MISS"

        print(f"  {q['description']:<45} sim={top1_score:.3f} {status:>10} got={top1_project}")

    print(f"\n{'=' * 70}")
    accuracy = correct / total * 100
    print(f"Top-1 accuracy: {correct}/{total} ({accuracy:.0f}%)")

    if accuracy >= 80:
        print("VERDICT: Clustering quality PASSED (>=80%)")
    elif accuracy >= 60:
        print("VERDICT: Clustering quality ACCEPTABLE (>=60%)")
    else:
        print("VERDICT: Clustering quality NEEDS IMPROVEMENT (<60%)")

    mongo.close()


if __name__ == "__main__":
    main()
