"""Seed MongoDB with real audio metadata from the Free Music Archive (FMA) dataset.

Uses track titles, genres, and Echonest/Spotify audio features (BPM, energy,
danceability, etc.) to create audio-type fragment entries. No actual MP3 files
are downloaded — only the 342 MB metadata zip is needed.

Data source: https://github.com/mdeff/fma
Download: https://os.unil.cloud.switch.ch/fma/fma_metadata.zip

Setup:
  cd /tmp
  curl -LO https://os.unil.cloud.switch.ch/fma/fma_metadata.zip
  unzip fma_metadata.zip -d fma_metadata

Run: .venv/bin/python tests/seed_fma_audio.py [--limit 100] [--dry-run]
"""

import argparse
import csv
import os
import pathlib
import random
import re
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import pymongo
import voyageai

FMA_DIR = pathlib.Path("/tmp/fma_metadata/fma_metadata")
USER_ID = "real_audio"

GENRE_THEME_MAP = {
    "Blues": ["heartbreak", "loss-grief"],
    "Country": ["hometown", "love", "home"],
    "Electronic": ["celebration", "freedom"],
    "Experimental": ["introspection", "self-identity"],
    "Folk": ["nature", "hometown", "memory"],
    "Hip-Hop": ["self-identity", "rebellion", "social-commentary"],
    "Instrumental": ["introspection"],
    "International": ["spirituality", "nature"],
    "Jazz": ["love", "introspection", "freedom"],
    "Old-Time / Historic": ["memory", "time"],
    "Pop": ["love", "celebration", "youth"],
    "Rock": ["rebellion", "freedom", "growth"],
    "Soul-RnB": ["love", "heartbreak", "self-identity"],
    "Spoken": ["social-commentary", "introspection"],
    "Classical": ["introspection", "nature", "spirituality"],
    "Easy Listening": ["love", "celebration"],
}

GENRE_STYLE_MAP = {
    "Blues": ["blues"],
    "Country": ["country"],
    "Electronic": ["electronic"],
    "Folk": ["folk"],
    "Hip-Hop": ["hip-hop"],
    "Jazz": ["jazz"],
    "Pop": ["pop"],
    "Rock": ["rock"],
    "Soul-RnB": ["r-and-b", "soul"],
    "Classical": ["classical"],
    "Instrumental": ["classical"],
}

KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def load_tracks_csv() -> dict[int, dict]:
    """Load tracks.csv with multi-level header. Returns {track_id: metadata}."""
    tracks_path = FMA_DIR / "tracks.csv"
    if not tracks_path.exists():
        print(f"ERROR: {tracks_path} not found")
        sys.exit(1)

    tracks = {}
    with open(tracks_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header0 = next(reader)
        header1 = next(reader)

        col_map = {}
        current_group = ""
        for i, (h0, h1) in enumerate(zip(header0, header1)):
            if h0:
                current_group = h0
            col_map[i] = (current_group, h1)

        title_col = genre_col = subset_col = artist_col = None
        for i, (g, c) in col_map.items():
            if g == "track" and c == "title":
                title_col = i
            elif g == "track" and c == "genre_top":
                genre_col = i
            elif g == "set" and c == "subset":
                subset_col = i
            elif g == "artist" and c == "name":
                artist_col = i

        for row in reader:
            if len(row) <= max(filter(None, [title_col, genre_col, subset_col, artist_col])):
                continue
            try:
                track_id = int(row[0])
            except (ValueError, IndexError):
                continue

            subset = row[subset_col] if subset_col else ""
            if subset != "small":
                continue

            title = row[title_col] if title_col else ""
            genre = row[genre_col] if genre_col else ""
            artist = row[artist_col] if artist_col else ""

            if title and genre:
                tracks[track_id] = {
                    "title": title,
                    "genre": genre,
                    "artist": artist,
                }

    print(f"Loaded {len(tracks)} small-subset tracks with genre")
    return tracks


def load_echonest_csv() -> dict[int, dict]:
    """Load echonest.csv for audio features."""
    echo_path = FMA_DIR / "echonest.csv"
    if not echo_path.exists():
        print(f"WARNING: {echo_path} not found, skipping audio features")
        return {}

    features = {}
    with open(echo_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header0 = next(reader)
        header1 = next(reader)
        header2 = next(reader)

        col_map = {}
        current_g0, current_g1 = "", ""
        for i, (h0, h1, h2) in enumerate(zip(header0, header1, header2)):
            if h0:
                current_g0 = h0
            if h1:
                current_g1 = h1
            col_map[i] = (current_g0, current_g1, h2)

        feature_cols = {}
        for i, (g0, g1, g2) in col_map.items():
            if g1 == "audio_features" or g1 == "temporal_features":
                feature_cols[g2] = i

        for row in reader:
            try:
                track_id = int(row[0])
            except (ValueError, IndexError):
                continue

            feat = {}
            for name, idx in feature_cols.items():
                try:
                    feat[name] = float(row[idx])
                except (ValueError, IndexError):
                    pass

            if feat:
                features[track_id] = feat

    print(f"Loaded echonest features for {len(features)} tracks")
    return features


def build_fragments(tracks: dict, echonest: dict, limit: int | None = None) -> list[dict]:
    """Build fragment documents from FMA metadata."""
    random.seed(42)

    track_ids = sorted(tracks.keys())
    random.shuffle(track_ids)

    if limit:
        track_ids = track_ids[:limit]

    fragments = []
    for tid in track_ids:
        meta = tracks[tid]
        echo = echonest.get(tid, {})

        title = meta["title"]
        artist = meta["artist"]
        genre = meta["genre"]

        raw_input = f"{title}"
        if artist:
            raw_input += f" by {artist}"
        raw_input += f" [{genre}]"

        audio_features = {}
        if "tempo" in echo:
            audio_features["bpm"] = round(echo["tempo"], 1)
        if "key" in echo:
            key_idx = int(echo["key"]) % 12
            audio_features["estimated_key"] = KEY_NAMES[key_idx]
        if "energy" in echo:
            audio_features["energy"] = round(echo["energy"], 3)
        if "danceability" in echo:
            audio_features["danceability"] = round(echo["danceability"], 3)
        if "acousticness" in echo:
            audio_features["acousticness"] = round(echo["acousticness"], 3)
        if "instrumentalness" in echo:
            audio_features["instrumentalness"] = round(echo["instrumentalness"], 3)
        if "valence" in echo:
            audio_features["valence"] = round(echo["valence"], 3)

        themes = GENRE_THEME_MAP.get(genre, [])
        styles = GENRE_STYLE_MAP.get(genre, [])

        is_instrumental = echo.get("instrumentalness", 0) > 0.5
        structure_hint = "melodic_motif" if is_instrumental else "lyric_fragment"

        artist_slug = re.sub(r"[^a-z0-9]+", "_", artist.lower()).strip("_") if artist else "unknown"
        project_id = f"proj_fma_{artist_slug}_{tid}"

        fragment = {
            "user_id": USER_ID,
            "raw_input": raw_input,
            "input_type": "audio",
            "source": {
                "dataset": "FMA",
                "track_id": tid,
                "title": title,
                "artist": artist,
                "genre": genre,
            },
            "tags": {
                "emotion": [],
                "theme": themes[:2],
                "structure_hint": structure_hint,
                "style": styles[:2],
                "potential": "medium",
                "needs_user_input": False,
                "user_prompt": None,
            },
            "audio_features": audio_features or None,
            "project_id": project_id,
            "created_at": datetime.now(UTC),
            "status": "seeded",
        }
        fragments.append(fragment)

    print(f"Built {len(fragments)} audio fragments")
    return fragments


def embed_fragments(fragments: list[dict], batch_size: int = 3, delay: float = 22.0):
    """Generate Voyage AI embeddings."""
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

    genres = {}
    for f in fragments:
        g = f["source"]["genre"]
        genres[g] = genres.get(g, 0) + 1
    print("\nGenre distribution:")
    for g, c in sorted(genres.items(), key=lambda x: -x[1]):
        print(f"  {g}: {c}")

    mongo.close()


def main():
    parser = argparse.ArgumentParser(description="Seed FMA audio metadata into MongoDB")
    parser.add_argument("--limit", type=int, default=100, help="Max fragments to seed (default 100)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and show stats without embedding/inserting")
    parser.add_argument("--batch-size", type=int, default=3, help="Voyage AI batch size (default 3)")
    parser.add_argument("--delay", type=float, default=22.0, help="Delay between batches in seconds (default 22)")
    args = parser.parse_args()

    if not FMA_DIR.exists():
        print(f"ERROR: {FMA_DIR} not found.")
        print("Download first:")
        print("  cd /tmp")
        print("  curl -LO https://os.unil.cloud.switch.ch/fma/fma_metadata.zip")
        print("  unzip fma_metadata.zip -d fma_metadata")
        sys.exit(1)

    tracks = load_tracks_csv()
    echonest = load_echonest_csv()

    fragments = build_fragments(tracks, echonest, limit=args.limit)

    if not fragments:
        print("ERROR: No fragments built.")
        sys.exit(1)

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Would seed {len(fragments)} audio fragments")

        genres = {}
        for f in fragments:
            g = f["source"]["genre"]
            genres[g] = genres.get(g, 0) + 1
        print("Genre distribution:")
        for g, c in sorted(genres.items(), key=lambda x: -x[1]):
            print(f"  {g}: {c}")

        with_features = sum(1 for f in fragments if f.get("audio_features"))
        print(f"With echonest features: {with_features}/{len(fragments)}")

        print("\nSample fragment:")
        sample = fragments[0]
        print(f"  Title: {sample['source']['title']}")
        print(f"  Artist: {sample['source']['artist']}")
        print(f"  Genre: {sample['source']['genre']}")
        print(f"  Audio features: {sample.get('audio_features')}")
        print(f"  Structure: {sample['tags']['structure_hint']}")
        print(f"  Themes: {sample['tags']['theme']}")
        return

    embed_fragments(fragments, batch_size=args.batch_size, delay=args.delay)
    insert_to_mongodb(fragments)
    print("\nDone!")


if __name__ == "__main__":
    main()
