"""Download Freesound preview audio for held-out split items.

Downloads HQ MP3 previews (~300KB each) for all 408 held-out items.
Skips items that already exist on disk.

Usage:
  python research/download_heldout_audio.py
"""

import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts" / "cocola-audio"
METADATA = ROOT / "research" / "data" / "fsld" / "metadata.json"
ITEMS = ROOT / "research" / "data" / "fsld" / "items_laion-clap-music_packonly.jsonl"
SPLIT = ROOT / "artifacts" / "heldout-split-packonly" / "split.json"


def main():
    split = json.loads(SPLIT.read_text())
    heldout_sources = set(split["heldout_source_ids"])

    items = []
    with open(ITEMS) as f:
        for line in f:
            d = json.loads(line)
            if d["source_id"] in heldout_sources:
                items.append(d)

    meta = json.loads(METADATA.read_text())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    skipped = 0
    failed = 0

    for i, item in enumerate(items):
        fsid = item["item_id"].replace("fsld:", "")
        out_path = OUT_DIR / f"{fsid}.mp3"

        if out_path.exists() and out_path.stat().st_size > 0:
            skipped += 1
            continue

        preview_url = meta[fsid]["preview_url"]
        # Upgrade to HTTPS
        if preview_url.startswith("http://"):
            preview_url = "https://" + preview_url[7:]

        try:
            urllib.request.urlretrieve(preview_url, str(out_path))
            downloaded += 1
            if downloaded % 20 == 0:
                print(f"  [{i+1}/{len(items)}] downloaded {downloaded}, skipped {skipped}", flush=True)
            time.sleep(0.1)
        except Exception as e:
            print(f"  FAIL {fsid}: {e}", flush=True)
            failed += 1

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped, {failed} failed out of {len(items)} items")


if __name__ == "__main__":
    main()
