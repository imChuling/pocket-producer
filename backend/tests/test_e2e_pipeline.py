"""End-to-end pipeline test: text → tag → embed → MongoDB write → read back.

Uses direct API calls (not ADK Runner) to avoid free-tier quota issues.
Uses mock embedding when VOYAGE_API_KEY is not set.

Run: .venv/bin/python tests/test_e2e_pipeline.py
"""

import json
import os
import pathlib
import random
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import google.genai as genai  # noqa: E402
import pymongo  # noqa: E402

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

TEST_INPUT = (
    "The streetlights flicker like old memories, "
    "and I swear I can hear your voice in the wind"
)


def step_tag(client: genai.Client, text: str) -> dict:
    print("\n[Step 1] Catcher: tagging fragment...")
    resp = client.models.generate_content(
        model=os.environ.get("TEST_GEMINI_MODEL", "gemini-2.5-flash"),
        contents=f"Tag this fragment: {text}",
        config=genai.types.GenerateContentConfig(
            system_instruction=TAGGING_INSTRUCTION,
            temperature=0.3,
        ),
    )
    raw = resp.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    tags = json.loads(raw)
    print(f"  Emotions:  {tags['tags']['emotion']}")
    print(f"  Themes:    {tags['tags']['theme']}")
    print(f"  Structure: {tags['tags']['structure_hint']}")
    print(f"  Style:     {tags['tags']['style']}")
    print(f"  Potential: {tags['tags']['potential']}")
    print(f"  Reasoning: {tags['reasoning'][:100]}...")
    return tags


def step_embed(text: str) -> list[float]:
    print("\n[Step 2] Embedding: generating vector...")
    voyage_key = os.environ.get("VOYAGE_API_KEY", "")
    if voyage_key and voyage_key != "<voyage-key>":
        import voyageai

        vc = voyageai.Client(api_key=voyage_key)
        result = vc.embed([text], model="voyage-3", input_type="document")
        embedding = result.embeddings[0]
        print(f"  Voyage AI embedding: {len(embedding)} dims (real)")
    else:
        random.seed(hash(text) % (2**32))
        embedding = [random.gauss(0, 0.1) for _ in range(1024)]
        print(f"  Mock embedding: {len(embedding)} dims (VOYAGE_API_KEY not set)")
    return embedding


def step_write(mongo_client: pymongo.MongoClient, doc: dict) -> str:
    print("\n[Step 3] MongoDB: writing fragment...")
    db = mongo_client["pocketproducer"]
    result = db.fragments.insert_one(doc)
    oid = str(result.inserted_id)
    print(f"  Inserted: {oid}")
    return oid


def step_read(mongo_client: pymongo.MongoClient, oid: str) -> dict:
    print("\n[Step 4] MongoDB: reading back fragment...")
    from bson import ObjectId

    db = mongo_client["pocketproducer"]
    doc = db.fragments.find_one({"_id": ObjectId(oid)})
    if not doc:
        raise ValueError(f"Document {oid} not found")
    print(f"  Found: {doc['raw_input'][:60]}...")
    print(f"  Tags:  {list(doc['tags'].keys())}")
    print(f"  Embedding dims: {len(doc['embedding'])}")
    return doc


def step_cleanup(mongo_client: pymongo.MongoClient, oid: str):
    print("\n[Cleanup] Removing test document...")
    from bson import ObjectId

    db = mongo_client["pocketproducer"]
    db.fragments.delete_one({"_id": ObjectId(oid)})
    print("  Deleted.")


def main():
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    mongo_uri = os.environ.get("MONGODB_CONNECTION_STRING", "")

    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set")
        sys.exit(1)
    if not mongo_uri:
        print("ERROR: MONGODB_CONNECTION_STRING not set")
        sys.exit(1)

    gemini = genai.Client(api_key=api_key)
    mongo = pymongo.MongoClient(mongo_uri)

    print("=" * 60)
    print("End-to-End Pipeline Test")
    print(f"Input: \"{TEST_INPUT[:60]}...\"")
    print("=" * 60)

    try:
        tags_result = step_tag(gemini, TEST_INPUT)
    except Exception as e:
        print(f"FAIL at Step 1 (tagging): {e}")
        sys.exit(1)

    embedding = step_embed(TEST_INPUT)

    fragment_doc = {
        "user_id": "e2e_test_user",
        "raw_input": TEST_INPUT,
        "input_type": "text",
        "tags": tags_result["tags"],
        "reasoning": tags_result["reasoning"],
        "embedding": embedding,
        "created_at": datetime.now(UTC),
        "status": "tagged",
    }

    try:
        oid = step_write(mongo, fragment_doc)
    except Exception as e:
        print(f"FAIL at Step 3 (write): {e}")
        sys.exit(1)

    try:
        readback = step_read(mongo, oid)
    except Exception as e:
        print(f"FAIL at Step 4 (read): {e}")
        sys.exit(1)

    print("\n[Verification]")
    ok = True
    if readback["raw_input"] != TEST_INPUT:
        print("  FAIL: raw_input mismatch")
        ok = False
    else:
        print("  OK: raw_input matches")

    if readback["tags"]["emotion"] != tags_result["tags"]["emotion"]:
        print("  FAIL: tags.emotion mismatch")
        ok = False
    else:
        print(f"  OK: tags.emotion = {readback['tags']['emotion']}")

    if len(readback["embedding"]) != 1024:
        print(f"  FAIL: embedding has {len(readback['embedding'])} dims, expected 1024")
        ok = False
    else:
        print("  OK: embedding = 1024 dims")

    if readback["status"] != "tagged":
        print("  FAIL: status mismatch")
        ok = False
    else:
        print("  OK: status = tagged")

    step_cleanup(mongo, oid)

    mongo.close()

    print("\n" + "=" * 60)
    if ok:
        print("VERDICT: End-to-end pipeline PASSED")
    else:
        print("VERDICT: End-to-end pipeline FAILED")
    print("=" * 60)


if __name__ == "__main__":
    main()
