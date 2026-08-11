"""Convert human-labeled BPR pairs to the offline evaluator format.

The export script outputs {context_embeddings, positive_embedding,
negative_embeddings} with raw vectors. The evaluator expects
{session, candidates, label} with structured objects. This script
bridges the two.

Usage:
  backend/.venv/bin/python research/convert_human_to_eval.py \
    --input research/data/human_pairs.jsonl \
    --output research/data/human_eval.jsonl
"""

import argparse
import json
import pathlib
import sys
import uuid


def convert(row: dict) -> dict:
    context_embeddings = row["context_embeddings"]
    positive = row["positive_embedding"]
    negatives = row["negative_embeddings"]

    preferred_id = f"preferred-{uuid.uuid5(uuid.NAMESPACE_URL, row['example_id'])}"
    rejected_ids = [
        f"rejected-{i}-{uuid.uuid5(uuid.NAMESPACE_URL, row['example_id'] + str(i))}"
        for i in range(len(negatives))
    ]

    candidates = [
        {
            "fragment_id": preferred_id,
            "duration_seconds": 4.0,
            "created_at_iso": "2026-08-01T00:00:00Z",
            "audio_url": "/synthetic",
            "audio_embedding": positive,
        }
    ]
    for rid, neg in zip(rejected_ids, negatives):
        candidates.append(
            {
                "fragment_id": rid,
                "duration_seconds": 4.0,
                "created_at_iso": "2026-08-01T00:00:00Z",
                "audio_url": "/synthetic",
                "audio_embedding": neg,
            }
        )

    return {
        "example_id": row["example_id"],
        "source_id": row.get("source_id", ""),
        "participant_hash": row.get("participant_hash", "unknown"),
        "session": {
            "project_id": row.get("context_project_hash", "p0"),
            "playhead_seconds": 0,
            "track_count": len(context_embeddings),
            "active_track_types": [],
            "region_audio_embeddings": context_embeddings,
        },
        "candidates": candidates,
        "label": {
            "type": "pairwise",
            "preferred_id": preferred_id,
            "rejected_id": rejected_ids[0],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in pathlib.Path(args.input).read_text().splitlines()
        if line.strip()
    ]
    converted = [convert(row) for row in rows]
    pathlib.Path(args.output).write_text(
        "".join(json.dumps(c) + "\n" for c in converted)
    )
    print(f"converted {len(converted)} pairs → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
