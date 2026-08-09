"""Held-out LOSO ablation: retrain with one signal dropped, evaluate on held-out.

For each of the 5 signals, trains a "minus-one" BPR fusion on the train
split and evaluates on the frozen held-out split.  Computes per-negative-type
deltas to verify that regime-dependent signal contributions replicate.

Usage:
  backend/.venv/bin/python research/loso_heldout.py \
    --items research/data/fsld/items_laion-clap-music.jsonl \
    --split artifacts/heldout-split/split.json \
    --output artifacts/heldout-eval/loso.json
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.weak_pairs import split_sources

from run_fusion import (
    PAIR_SEED,
    SEEDS,
    SIGNALS,
    build_feature_examples,
    evaluate,
    load_items,
    train_logistic,
)
from run_heldout_eval import FUSION_5SIG_IDX, load_aux

SIGNAL_NAMES = [SIGNALS[i] for i in FUSION_5SIG_IDX]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--split", default="artifacts/heldout-split/split.json")
    parser.add_argument("--chroma", default="research/data/fsld/chroma.jsonl")
    parser.add_argument("--role-prompts", default="research/data/fsld/role_prompts.json")
    parser.add_argument("--output", default="artifacts/heldout-eval/loso.json")
    args = parser.parse_args()

    with open(args.split) as f:
        split_data = json.load(f)
    heldout_ids = set(split_data["heldout_source_ids"])

    all_items = load_items(args.items)
    train_items = [i for i in all_items if i["source_id"] not in heldout_ids]
    heldout_items = [i for i in all_items if i["source_id"] in heldout_ids]
    print(f"Items: {len(train_items)} train, {len(heldout_items)} held-out", flush=True)

    aux = load_aux(all_items, args.chroma, args.role_prompts)

    print("Building examples...", flush=True)
    train_examples = build_feature_examples(train_items, seed=PAIR_SEED, aux=aux)
    heldout_examples = build_feature_examples(heldout_items, seed=PAIR_SEED, aux=aux)
    print(f"  {len(train_examples)} train, {len(heldout_examples)} held-out", flush=True)

    # Full 5-signal baseline on held-out (retrained on train split)
    conditions = {"full-5sig": list(FUSION_5SIG_IDX)}
    for drop_i, drop_name in enumerate(SIGNAL_NAMES):
        remaining = [idx for idx in FUSION_5SIG_IDX if idx != FUSION_5SIG_IDX[drop_i]]
        conditions[f"minus-{drop_name}"] = remaining

    results = {}
    for cond_name, fidx_list in conditions.items():
        fidx = np.array(fidx_list)
        seed_evals = []

        for seed in SEEDS:
            train_src_ids = [e["source_id"] for e in train_examples]
            int_train_src, int_val_src = split_sources(
                train_src_ids, seed=seed, val_fraction=0.25
            )
            int_train = [e for e in train_examples if e["source_id"] in set(int_train_src)]

            w = train_logistic(int_train, fidx, seed)
            ev = evaluate(heldout_examples, w, fidx)
            seed_evals.append(ev)

        neg_types = sorted({k for ev in seed_evals for k in ev if k != "overall"})
        entry = {}
        for nt in ["overall"] + neg_types:
            vals = [ev.get(nt, float("nan")) for ev in seed_evals]
            entry[f"mean_{nt}"] = round(statistics.mean(vals), 4)
            entry[f"values_{nt}"] = [round(v, 4) for v in vals]
        results[cond_name] = entry

        print(f"  {cond_name:25s} overall={entry['mean_overall']:.4f}  "
              + "  ".join(f"{nt}={entry[f'mean_{nt}']:.4f}" for nt in neg_types),
              flush=True)

    # Compute LOSO deltas
    full = results["full-5sig"]
    neg_types = sorted({k.replace("mean_", "") for k in full
                        if k.startswith("mean_") and k != "mean_overall"})

    loso_deltas = {}
    print("\n=== LOSO DELTAS (held-out) ===", flush=True)
    for drop_name in SIGNAL_NAMES:
        minus = results[f"minus-{drop_name}"]
        deltas = {}
        for nt in ["overall"] + neg_types:
            d = round(minus[f"mean_{nt}"] - full[f"mean_{nt}"], 4)
            deltas[nt] = d
        loso_deltas[drop_name] = deltas
        print(f"  minus-{drop_name:18s} " +
              "  ".join(f"{nt}={deltas[nt]:+.4f}" for nt in ["overall"] + neg_types),
              flush=True)

    report = {
        "experiment": "held-out LOSO ablation",
        "split": args.split,
        "signals": SIGNAL_NAMES,
        "seeds": SEEDS,
        "conditions": results,
        "loso_deltas": loso_deltas,
    }

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"\n-> {out}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
