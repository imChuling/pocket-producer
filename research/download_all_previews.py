"""Download Freesound HQ preview MP3s for all 1,797 pack-only items.

Used when FSL10K.zip (original WAVs) is unavailable. Preview audio is
sufficient for MERT embedding computation; the difference from source
WAVs is noted in the sensitivity report as a known limitation.

Usage:
  python research/download_all_previews.py
"""

import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "research" / "data" / "fsld" / "previews"
METADATA = ROOT / "research" / "data" / "fsld" / "metadata.json"
ITEMS = ROOT / "research" / "data" / "fsld" / "items_laion-clap-music_packonly.jsonl"


def main():
    meta = json.loads(METADATA.read_text())

    item_ids = []
    with open(ITEMS) as f:
        for line in f:
            row = json.loads(line)
            item_ids.append(row["item_id"])

    fsids = [iid.split(":")[1] for iid in item_ids]
    print(f"Items to download: {len(fsids)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0

    for i, fsid in enumerate(fsids):
        out_path = OUT_DIR / f"{fsid}.mp3"
        if out_path.exists() and out_path.stat().st_size > 1000:
            skipped += 1
            continue

        entry = meta.get(fsid)
        if not entry or not entry.get("preview_url"):
            print(f"  NO URL for {fsid}")
            failed += 1
            continue

        url = entry["preview_url"]
        if url.startswith("http://"):
            url = "https://" + url[7:]

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            out_path.write_bytes(data)
            downloaded += 1
            if downloaded % 100 == 0:
                print(f"  downloaded {downloaded} / {len(fsids) - skipped} "
                      f"(total {i+1}/{len(fsids)})", flush=True)
            time.sleep(0.1)
        except Exception as e:
            print(f"  FAILED {fsid}: {e}", flush=True)
            if out_path.exists():
                out_path.unlink()
            failed += 1

    print(f"\nDone: downloaded={downloaded} skipped={skipped} failed={failed}")
    print(f"Total files in {OUT_DIR}: {len(list(OUT_DIR.glob('*.mp3')))}")


if __name__ == "__main__":
    main()
