"""Test Producer Agent's decision logic with real data.

Simulates the 3-agent pipeline:
  1. Catcher tags a new fragment (Gemini)
  2. Memory classifies neighbors (vector search + Gemini)
  3. Producer decides action + computes Rescue Score (pure Python)

Uses direct API calls to conserve free-tier quota.

Run: .venv/bin/python tests/test_producer_decision.py
"""

import json
import os
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import google.genai as genai  # noqa: E402
import pymongo  # noqa: E402
import voyageai  # noqa: E402

from tools.rescue_score import compute_rescue_score  # noqa: E402


def _gemini_call(gemini, model, contents, system_instruction, temperature=0.2, retries=3):
    """Call Gemini with retry on 500/503."""
    import time as _time

    for attempt in range(retries):
        try:
            resp = gemini.models.generate_content(
                model=model,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                ),
            )
            raw = resp.text.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            return json.loads(raw)
        except (json.JSONDecodeError,):
            if attempt < retries - 1:
                _time.sleep(3)
                continue
            raise
        except Exception as e:
            err = str(e)
            if ("500" in err or "503" in err) and attempt < retries - 1:
                _time.sleep(5 * (attempt + 1))
                continue
            raise


TAGGING_INSTRUCTION = """\
You are the Catcher Agent (Perception layer) of Pocket Producer.

## Emotion Taxonomy
Primary: joy, sadness, anger, fear, surprise, disgust, trust, anticipation
Musical: melancholy, euphoria, tension, nostalgia, tenderness, defiance,
  longing, serenity, vulnerability, excitement, acceptance, freedom, loss, anxiety

## Theme Taxonomy
love, heartbreak, self-identity, mental-health, hometown, celebration,
freedom, rebellion, growth, loss-grief, friendship, nature, time, memory,
spirituality, social-commentary, isolation, youth, home, introspection

## Structure Hints
verse_candidate, chorus_candidate, bridge_candidate, hook_candidate,
melodic_motif, lyric_fragment, near_complete_demo

## Style Vocabulary
pop, rock, hip-hop, r-and-b, country, electronic, jazz, classical, folk,
indie, alternative, latin, afrobeats, k-pop, metal, punk, blues, soul, reggae, funk

Output ONLY valid JSON:
{
  "tags": {
    "emotion": ["string"],
    "theme": ["string"],
    "structure_hint": "string | null",
    "style": ["string"],
    "potential": "high | medium | low",
    "needs_user_input": false,
    "user_prompt": null
  },
  "reasoning": "string"
}
"""

MEMORY_INSTRUCTION = """\
You are the Memory Agent (Grounding layer) of Pocket Producer.

You are given a new fragment and its vector search neighbors.
Classify the relationship between the new fragment and each neighbor.

## Relationship Types
- same_song_candidate: fragments likely belong to the same song/project
- related_theme: share thematic elements but probably different songs
- similar_emotion: share emotional tone but different content
- unrelated: no meaningful connection

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

Output ONLY valid JSON:
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

PRODUCER_INSTRUCTION = """\
You are the Producer Agent (Action layer) of Pocket Producer.

Given:
1. A new fragment's tags (from Catcher)
2. Memory's classification of neighbors and suggested_action
3. The Rescue Score of the affected project (pre-computed)

Decide the final action and generate a user-facing response.

Output ONLY valid JSON:
{
  "decision": "join | new | bridge | ask_user",
  "project_id": "string | null",
  "reasoning": "string (1-2 sentences for the user)",
  "next_action": "string (specific, doable in 30 min)",
  "rescue_score": null
}

Rules:
- join: Memory found same_song_candidate with high confidence
- new: No matching project found
- bridge: Two related projects found — highlight this to the user
- ask_user: Memory unsure, surface options

