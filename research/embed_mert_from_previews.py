"""Compute MERT-v1-95M embeddings from downloaded preview MP3s.

Replaces embed_fsld_subset.py --adapter mert-v1-95m when FSL10K.zip
is not available. Uses the Freesound HQ preview MP3s instead.

The difference from source WAVs (lossy MP3 vs lossless WAV, possibly
slightly different duration/encoding) is a known limitation documented
in protocol-mert-sensitivity-v1.md addendum.

Usage:
  python research/embed_mert_from_previews.py

Prerequisites:
  python research/download_all_previews.py   (downloads the MP3s)
"""

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.adapters.base import encode_with_lineage
from ranking.research.adapters.mert import MertAdapter

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "research" / "data" / "fsld"
PREVIEW_DIR = DATA_DIR / "previews"
MATCH_ITEMS = DATA_DIR / "items_laion-clap-music_packonly.jsonl"
OUT_PATH = DATA_DIR / "items_mert_packonly.jsonl"

TARGET_SR = 24000
MAX_SECONDS = 30.0


def main():
    import librosa

    # Load reference items for matching
    ref_items = {}
    with open(MATCH_ITEMS) as f:
        for line in f:
            row = json.loads(line)
            ref_items[row["item_id"]] = row

    print(f"Reference items: {len(ref_items)}")
    print(f"Preview dir: {PREVIEW_DIR}")
    preview_count = len(list(PREVIEW_DIR.glob("*.mp3")))
    print(f"Available previews: {preview_count}")

    if preview_count < len(ref_items):
        print(f"WARNING: only {preview_count}/{len(ref_items)} previews available")
        print("Run download_all_previews.py first")

    # Resume support
    done_ids = set()
    if OUT_PATH.exists():
        for line in OUT_PATH.read_text().splitlines():
            if line.strip():
                done_ids.add(json.loads(line)["item_id"])
        print(f"Resuming: {len(done_ids)} already embedded")

    adapter = MertAdapter()
    encoded = skipped = failed = 0

    with open(OUT_PATH, "a") as sink:
        for item_id, ref in ref_items.items():
            if item_id in done_ids:
                skipped += 1
                continue

            fsid = item_id.split(":")[1]
            mp3_path = PREVIEW_DIR / f"{fsid}.mp3"

            if not mp3_path.exists():
                failed += 1
                continue

            try:
                waveform, sr = librosa.load(
                    str(mp3_path), sr=TARGET_SR, mono=True, duration=MAX_SECONDS
                )
                record = encode_with_lineage(
                    adapter, waveform.astype(np.float32), TARGET_SR
                )
                sink.write(
                    json.dumps({
                        "item_id": item_id,
                        "source_id": ref["source_id"],
                        "embedding": record.vector,
                        "model_id": record.model_id,
                        "revision": record.revision,
                        "bpm": ref.get("bpm"),
                        "key": ref.get("key"),
                        "tags": ref.get("tags") or [],
                        "duration_seconds": round(len(waveform) / TARGET_SR, 2),
                        "license_class": ref.get("license_class", "unknown"),
                        "redistribution_ok": ref.get("redistribution_ok", False),
                        "audio_source": "freesound_preview_mp3",
                    })
                    + "\n"
                )
                sink.flush()
                encoded += 1
                if encoded % 25 == 0:
                    print(f"  encoded {encoded}/{len(ref_items) - len(done_ids) - failed}")
            except Exception as e:
                failed += 1
                print(f"  FAILED {item_id}: {e}")

    print(f"\nDone: encoded={encoded} resumed={skipped} failed={failed}")
    total = len(list(OUT_PATH.read_text().splitlines()))
    print(f"Total items in output: {total}")


if __name__ == "__main__":
    main()
