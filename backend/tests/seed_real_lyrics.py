"""Seed MongoDB with real lyric fragments from the LabROSA lyric_database.

Parses 249 songs with [VERSE]/[CHORUS]/[BRIDGE] structure annotations,
extracts individual sections as fragments, embeds via Voyage AI,
and inserts into MongoDB Atlas.

Data source: https://github.com/mattmcvicar/lyric_database
Clone to /tmp first: git clone --depth 1 https://github.com/mattmcvicar/lyric_database.git /tmp/lyric_database

Run: .venv/bin/python tests/seed_real_lyrics.py [--limit 200] [--dry-run]
"""

import argparse
import os
import pathlib
import re
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import pymongo
import voyageai

LYRICS_DIR = pathlib.Path("/tmp/lyric_database/lyrics")
USER_ID = "real_lyrics"

STRUCTURE_MAP = {
    "VERSE": "verse_candidate",
    "CHORUS": "chorus_candidate",
    "CHOURUS": "chorus_candidate",
    "CHOURS": "chorus_candidate",
    "CHORYS": "chorus_candidate",
    "INTERLUDE": "bridge_candidate",
    "INTRO": "hook_candidate",
    "OUTRO": "lyric_fragment",
}

SECTION_TAG_RE = re.compile(r"^\[([A-Za-z\s\d]+)\]\s*$")