next_action must be concrete and achievable in 30 minutes. Examples:
- "Try humming a chorus melody that matches this verse's mood"
- "Record a second verse exploring the same theme from a different angle"
- "This has verse + chorus — try a bridge section to contrast the emotions"
"""


GEMINI_MODEL = os.environ.get("TEST_GEMINI_MODEL", "gemini-3.1-flash-lite")


def step_catcher(gemini, text):
    """Tag the fragment using Gemini."""
    return _gemini_call(
        gemini,
        GEMINI_MODEL,
        f'Tag this fragment:\n"{text}"',
        TAGGING_INSTRUCTION,
    )


def step_memory(gemini, db, vc, text, tags):
    """Run vector search and classify neighbors."""
    query_emb = vc.embed([text], model="voyage-3", input_type="query").embeddings[0]

    neighbors = list(
        db.fragments.aggregate(
            [
                {
                    "$vectorSearch": {
                        "index": "fragment_vector_index",
                        "path": "embedding",
                        "queryVector": query_emb,
                        "numCandidates": 20,
                        "limit": 5,
                        "filter": {"user_id": "test_memory"},
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
            ]
        )
    )

    neighbor_lines = []
    for n in neighbors:
        neighbor_lines.append(f"- fragment_id: {n['_id']}")
        neighbor_lines.append(f"  similarity: {n['score']:.4f}")
        neighbor_lines.append(f"  raw_input: {n['raw_input']}")
        neighbor_lines.append(f"  emotions: {n['tags'].get('emotion', [])}")
        neighbor_lines.append(f"  themes: {n['tags'].get('theme', [])}")
        neighbor_lines.append(f"  structure: {n['tags'].get('structure_hint')}")
        af = n.get("audio_features") or {}
        neighbor_lines.append(f"  bpm: {af.get('bpm', 'n/a')}  key: {af.get('key', 'n/a')}")
        neighbor_lines.append(f"  created_at: {n.get('created_at', 'unknown')}")
        neighbor_lines.append(f"  project_id: {n.get('project_id', 'none')}")
        neighbor_lines.append("")

    prompt = (
        f'New fragment: "{text}"\n'
        f"New fragment tags: {json.dumps(tags['tags'])}\n\n"
        f"Vector search neighbors:\n{''.join(neighbor_lines)}\n"
        f"Classify relationships."
    )

    result = _gemini_call(gemini, GEMINI_MODEL, prompt, MEMORY_INSTRUCTION)
    return result, neighbors


def step_producer(gemini, text, tags, memory_result, rescue):
    """Producer decides action."""
    prompt = (
        f'New fragment: "{text}"\n'
        f"Catcher tags: {json.dumps(tags['tags'])}\n\n"
        f"Memory result:\n{json.dumps(memory_result, indent=2, default=str)}\n\n"
        f"Rescue Score: {json.dumps(rescue, default=str)}\n\n"
        f"Decide the action."
    )

    return _gemini_call(gemini, GEMINI_MODEL, prompt, PRODUCER_INSTRUCTION)


TEST_CASES = [
    {
        "input": "The rain keeps falling and I keep walking, nowhere to go, nowhere to be",
        "description": "Should relate to existing rain/walking seeds → join or ask_user",
        "expect_decision": ["join", "ask_user"],
    },
    {
        "input": "Turn up the bass, feel the floor vibrate, hands in the air tonight",
        "description": "Party/bass theme — should be new project or unrelated to rain seeds",
        "expect_decision": ["new"],
    },
    {
        "input": "Puddles on the sidewalk reflect the neon signs, I pull my hood up tight",
        "description": "Rain + urban imagery — could bridge or join existing rain project",
        "expect_decision": ["join", "bridge", "ask_user"],
    },
]


def run_test(gemini, db, vc, case, index):
    print(f"\n{'=' * 60}")
    print(f"Test {index + 1}: {case['input'][:55]}...")
    print(f"Expect: {case['description']}")
    print(f"{'=' * 60}")

    print("\n--- Catcher ---")
    tags = step_catcher(gemini, case["input"])
    print(f"  emotions: {tags['tags']['emotion']}")
    print(f"  themes: {tags['tags']['theme']}")
    print(f"  structure: {tags['tags']['structure_hint']}")

    print("\n--- Memory ---")
    memory_result, neighbors = step_memory(gemini, db, vc, case["input"], tags)
    action = memory_result.get("suggested_action", "unknown")
    print(f"  suggested_action: {action}")
    for m in memory_result.get("matches", [])[:3]:
        print(f"  {m['relationship']:25s} sim={m['similarity']:.3f} {m['reasoning'][:50]}")

    print("\n--- Rescue Score ---")
    rescue = compute_rescue_score(neighbors, "test_project", now=datetime.now(UTC))
    print(f"  score: {rescue['rescue_score']}, tier: {rescue['tier']}")
    if rescue["components"]:
        print(f"  components: {rescue['components']}")

    print("\n--- Producer ---")
    producer_result = step_producer(gemini, case["input"], tags, memory_result, rescue)
    decision = producer_result.get("decision", "unknown")
    print(f"  decision: {decision}")
    print(f"  reasoning: {producer_result.get('reasoning', 'n/a')}")
    print(f"  next_action: {producer_result.get('next_action', 'n/a')}")

    passed = True

    if decision not in ("join", "new", "bridge", "ask_user"):
        print(f"FAIL: invalid decision '{decision}'")
        passed = False

    if decision in case["expect_decision"]:
        print(f"OK: decision '{decision}' matches expected {case['expect_decision']}")
    else:
        print(f"WARN: decision '{decision}' not in expected {case['expect_decision']}")

    if not producer_result.get("next_action"):
        print("FAIL: missing next_action")
        passed = False
    else:
        print("OK: next_action present")

    if not producer_result.get("reasoning"):
        print("FAIL: missing reasoning")
        passed = False
    else:
        print("OK: reasoning present")

    return passed


def main():
    gemini = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    mongo = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = mongo["pocketproducer"]
    vc = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    count = db.fragments.count_documents({"user_id": "test_memory"})
    print(f"Seed fragments in DB: {count}")
    if count == 0:
        print("ERROR: No seed data. Run test_e2e_pipeline.py first.")
        sys.exit(1)

    import time

    results = []
    for i, case in enumerate(TEST_CASES):
        if i > 0:
            time.sleep(5)
        try:
            passed = run_test(gemini, db, vc, case, i)
            results.append(passed)
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {str(e)[:200]}")
            results.append(False)

    print(f"\n{'=' * 60}")
    print(f"Results: {sum(results)}/{len(results)} passed")
    if all(results):
        print("VERDICT: Producer decision pipeline PASSED")
    else:
        print("VERDICT: Some tests had issues (check WARN vs FAIL above)")
    mongo.close()


if __name__ == "__main__":
    main()
