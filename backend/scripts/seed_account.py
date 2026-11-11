"""Seed a demo account with local audio files — no Cloud Run needed.

Processes audio locally (librosa features + CLAP embedding), uploads to
GCS, and inserts complete fragment documents into MongoDB. Skips Gemini
tagging entirely; tags/emotions/themes are provided via a companion JSON
or auto-generated from audio features.

Usage (from backend/):
  POCKET_ENABLE_CLAP=1 .venv/bin/python -m scripts.seed_account \
      --user-id <FIREBASE_UID> \
      --audio-dir /path/to/audio/files \
      [--lyrics-dir /path/to/lyrics] \
      [--meta seed_meta.json] \
      [--dry-run]
"""

import argparse
import json
import logging
import os
import pathlib
import sys
import uuid
from datetime import UTC, datetime

import librosa
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("seed")

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".webm", ".aac"}


def _load_env():
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def extract_features_local(path: str) -> dict:
    y, sr = librosa.load(path, sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo_raw, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.mean(tempo_raw))

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key_index = int(chroma.mean(axis=1).argmax())
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    chroma_mean = chroma.mean(axis=1)
    major_profile = np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1])
    minor_profile = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0])
    major_corr = float(np.corrcoef(np.roll(chroma_mean, -key_index), major_profile)[0, 1])
    minor_corr = float(np.corrcoef(np.roll(chroma_mean, -key_index), minor_profile)[0, 1])
    mode = "major" if major_corr > minor_corr else "minor"

    rms = librosa.feature.rms(y=y)[0]
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spec_flat = librosa.feature.spectral_flatness(y=y)[0]

    key_str = f"{keys[key_index]}m" if mode == "minor" else keys[key_index]

    return {
        "bpm": round(tempo, 1),
        "key": key_str,
        "estimated_key": keys[key_index],
        "estimated_mode": mode,
        "duration_sec": round(duration, 2),
        "energy_mean": round(float(np.mean(rms)), 4),
        "brightness": round(float(np.mean(centroid)), 1),
        "onset_density": round(len(onsets) / max(duration, 0.1), 2),
        "spectral_flatness": round(float(np.mean(spec_flat)), 4),
    }


def encode_clap(path: str, adapter, sr=44100) -> dict:
    from ranking.adapters.base import encode_with_lineage

    y, _ = librosa.load(path, sr=sr, mono=True)
    waveform = y.astype(np.float32)
    record = encode_with_lineage(adapter, waveform, sr)
    return record.model_dump(), waveform, sr


def chroma_record_local(waveform, sample_rate: int, input_sha256: str) -> dict:
    from ranking.harmonic_probe import chroma_from_audio
    from ranking.ingest import CHROMA_REVISION

    return {
        "model_id": CHROMA_REVISION,
        "revision": CHROMA_REVISION,
        "input_sha256": input_sha256,
        "vector": chroma_from_audio(waveform, sample_rate),
    }


def auto_tags_from_features(features: dict, filename: str) -> dict:
    """Generate basic tags from audio features and filename."""
    tags = []
    emotions = []
    themes = []
    style = []

    bpm = features["bpm"]
    if bpm < 90:
        tags.append("slow")
        emotions.append("calm")
    elif bpm < 120:
        tags.append("mid-tempo")
    elif bpm < 140:
        tags.append("upbeat")
        emotions.append("energetic")
    else:
        tags.append("fast")
        emotions.append("intense")

    key = features.get("key", "")
    if "m" in key:
        emotions.append("melancholic")
        themes.append("introspection")
    else:
        emotions.append("bright")
        themes.append("optimism")

    brightness = features.get("brightness", 0)
    if brightness > 3000:
        tags.append("bright")
    elif brightness < 1500:
        tags.append("warm")
        tags.append("dark")

    fname = filename.lower()
    style_hints = {
        "funk": "funk", "indie": "indie", "chill": "lo-fi",
        "bounce": "bounce", "laid": "lo-fi", "choir": "vocal",
        "beat": "hip-hop", "trap": "trap", "motion": "electronic",
    }
    for hint, s in style_hints.items():
        if hint in fname:
            style.append(s)
            break

    if not style:
        if bpm > 130:
            style.append("electronic")
        elif features.get("spectral_flatness", 0) > 0.05:
            style.append("ambient")
        else:
            style.append("pop")

    return {
        "tags": tags[:5],
        "emotions": emotions[:3],
        "themes": themes[:2],
        "style": style[:2],
    }


def upload_to_gcs(local_path: str, user_id: str, bucket_name: str) -> str:
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    fname = pathlib.Path(local_path).name
    blob_name = f"{user_id}/{uuid.uuid4()}-{fname}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    return f"gs://{bucket_name}/{blob_name}"


