"""Build Layer-A weak pairs from the user's own fragment library.

Source identity = the project a fragment was grouped into; fragments that
lived in the same project are weak positives (own-materials layer of the
pretraining data). FSLD/FMA layers are added later behind per-item license
checks and get their own source ids.

Usage:
  backend/.venv/bin/python research/build_weak_pairs.py \
    --out research/data/weak_pairs.jsonl --seed 20260725
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from dotenv import dotenv_values  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from ranking.weak_pairs import build_weak_pairs  # noqa: E402


def load_items() -> list[dict]:
    config = dotenv_values(
        pathlib.Path(__file__).parent.parent / "backend" / ".env"
    )
    db = MongoClient(config["MONGODB_CONNECTION_STRING"])["pocketproducer"]
    docs = db.fragments.find(
        {"representations.audio_semantic.vector": {"$exists": True}},
        {
            "project_id": 1,
            "representations.audio_semantic.vector": 1,
            "bpm": 1,
            "key": 1,
            "tags": 1,
            "audio_features.duration_sec": 1,
            "audio_features.tempo_bpm": 1,
        },
    )
    items = []
    for doc in docs:
        project_id = doc.get("project_id")
        if not project_id:
            continue  # ungrouped fragments carry no same-composition signal
        features = doc.get("audio_features") or {}
        items.append(
            {
                "item_id": str(doc["_id"]),
                "source_id": f"project:{project_id}",
                "embedding": doc["representations"]["audio_semantic"]["vector"],
                "bpm": doc.get("bpm") or features.get("tempo_bpm"),
                "key": doc.get("key"),
                "tags": doc.get("tags") or [],
                "duration_seconds": features.get("duration_sec") or 0.0,
            }
        )
    return items


def load_items_file(path: str) -> list[dict]:
    rows = []
    for line in pathlib.Path(path).read_text().splitlines():
        row = json.loads(line)
        rows.append(
            {
                "item_id": row["item_id"],
                "source_id": row["source_id"],
                "embedding": row["embedding"],
                "bpm": row.get("bpm"),
                "key": row.get("key"),
                "tags": row.get("tags") or [],
                "duration_seconds": row.get("duration_seconds") or 0.0,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="research/data/weak_pairs.jsonl")
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument(
        "--items-file",
        default=None,
        help="Build from an items JSONL (e.g. FSLD) instead of the Mongo library",
    )
    args = parser.parse_args()

    items = load_items_file(args.items_file) if args.items_file else load_items()
    sources = {item["source_id"] for item in items}
    examples = build_weak_pairs(items, seed=args.seed)
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "".join(json.dumps(example) + "\n" for example in examples)
    )
    print(
        f"items={len(items)} sources={len(sources)} "
        f"examples={len(examples)} → {out_path}"
    )
    per_source: dict[str, int] = {}
    for example in examples:
        per_source[example["source_id"]] = per_source.get(example["source_id"], 0) + 1
    for source_id, count in sorted(per_source.items()):
        print(f"  {source_id}: {count} examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
