"""Test Memory Agent's relationship classification with real vector search.

Run: .venv/bin/python tests/test_memory_classification.py
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import google.genai as genai  # noqa: E402
import pymongo  # noqa: E402
import voyageai  # noqa: E402

SKILLS_DIR = pathlib.Path(__file__).parent.parent / "skills"

MEMORY_INSTRUCTION = """\
You are the Memory Agent (Grounding layer) of Pocket Producer.

You are given a new fragment and its vector search neighbors (already retrieved).
Classify the relationship between the new fragment and each neighbor.

## Relationship Types
- same_song_candidate: fragments likely belong to the same song/project
- related_theme: share thematic elements but probably different songs
- similar_emotion: share emotional tone but different content
- unrelated: no meaningful connection

## The Four Signals
1. emotional_alignment: Compare emotion tags (strong/weak/conflicting/unknown)
2. thematic_alignment: Compare theme tags (strong/weak/conflicting/unknown)
3. musical_compatibility: Compare BPM (within 15 = compatible), key compatibility
   (same key or relative major/minor = strong), (strong/weak/conflicting/unknown/n/a)
4. temporal_pattern: active_project (<7 days) / dormant (7-30 days) /
   unrelated_in_time (>30 days)

## Classification Rules
- same_song_candidate: similarity >= 0.80 AND 3+ strong signals
- same_song_candidate: similarity >= 0.75 AND emotional + thematic both strong
  AND musical compatible
- related_theme: thematic_alignment strong, other signals mixed
- similar_emotion: emotional_alignment strong, thematic weak/conflicting
- unrelated: similarity < 0.70 OR 2+ conflicting signals

Conservative bias: when uncertain, choose the WEAKER relationship type.

## suggested_action Rules
- join_project: best_match is same_song_candidate with high confidence
- bridge_projects: two matches from DIFFERENT projects, both related_theme+
- new_project: no same_song_candidate found
- needs_user_confirmation: best_match is same_song_candidate with low/medium
  confidence

Output ONLY valid JSON matching this schema:
{
  "matches": [
    {
      "fragment_id": "string",
      "similarity": 0.0,
      "relationship": "same_song_candidate | related_theme | similar_emotion | unrelated",
      "confidence": "high | medium | low",
      "signals": {
        "emotional_alignment": "strong | weak | conflicting | unknown",
        "thematic_alignment": "strong | weak | conflicting | unknown",
        "musical_compatibility": "strong | weak | conflicting | unknown | n/a",
        "temporal_pattern": "active_project | dormant | unrelated_in_time"
      },
      "reasoning": "string"
    }
  ],
  "total_neighbors_evaluated": 0,
  "best_match_id": "string | null",
  "suggested_action": "join_project | bridge_projects | new_project | needs_user_confirmation"
}
"""

QUERIES = [
    {
        "input": "Walking alone in the drizzle, humming a tune I can't name yet",
        "description": "Should match rain/walking seeds (same_song_candidate or related_theme)",
        "expect_action": ["join_project", "needs_user_confirmation"],
    },
    {
        "input": "Drop the beat, speakers shaking, everyone jumping",
        "description": "Should match BASS DROP seed, unrelated to rain songs",
        "expect_action": ["new_project", "join_project"],
    },
]


def run_vector_search(db, query_emb, user_id="test_memory"):
    results = list(db.fragments.aggregate([
        {
            "$vectorSearch": {
                "index": "fragment_vector_index",
                "path": "embedding",
                "queryVector": query_emb,
                "numCandidates": 20,
                "limit": 5,
                "filter": {"user_id": user_id},
            }
        },
        {
            "$project": {
                "raw_input": 1,
                "tags": 1,
                "audio_features": 1,
                "created_at": 1,
                "project_id": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]))
    return results


def format_neighbors_for_prompt(neighbors):
    lines = []
    for n in neighbors:
        lines.append(f"- fragment_id: {n['_id']}")
        lines.append(f"  similarity: {n['score']:.4f}")
        lines.append(f"  raw_input: {n['raw_input']}")
        lines.append(f"  emotions: {n['tags'].get('emotion', [])}")
        lines.append(f"  themes: {n['tags'].get('theme', [])}")
        lines.append(f"  style: {n['tags'].get('style', [])}")
        lines.append(f"  structure: {n['tags'].get('structure_hint')}")
        af = n.get("audio_features") or {}
        lines.append(f"  bpm: {af.get('bpm', 'n/a')}  key: {af.get('key', 'n/a')}")
        lines.append(f"  created_at: {n.get('created_at', 'unknown')}")
        lines.append(f"  project_id: {n.get('project_id', 'none')}")
        lines.append("")
    return "\n".join(lines)


def test_classification(gemini, db, vc, query, index):
    print(f"\n{'='*60}")
    print(f"Test {index + 1}: {query['input'][:55]}...")
    print(f"Expect: {query['description']}")
    print(f"{'='*60}")

    query_emb = vc.embed(
        [query["input"]], model="voyage-3", input_type="query"
    ).embeddings[0]

    neighbors = run_vector_search(db, query_emb)
    neighbor_text = format_neighbors_for_prompt(neighbors)

    prompt = (
        f"New fragment: \"{query['input']}\"\n\n"
        f"Vector search neighbors:\n{neighbor_text}\n"
        f"Classify the relationship of each neighbor to the new fragment."
    )

    model = os.environ.get("TEST_GEMINI_MODEL", "gemini-3.1-flash-lite")
    resp = gemini.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=MEMORY_INSTRUCTION,
            temperature=0.2,
        ),
    )

    raw = resp.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print("FAIL: Invalid JSON")
        print(f"Raw: {raw[:300]}")
        return False

    matches = result.get("matches", [])
    action = result.get("suggested_action", "")
    best = result.get("best_match_id")

    print(f"\nResults ({len(matches)} neighbors classified):")
    for m in matches:
        print(f"  {m['relationship']:25s} conf={m['confidence']:6s} "
              f"sim={m['similarity']:.3f} | {m['reasoning'][:60]}")

    print(f"\nsuggested_action: {action}")
    print(f"best_match_id: {best}")

    passed = True

    if not matches:
        print("FAIL: No matches returned")
        passed = False

    if action not in ("join_project", "bridge_projects", "new_project",
                      "needs_user_confirmation"):
        print(f"FAIL: Invalid suggested_action: {action}")
        passed = False

    if action in query["expect_action"]:
        print(f"OK: suggested_action '{action}' is expected")
    else:
        print(f"WARN: suggested_action '{action}' not in expected {query['expect_action']}")

    for m in matches:
        if m["relationship"] not in ("same_song_candidate", "related_theme",
                                     "similar_emotion", "unrelated"):
            print(f"FAIL: Invalid relationship: {m['relationship']}")
            passed = False

    return passed


def main():
    gemini = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    mongo = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = mongo["pocketproducer"]
    vc = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    count = db.fragments.count_documents({"user_id": "test_memory"})
    print(f"Seed fragments: {count}")
    if count == 0:
        print("ERROR: No seed data. Run test_e2e_pipeline.py first.")
        sys.exit(1)

    results = []
    for i, q in enumerate(QUERIES):
        try:
            passed = test_classification(gemini, db, vc, q, i)
            results.append(passed)
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {str(e)[:100]}")
            results.append(False)

    print(f"\n{'='*60}")
    print(f"Results: {sum(results)}/{len(results)} passed")
    if all(results):
        print("VERDICT: Memory classification PASSED")
    mongo.close()


if __name__ == "__main__":
    main()