def parse_lyrics_file(path: pathlib.Path) -> list[dict]:
    """Parse a .lyrics file into structural sections."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []

    filename = path.stem
    parts = filename.split("_-_", 1)
    artist = parts[0].replace("_", " ").strip() if len(parts) == 2 else "Unknown"
    song = parts[1].replace("_", " ").strip() if len(parts) == 2 else filename.replace("_", " ")

    sections = []
    current_tag = None
    current_lines = []

    for line in text.split("\n"):
        m = SECTION_TAG_RE.match(line.strip())
        if m:
            if current_tag and current_lines:
                content = "\n".join(current_lines).strip()
                if len(content) >= 20:
                    sections.append({
                        "tag": current_tag,
                        "text": content,
                        "artist": artist,
                        "song": song,
                    })
            raw_tag = m.group(1).strip().upper()
            raw_tag = re.sub(r"\s*\d+$", "", raw_tag)
            current_tag = raw_tag
            current_lines = []
        else:
            stripped = line.strip()
            if stripped:
                current_lines.append(stripped)

    if current_tag and current_lines:
        content = "\n".join(current_lines).strip()
        if len(content) >= 20:
            sections.append({
                "tag": current_tag,
                "text": content,
                "artist": artist,
                "song": song,
            })

    return sections


def sections_to_fragments(sections: list[dict]) -> list[dict]:
    """Convert parsed sections to fragment documents."""
    fragments = []
    song_slug = re.sub(r"[^a-z0-9]+", "_", sections[0]["song"].lower()).strip("_") if sections else ""
    artist_slug = re.sub(r"[^a-z0-9]+", "_", sections[0]["artist"].lower()).strip("_") if sections else ""
    project_id = f"proj_{artist_slug}_{song_slug}"

    for i, sec in enumerate(sections):
        structure_hint = STRUCTURE_MAP.get(sec["tag"], "lyric_fragment")

        fragments.append({
            "user_id": USER_ID,
            "raw_input": sec["text"],
            "input_type": "text",
            "source": {
                "dataset": "LabROSA",
                "artist": sec["artist"],
                "song": sec["song"],
                "section_index": i,
                "section_type": sec["tag"],
            },
            "tags": {
                "emotion": [],
                "theme": [],
                "structure_hint": structure_hint,
                "style": [],
                "potential": "medium",
                "needs_user_input": False,
                "user_prompt": None,
            },
            "project_id": project_id,
            "created_at": datetime.now(UTC),
            "status": "seeded",
        })

    return fragments


def collect_all_fragments(limit: int | None = None) -> list[dict]:
    """Walk the lyrics directory and collect fragments."""
    all_fragments = []
    lyric_files = sorted(LYRICS_DIR.rglob("*.lyrics"))

    print(f"Found {len(lyric_files)} lyric files")

    for path in lyric_files:
        sections = parse_lyrics_file(path)
        if sections:
            frags = sections_to_fragments(sections)
            all_fragments.extend(frags)

    print(f"Extracted {len(all_fragments)} fragments from {len(lyric_files)} songs")

    if limit and len(all_fragments) > limit:
        import random
        random.seed(42)

        by_project: dict[str, list[dict]] = {}
        for f in all_fragments:
            by_project.setdefault(f["project_id"], []).append(f)

        selected = []
        projects = list(by_project.keys())
        random.shuffle(projects)
        for proj in projects:
            frags = by_project[proj]
            selected.extend(frags)
            if len(selected) >= limit:
                break

        all_fragments = selected[:limit]
        print(f"Limited to {len(all_fragments)} fragments from {len(set(f['project_id'] for f in all_fragments))} projects")

    return all_fragments


def embed_fragments(fragments: list[dict], batch_size: int = 3, delay: float = 22.0):
    """Generate Voyage AI embeddings for all fragments."""
    vc = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    texts = [f["raw_input"] for f in fragments]
    total = len(texts)

    print(f"\nEmbedding {total} fragments (batch_size={batch_size}, delay={delay}s)...")
    estimated_minutes = (total / batch_size) * delay / 60
    print(f"Estimated time: {estimated_minutes:.0f} minutes")

    all_embeddings = []
    for i in range(0, total, batch_size):
        if i > 0:
            time.sleep(delay)

        batch = texts[i : i + batch_size]
        for attempt in range(3):
            try:
                result = vc.embed(batch, model="voyage-3", input_type="document")
                all_embeddings.extend(result.embeddings)
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  Rate limited at {i}/{total}, waiting 30s... ({e})")
                    time.sleep(30)
                else:
                    raise

        done = min(i + batch_size, total)
        if done % 30 == 0 or done == total:
            print(f"  {done}/{total} embedded")

    for idx, emb in enumerate(all_embeddings):
        fragments[idx]["embedding"] = emb

    print(f"Embedding complete: {len(all_embeddings)} vectors")


def insert_to_mongodb(fragments: list[dict]):
    """Insert fragments into MongoDB."""
    mongo = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = mongo["pocketproducer"]

    existing = db.fragments.count_documents({"user_id": USER_ID})
    if existing > 0:
        print(f"\nWARNING: {existing} fragments with user_id='{USER_ID}' already exist.")
        resp = input("Delete existing and re-seed? [y/N] ")
        if resp.lower() != "y":
            print("Aborted.")
            mongo.close()
            return
        db.fragments.delete_many({"user_id": USER_ID})
        print(f"Deleted {existing} existing fragments.")

    result = db.fragments.insert_many(fragments)
    print(f"Inserted {len(result.inserted_ids)} fragments into MongoDB")

    projects = set(f["project_id"] for f in fragments)
    structures = {}
    for f in fragments:
        s = f["tags"]["structure_hint"]
        structures[s] = structures.get(s, 0) + 1

    print("\nSummary:")
    print(f"  Projects: {len(projects)}")
    print(f"  Fragments: {len(fragments)}")
    print(f"  Structure distribution: {structures}")

    mongo.close()


def main():
    parser = argparse.ArgumentParser(description="Seed real lyrics into MongoDB")
    parser.add_argument("--limit", type=int, default=200, help="Max fragments to seed (default 200)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and show stats without embedding/inserting")
    parser.add_argument("--batch-size", type=int, default=3, help="Voyage AI batch size (default 3)")
    parser.add_argument("--delay", type=float, default=22.0, help="Delay between batches in seconds (default 22)")
    args = parser.parse_args()

    if not LYRICS_DIR.exists():
        print(f"ERROR: {LYRICS_DIR} not found.")
        print("Clone first: git clone --depth 1 https://github.com/mattmcvicar/lyric_database.git /tmp/lyric_database")
        sys.exit(1)

    fragments = collect_all_fragments(limit=args.limit)

    if not fragments:
        print("ERROR: No fragments extracted.")
        sys.exit(1)

    if args.dry_run:
        print("\n--- DRY RUN ---")
        projects = set(f["project_id"] for f in fragments)
        print(f"Would seed {len(fragments)} fragments from {len(projects)} projects")
        for proj in sorted(projects)[:10]:
            count = sum(1 for f in fragments if f["project_id"] == proj)
            sample = next(f for f in fragments if f["project_id"] == proj)
            print(f"  {proj}: {count} fragments ({sample['source']['artist']} - {sample['source']['song']})")
        if len(projects) > 10:
            print(f"  ... and {len(projects) - 10} more projects")

        structures = {}
        for f in fragments:
            s = f["tags"]["structure_hint"]
            structures[s] = structures.get(s, 0) + 1
        print(f"\nStructure distribution: {structures}")
        print("\nSample fragment:")
        sample = fragments[0]
        print(f"  Artist: {sample['source']['artist']}")
        print(f"  Song: {sample['source']['song']}")
        print(f"  Structure: {sample['tags']['structure_hint']}")
        print(f"  Text: {sample['raw_input'][:120]}...")
        return

    embed_fragments(fragments, batch_size=args.batch_size, delay=args.delay)
    insert_to_mongodb(fragments)
    print("\nDone!")


if __name__ == "__main__":
    main()