def generate_text_embedding(text: str) -> list[float] | None:
    """Generate text embedding using Voyage if available."""
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        return None
    import requests

    resp = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": "voyage-3", "input": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a Pocket Producer demo account")
    parser.add_argument(
        "--user-id", default="demo-seed-user", help="virtual UID for seed account",
    )
    parser.add_argument("--audio-dir", required=True, help="directory with audio files")
    parser.add_argument("--lyrics-dir", help="directory with .txt lyrics (matched by stem)")
    parser.add_argument("--meta", help="JSON with per-file overrides {filename: {...}}")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env()

    audio_dir = pathlib.Path(args.audio_dir)
    files = sorted(
        f for f in audio_dir.iterdir()
        if f.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not files:
        logger.error("No audio files found in %s", audio_dir)
        return 1
    logger.info("Found %d audio files", len(files))

    lyrics_map = {}
    if args.lyrics_dir:
        for lf in pathlib.Path(args.lyrics_dir).glob("*.txt"):
            lyrics_map[lf.stem.lower()] = lf.read_text().strip()

    meta_map = {}
    if args.meta:
        meta_map = json.loads(pathlib.Path(args.meta).read_text())

    if args.dry_run:
        for f in files:
            stem = f.stem.lower()
            has_lyrics = stem in lyrics_map or any(stem.startswith(k) for k in lyrics_map)
            has_meta = f.name in meta_map
            logger.info("  %s  lyrics=%s  meta=%s", f.name, has_lyrics, has_meta)
        return 0

    from api.deps import get_db
    from ranking.adapters.base import audio_sha256

    db = get_db()

    adapter = None
    if os.environ.get("POCKET_ENABLE_CLAP") == "1":
        from ranking.adapters import shared
        adapter = shared.get_msclap()
        if adapter:
            logger.info("CLAP adapter loaded")
    if not adapter:
        logger.warning("CLAP disabled — fragments will have no audio_semantic embedding")

    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        logger.error("GCS_BUCKET not set")
        return 1

    existing_titles = {
        doc["title"]
        for doc in db["fragments"].find(
            {"user_id": args.user_id, "seed": True}, {"title": 1},
        )
    }

    counts = {"ok": 0, "skipped": 0, "failed": 0}
    for f in files:
        try:
            title = f.stem.replace("-", " ").replace("_", " ").strip()
            if title in existing_titles:
                logger.info("Skipping %s (already seeded)", f.name)
                counts["skipped"] += 1
                continue
            logger.info("Processing %s ...", f.name)

            # Audio features
            features = extract_features_local(str(f))
            logger.info(
                "  BPM=%.1f  key=%s  dur=%.1fs",
                features["bpm"], features["key"], features["duration_sec"],
            )

            # Lyrics
            stem = f.stem.lower()
            text = lyrics_map.get(stem)
            if not text:
                for k, v in lyrics_map.items():
                    if stem.startswith(k) or k.startswith(stem):
                        text = v
                        break

            # Tags
            file_meta = meta_map.get(f.name, {})
            if file_meta:
                tag_data = file_meta
            else:
                tag_data = auto_tags_from_features(features, f.name)

            # CLAP
            clap_record = None
            chroma_rec = None
            if adapter:
                from ranking.adapters import shared as shared_mod
                with shared_mod.infer_lock:
                    clap_dict, waveform_44k, sr_44k = encode_clap(str(f), adapter)
                input_hash = audio_sha256(waveform_44k, sr_44k)
                chroma_rec = chroma_record_local(waveform_44k, sr_44k, input_hash)
                logger.info("  CLAP dims=%d", len(clap_dict["vector"]))

            # Upload to GCS
            gcs_uri = upload_to_gcs(str(f), args.user_id, bucket_name)
            logger.info("  GCS: %s", gcs_uri)

            # Text embedding (best-effort, Voyage rate limits are tight)
            embedding = None
            embed_source = text or " ".join(
                tag_data.get("tags", []) + tag_data.get("emotions", []),
            )
            try:
                embedding = generate_text_embedding(embed_source)
            except Exception as emb_err:
                logger.warning("  Embedding skipped: %s", emb_err)

            # Build document
            now = datetime.now(UTC)
            doc = {
                "user_id": args.user_id,
                "type": "audio",
                "title": title,
                "text": text,
                "raw_text": text,
                "audio_url": gcs_uri,
                "tags": tag_data.get("tags", []),
                "emotions": tag_data.get("emotions", []),
                "themes": tag_data.get("themes", []),
                "style": tag_data.get("style", []),
                "key": features["key"],
                "bpm": features["bpm"],
                "audio_features": features,
                "status": "ready",
                "pipeline_step": "done",
                "created_at": now,
                "seed": True,
            }
            if embedding:
                doc["embedding"] = embedding
            reps = {}
            if clap_record:
                reps["audio_semantic"] = clap_dict
            if chroma_rec:
                reps["chroma"] = chroma_rec
            if reps:
                doc["representations"] = reps

            result = db["fragments"].insert_one(doc)
            logger.info("  Inserted %s", result.inserted_id)
            counts["ok"] += 1

        except Exception:
            logger.exception("  Failed: %s", f.name)
            counts["failed"] += 1

    logger.info(
        "Done: %d ok, %d skipped, %d failed",
        counts["ok"], counts["skipped"], counts["failed"],
    )
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
