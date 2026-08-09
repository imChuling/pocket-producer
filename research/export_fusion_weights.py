"""Train fusion-5sig on a full items file and export deployment weights.

Trains the same BPR logistic fusion as run_fusion.py, but on ALL examples
from the given items file (no validation carve-out — this is a deployment
export, not an evaluation), averaging weights over the standard 5 seeds.

The items file should be the pack-only TRAIN side of the frozen held-out
split, in the DEPLOYED embedding space (msclap-2023), so the shipped
ranker matches both the paper's training recipe and the production
representation.

Usage:
  backend/.venv/bin/python research/export_fusion_weights.py \
    --items research/data/fsld/items_msclap_packonly_train.jsonl \
    --output artifacts/fusion-deploy/weights.json
"""

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from run_fusion import (
    PAIR_SEED,
    SEEDS,
    build_feature_examples,
    evaluate,
    load_items,
    train_logistic,
)

FUSION_5SIG_IDX = np.array([0, 1, 2, 3, 4])
SIGNAL_NAMES = ["audio_cos_mean", "audio_cos_max", "tempo", "key", "tag_jaccard"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    items = load_items(args.items)
    # load_items drops model_id; read it from the raw file for metadata.
    with open(args.items) as f:
        model_ids = {
            json.loads(line).get("model_id") for line in f if line.strip()
        }
    model_ids.discard(None)
    print(f"{len(items)} items, embedding space: {model_ids}")

    examples = build_feature_examples(items, seed=PAIR_SEED, aux={})
    print(f"{len(examples)} examples")

    per_seed = []
    for seed in SEEDS:
        w = train_logistic(examples, FUSION_5SIG_IDX, seed)
        ev = evaluate(examples, w, FUSION_5SIG_IDX)
        per_seed.append(w)
        print(f"  seed {seed}: train-fit overall={ev['overall']:.4f} "
              f"w={np.array2string(w, precision=3)}")

    mean_w = np.mean(per_seed, axis=0)
    print(f"mean weights: {np.array2string(mean_w, precision=4)}")

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model_id": "fusion-5sig-v1",
        "signals": SIGNAL_NAMES,
        "weights": [round(float(x), 6) for x in mean_w],
        "per_seed_weights": {
            str(s): [round(float(x), 6) for x in w]
            for s, w in zip(SEEDS, per_seed)
        },
        "representation_model": sorted(model_ids),
        "trained_on": (
            "pack-only train split (protocol-heldout-v2), "
            "pack co-membership weak labels, BPR, mean over 5 seeds"
        ),
        "items_file": args.items,
    }, indent=2))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
