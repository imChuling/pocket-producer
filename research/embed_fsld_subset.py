"""Embed the annotated, well-cut FSLD subset with MS-CLAP.

Selection: manifest rows with human annotations, well_cut=true and
research_ok=true. Output items carry the per-item license class so weak-pair
artifacts can be filtered again at export time. Resumable: already-embedded
ids are skipped on re-run; wav bytes only ever live in a temp file.

Usage:
  backend/.venv/bin/python research/embed_fsld_subset.py \
    --zip research/data/fsld/FSL10K.zip \
    --out research/data/fsld/items.jsonl
"""

import argparse
import json
import pathlib
import sys
import tempfile
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

import librosa  # noqa: E402
import numpy as np  # noqa: E402

from ranking.adapters.base import encode_with_lineage  # noqa: E402


def make_adapter(name: str):
    if name == "msclap-2023":
        from ranking.adapters.msclap import MsClapAdapter

        return MsClapAdapter()
    if name == "laion-clap-music":
        from ranking.adapters.laion_clap import LaionClapMusicAdapter

        return LaionClapMusicAdapter()
    if name == "mert-v1-95m":
        from ranking.adapters.mert import MertAdapter

        return MertAdapter()
    raise ValueError(f"unknown adapter {name}")

DATA_DIR = pathlib.Path(__file__).parent / "data" / "fsld"
TARGET_SR = 44100
MAX_SECONDS = 30.0

ROLE_KEYS = ("percussion", "bass", "chords", "melody", "fx", "vocal")


def selected_rows(manifest_path: pathlib.Path) -> list[dict]:
    rows = []
    for line in manifest_path.read_text().splitlines():
        row = json.loads(line)
        if row.get("annotated") and row.get("well_cut") and row.get("research_ok"):
            rows.append(row)
    return rows


def normalized_key(row: dict) -> str | None:
    key, mode = row.get("key"), row.get("mode")
    if not key or not mode:
        return None
    mode_word = {"min": "minor", "maj": "major"}.get(mode, mode)
    return f"{key} {mode_word}"


def role_tags(row: dict) -> list[str]:
    instrumentation = row.get("instrumentation") or {}
    return [role for role in ROLE_KEYS if instrumentation.get(role)]


def parse_bpm(row: dict) -> float | None:
    for field in ("annotation_bpm", "metadata_bpm"):
        value = row.get(field)
        try:
            bpm = float(value)
        except (TypeError, ValueError):
            continue
        if bpm > 0:
            return bpm
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", default=str(DATA_DIR / "FSL10K.zip"))
    parser.add_argument("--manifest", default=str(DATA_DIR / "manifest.jsonl"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--adapter", default="msclap-2023")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--match-items",
        default=None,
        help="existing items jsonl; embed exactly its item_ids so a new "
        "representation shares the corpus (protocol-mert-sensitivity-v1)",
    )
    args = parser.parse_args()
    if args.out is None:
        suffix = "" if args.adapter == "msclap-2023" else f"_{args.adapter}"
        args.out = str(DATA_DIR / f"items{suffix}.jsonl")

    rows = selected_rows(pathlib.Path(args.manifest))
    if args.match_items:
        wanted = {
            json.loads(line)["item_id"]
            for line in pathlib.Path(args.match_items).read_text().splitlines()
            if line.strip()
        }
        rows = [r for r in rows if f"fsld:{r['freesound_id']}" in wanted]
        if len(rows) != len(wanted):
            raise SystemExit(
                f"--match-items mismatch: {len(wanted)} wanted, "
                f"{len(rows)} matched in manifest"
            )
        print(f"restricted to {len(rows)} items from {args.match_items}")
    if args.limit:
        rows = rows[: args.limit]
    print(f"selected annotated well-cut loops: {len(rows)}")

    out_path = pathlib.Path(args.out)
    done_ids: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            done_ids.add(json.loads(line)["item_id"])
        print(f"resuming: {len(done_ids)} already embedded")

    archive = zipfile.ZipFile(args.zip)
    wav_by_id: dict[str, str] = {}
    for name in archive.namelist():
        base = pathlib.Path(name).name
        if name.endswith(".wav") and "_" in base:
            wav_by_id.setdefault(base.split("_", 1)[0], name)
    print(f"wav members indexed: {len(wav_by_id)}")

    adapter = make_adapter(args.adapter)
    encoded = skipped = failed = 0
    with out_path.open("a") as sink:
        for index, row in enumerate(rows):
            item_id = f"fsld:{row['freesound_id']}"
            if item_id in done_ids:
                skipped += 1
                continue
            member = wav_by_id.get(str(row["freesound_id"]))
            if member is None:
                failed += 1
                continue
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
                    handle.write(archive.read(member))
                    handle.flush()
                    waveform, _ = librosa.load(
                        handle.name, sr=TARGET_SR, mono=True, duration=MAX_SECONDS
                    )
                record = encode_with_lineage(
                    adapter, waveform.astype(np.float32), TARGET_SR
                )
                sink.write(
                    json.dumps(
                        {
                            "item_id": item_id,
                            "source_id": row["source_id"],
                            "embedding": record.vector,
                            "model_id": record.model_id,
                            "revision": record.revision,
                            "bpm": parse_bpm(row),
                            "key": normalized_key(row),
                            "tags": role_tags(row) + (row.get("genres") or []),
                            "duration_seconds": round(
                                len(waveform) / TARGET_SR, 2
                            ),
                            "license_class": row["license_class"],
                            "redistribution_ok": row["redistribution_ok"],
                        }
                    )
                    + "\n"
                )
                sink.flush()
                encoded += 1
                if encoded % 50 == 0:
                    print(f"encoded {encoded}/{len(rows) - len(done_ids)}")
            except Exception as error:  # noqa: BLE001 - one bad wav must not kill the batch
                failed += 1
                print(f"FAILED {item_id}: {error}")
    print(f"encoded={encoded} resumed_skip={skipped} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
