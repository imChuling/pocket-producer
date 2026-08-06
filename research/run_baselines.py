"""Baseline comparison: random, cosine-only, and learned rankers.

Evaluates on the same weak_pairs_fsld.jsonl with source-held-out splits,
identical to run_multiseed_grid.py. No GPU needed.

Usage:
  python research/run_baselines.py \
    --weak-data research/data/weak_pairs_fsld.jsonl \
    --output artifacts/baselines

Baselines:
  random-v1           uniform random scores (averaged over 100 trials)
  cosine-mean-v1      cosine(mean_context_vector, candidate)
  cosine-max-v1       max cosine(context_i, candidate) over context items
  linear-v1           learned 2-param model (from run_multiseed_grid)
  deepsets-v1         learned 295K-param model
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

import torch
from ranking.context_model import LadderConfig, PocketRankContext, trainable_parameters
from ranking.deepsets_ranker import DeepSetsRanker
from ranking.linear_ranker import LinearRanker
from ranking.training import train_model, pairwise_eval
from ranking.weak_pairs import split_sources

SEEDS = [20260725, 20260801, 20260802, 20260803, 20260804]
EPOCHS = 30
LR = 1e-3
D_MODEL = 128


def cosine_mean_eval(examples):
    wins = 0.0
    total = 0
    for ex in examples:
        ctx = np.array(ex["context_embeddings"])
        mean_ctx = ctx.mean(axis=0)
        mean_ctx = mean_ctx / (np.linalg.norm(mean_ctx) + 1e-9)
        pos = np.array(ex["positive_embedding"])
        pos = pos / (np.linalg.norm(pos) + 1e-9)
        pos_score = float(mean_ctx @ pos)
        for neg in ex["negative_embeddings"]:
            neg = np.array(neg)
            neg = neg / (np.linalg.norm(neg) + 1e-9)
            neg_score = float(mean_ctx @ neg)
            if pos_score > neg_score:
                wins += 1.0
            elif pos_score == neg_score:
                wins += 0.5
            total += 1
    return round(wins / total, 4) if total else None


def cosine_max_eval(examples):
    wins = 0.0
    total = 0
    for ex in examples:
        ctx = np.array(ex["context_embeddings"])
        ctx_norms = ctx / (np.linalg.norm(ctx, axis=1, keepdims=True) + 1e-9)
        pos = np.array(ex["positive_embedding"])
        pos = pos / (np.linalg.norm(pos) + 1e-9)
        pos_score = float((ctx_norms @ pos).max())
        for neg in ex["negative_embeddings"]:
            neg = np.array(neg)
            neg = neg / (np.linalg.norm(neg) + 1e-9)
            neg_score = float((ctx_norms @ neg).max())
            if pos_score > neg_score:
                wins += 1.0
            elif pos_score == neg_score:
                wins += 0.5
            total += 1
    return round(wins / total, 4) if total else None


def random_eval(examples, n_trials=100, seed=42):
    rng = np.random.default_rng(seed)
    accs = []
    for _ in range(n_trials):
        wins = 0.0
        total = 0
        for ex in examples:
            n_neg = len(ex["negative_embeddings"])
            scores = rng.random(1 + n_neg)
            pos_score = scores[0]
            for neg_score in scores[1:]:
                if pos_score > neg_score:
                    wins += 1.0
                elif pos_score == neg_score:
                    wins += 0.5
                total += 1
        accs.append(wins / total if total else 0.0)
    return round(float(np.mean(accs)), 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weak-data", required=True)
    parser.add_argument("--output", default="artifacts/baselines")
    args = parser.parse_args()

    data_path = pathlib.Path(args.weak_data)
    examples = [json.loads(l) for l in data_path.open() if l.strip()]
    input_dim = len(examples[0]["positive_embedding"])
    print(f"Loaded {len(examples)} examples, input_dim={input_dim}", flush=True)

    output = pathlib.Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    all_results = {}

    # Run over same seeds as multiseed experiment
    for model_id in ["random-v1", "cosine-mean-v1", "cosine-max-v1",
                      "linear-v1", "deepsets-v1", "pocketrank-context-v1"]:
        all_results[model_id] = {"per_seed": [], "params": None}

    print("\n=== Running baselines + learned models over 5 seeds ===\n", flush=True)

    for seed in SEEDS:
        print(f"--- Seed {seed} ---", flush=True)

        train_sources, val_sources = split_sources(
            [e["source_id"] for e in examples], seed=seed, val_fraction=0.25
        )
        train_set = set(train_sources)
        val_set = set(val_sources)
        train = [e for e in examples if e["source_id"] in train_set]
        val = [e for e in examples if e["source_id"] in val_set]
        print(f"  train={len(train)}, val={len(val)}", flush=True)

        # Baselines (no training, evaluated on val only)
        rand_acc = random_eval(val, seed=seed)
        all_results["random-v1"]["per_seed"].append(rand_acc)
        all_results["random-v1"]["params"] = 0
        print(f"  random-v1:       {rand_acc:.4f}", flush=True)

        cos_mean_acc = cosine_mean_eval(val)
        all_results["cosine-mean-v1"]["per_seed"].append(cos_mean_acc)
        all_results["cosine-mean-v1"]["params"] = 0
        print(f"  cosine-mean-v1:  {cos_mean_acc:.4f}", flush=True)

        cos_max_acc = cosine_max_eval(val)
        all_results["cosine-max-v1"]["per_seed"].append(cos_max_acc)
        all_results["cosine-max-v1"]["params"] = 0
        print(f"  cosine-max-v1:   {cos_max_acc:.4f}", flush=True)

        # Learned models
        config = LadderConfig(input_dim=input_dim, d_model=D_MODEL, structured_dim=0)
        for Builder, mid in [(LinearRanker, "linear-v1"),
                             (DeepSetsRanker, "deepsets-v1"),
                             (PocketRankContext, "pocketrank-context-v1")]:
            torch.manual_seed(seed)
            model = Builder(config)
            outcome = train_model(model, train, val, config, seed=seed, epochs=EPOCHS, lr=LR)
            all_results[mid]["per_seed"].append(outcome.val_pairwise_accuracy)
            all_results[mid]["params"] = trainable_parameters(model)
            print(f"  {mid:25s} {outcome.val_pairwise_accuracy:.4f}", flush=True)

    # Summary
    print("\n=== Summary (mean ± std, n=5) ===\n", flush=True)
    summary = {}
    for mid in ["random-v1", "cosine-mean-v1", "cosine-max-v1",
                 "linear-v1", "deepsets-v1", "pocketrank-context-v1"]:
        vals = all_results[mid]["per_seed"]
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if len(vals) >= 2 else 0.0
        params = all_results[mid]["params"]
        summary[mid] = {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "values": [round(v, 4) for v in vals],
            "params": params,
        }
        print(f"  {mid:25s}  {mean:.4f} ± {std:.4f}  (params={params})", flush=True)

    report = {
        "experiment": "baseline comparison",
        "dataset": str(args.weak_data),
        "seeds": SEEDS,
        "epochs": EPOCHS,
        "lr": LR,
        "d_model": D_MODEL,
        "models": summary,
    }

    out_path = output / "baselines.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n→ {out_path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
