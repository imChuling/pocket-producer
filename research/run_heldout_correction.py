"""Corrective held-out evaluation: train on FULL train side.

Protocol: protocol-heldout-correction-v1.md
Motivation: original scripts used val_fraction=0.25 internal split,
violating the protocol requirement to "retrain on full train side".
This script trains each seed on ALL 484 train sources.

Usage:
  # LAION-CLAP
  python research/run_heldout_correction.py \
    --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
    --split artifacts/heldout-split-packonly/split.json \
    --output artifacts/heldout-eval-correction \
    --mode laion

  # MS-CLAP
  python research/run_heldout_correction.py \
    --items research/data/fsld/items_msclap_packonly.jsonl \
    --split artifacts/heldout-split-packonly/split.json \
    --output artifacts/msclap-sensitivity-correction \
    --mode msclap
"""

import argparse
import json
import pathlib
import statistics
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from run_fusion import (
    PAIR_SEED,
    SEEDS,
    SIGNALS,
    build_feature_examples,
    compute_source_weights,
    evaluate,
    load_items,
    train_logistic,
)

FUSION_5SIG_IDX = [0, 1, 2, 3, 4]
COSINE_IDX = [0]
RULES_IDX = [2, 3, 4]

RULES_WEIGHTS = np.array([0.30, 0.20, 0.35])
RULES_WEIGHTS = RULES_WEIGHTS / RULES_WEIGHTS.sum()

HARD_SIMILAR_WEIGHT = 2.0
NEG_TYPE_WEIGHTS = {"hard_similar": HARD_SIMILAR_WEIGHT}

N_BOOTSTRAP = 10_000
ALPHA = 0.05


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", required=True, choices=["laion", "msclap", "mert"])
    args = parser.parse_args()

    print(f"=== Corrective held-out eval ({args.mode}) ===")
    print(f"Protocol: protocol-heldout-correction-v1.md")
    print(f"Training on FULL train side (no internal val split)\n")

    all_items = load_items(args.items)
    dim = len(all_items[0]["embedding"])
    print(f"Loaded {len(all_items)} items, embedding dim={dim}", flush=True)

    with open(args.split) as f:
        split_data = json.load(f)
    heldout_ids = set(split_data["heldout_source_ids"])
    print(f"Split: {split_data['n_train_sources']} train, "
          f"{split_data['n_heldout_sources']} held-out sources", flush=True)

    train_items = [i for i in all_items if i["source_id"] not in heldout_ids]
    heldout_items = [i for i in all_items if i["source_id"] in heldout_ids]
    print(f"Items: {len(train_items)} train, {len(heldout_items)} held-out",
          flush=True)

    aux = {}
    train_examples = build_feature_examples(train_items, seed=PAIR_SEED, aux=aux)
    heldout_examples = build_feature_examples(heldout_items, seed=PAIR_SEED, aux=aux)
    print(f"Examples: {len(train_examples)} train, {len(heldout_examples)} held-out\n",
          flush=True)

    # mert follows the msclap sw-BPR recipe (protocol-mert-sensitivity-v1.md)
    use_source_weights = args.mode in ("msclap", "mert")
    use_neg_weights = args.mode in ("msclap", "mert")

    fidx_fusion = np.array(FUSION_5SIG_IDX)
    fidx_cosine = np.array(COSINE_IDX)
    fidx_rules = np.array(RULES_IDX)

    per_seed_weights = []
    heldout_results = {"rules": [], "cosine": [], "fusion-5sig": []}

    for seed in SEEDS:
        print(f"--- Seed {seed} (train_examples={len(train_examples)}, "
              f"full train, no internal split) ---", flush=True)

        sw = compute_source_weights(train_examples) if use_source_weights else None
        ntw = NEG_TYPE_WEIGHTS if use_neg_weights else None

        w_fusion = train_logistic(
            train_examples, fidx_fusion, seed,
            source_weights=sw,
            neg_type_weights=ntw,
        )

        ev_rules = evaluate(heldout_examples, RULES_WEIGHTS, fidx_rules)
        ev_cosine = evaluate(heldout_examples, np.ones(1), fidx_cosine)
        ev_fusion = evaluate(heldout_examples, w_fusion, fidx_fusion)

        heldout_results["rules"].append(ev_rules)
        heldout_results["cosine"].append(ev_cosine)
        heldout_results["fusion-5sig"].append(ev_fusion)
        per_seed_weights.append({
            "seed": seed,
            "fusion-5sig": w_fusion.tolist(),
        })

        print(f"  rules={ev_rules['overall']:.4f}  "
              f"cosine={ev_cosine['overall']:.4f}  "
              f"fusion={ev_fusion['overall']:.4f}  "
              f"(hs: r={ev_rules.get('hard_similar', 0):.4f} "
              f"c={ev_cosine.get('hard_similar', 0):.4f} "
              f"f={ev_fusion.get('hard_similar', 0):.4f})",
              flush=True)

    # Summary
    print("\n=== HELD-OUT SUMMARY (full-train, 5 seeds) ===\n", flush=True)
    heldout_summary = {}
    neg_types = sorted({k for r in heldout_results["fusion-5sig"]
                        for k in r if k != "overall"})

    for name in heldout_results:
        overalls = [r["overall"] for r in heldout_results[name]]
        entry = {"mean_overall": round(statistics.mean(overalls), 4),
                 "std_overall": round(statistics.stdev(overalls), 4),
                 "values_overall": overalls}
        for nt in neg_types:
            vals = [r.get(nt, float("nan")) for r in heldout_results[name]]
            entry[f"mean_{nt}"] = round(statistics.mean(vals), 4)
            entry[f"values_{nt}"] = vals
        heldout_summary[name] = entry
        print(f"  {name:15s} overall={entry['mean_overall']:.4f}"
              f"+-{entry['std_overall']:.4f}  "
              + "  ".join(f"{nt}={entry[f'mean_{nt}']:.4f}"
                          for nt in neg_types),
              flush=True)

    # Bootstrap CIs
    print("\n=== Bootstrap CIs (source-grouped, pooled over seeds) ===\n",
          flush=True)
    rng = np.random.default_rng(42)
    sources = sorted(set(e["source_id"] for e in heldout_examples))
    n_src = len(sources)
    src_idx = {s: i for i, s in enumerate(sources)}
    bootstrap_results = {}

    for contrast_name, (ba, bb) in [
        ("fusion_vs_cosine", ("fusion-5sig", "cosine")),
        ("fusion_vs_rules", ("fusion-5sig", "rules")),
        ("cosine_vs_rules", ("cosine", "rules")),
    ]:
        all_seed_diffs = {nt: np.zeros((len(SEEDS), n_src))
                         for nt in neg_types + ["overall"]}
        cnt = {nt: np.zeros(n_src) for nt in neg_types + ["overall"]}

        for si, sw_entry in enumerate(per_seed_weights):
            w_f = np.array(sw_entry["fusion-5sig"])
            for ex in heldout_examples:
                i = src_idx[ex["source_id"]]
                for neg, ntype in zip(ex["negs"], ex["neg_types"]):
                    def score(baseline, pos_feat, neg_feat):
                        if baseline == "fusion-5sig":
                            return w_f @ pos_feat[fidx_fusion], w_f @ neg_feat[fidx_fusion]
                        elif baseline == "cosine":
                            return pos_feat[fidx_cosine][0], neg_feat[fidx_cosine][0]
                        else:
                            return (RULES_WEIGHTS @ pos_feat[fidx_rules],
                                    RULES_WEIGHTS @ neg_feat[fidx_rules])

                    sp_a, sn_a = score(ba, ex["pos"], neg)
                    sp_b, sn_b = score(bb, ex["pos"], neg)

                    win_a = 1.0 if sp_a > sn_a else (0.5 if sp_a == sn_a else 0.0)
                    win_b = 1.0 if sp_b > sn_b else (0.5 if sp_b == sn_b else 0.0)
                    d = win_a - win_b
                    all_seed_diffs[ntype][si, i] += d
                    all_seed_diffs["overall"][si, i] += d
                    if si == 0:
                        cnt[ntype][i] += 1
                        cnt["overall"][i] += 1

        contrast_cis = {}
        for nt in neg_types + ["overall"]:
            total = cnt[nt].sum()
            if total == 0:
                contrast_cis[nt] = {"point_delta": float("nan"),
                                    "ci_lo": float("nan"),
                                    "ci_hi": float("nan")}
                continue
            point = float(np.mean([all_seed_diffs[nt][si].sum() / total
                                   for si in range(len(SEEDS))]))
            deltas = np.empty(N_BOOTSTRAP)
            for b in range(N_BOOTSTRAP):
                idx = rng.integers(0, n_src, size=n_src)
                t = cnt[nt][idx].sum()
                if t == 0:
                    deltas[b] = np.nan
                else:
                    per_seed = [all_seed_diffs[nt][si, idx].sum() / t
                                for si in range(len(SEEDS))]
                    deltas[b] = np.mean(per_seed)
            lo = float(np.nanpercentile(deltas, 100 * ALPHA / 2))
            hi = float(np.nanpercentile(deltas, 100 * (1 - ALPHA / 2)))
            contrast_cis[nt] = {"point_delta": round(point, 6),
                                "ci_lo": round(lo, 6),
                                "ci_hi": round(hi, 6)}
            print(f"  {contrast_name} {nt:20s} "
                  f"delta={point:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]", flush=True)

        bootstrap_results[contrast_name] = contrast_cis

    # LOSO (modes with the sw-BPR recipe)
    loso_summary = None
    if args.mode in ("msclap", "mert"):
        print("\n=== LOSO ABLATION (held-out, full-train weights) ===\n",
              flush=True)
        full_idx = np.array(FUSION_5SIG_IDX)
        loso_results = {}

        for si, sw_entry in enumerate(per_seed_weights):
            w_full = np.array(sw_entry["fusion-5sig"])
            if si == 0:
                loso_results["full-5sig"] = []
            ev_full = evaluate(heldout_examples, w_full, full_idx)
            loso_results["full-5sig"].append(ev_full)

            for drop_i in range(5):
                name = f"minus-{SIGNALS[drop_i]}"
                if si == 0:
                    loso_results[name] = []
                kept = [j for j in range(5) if j != drop_i]
                w_kept = w_full[kept]
                ev = evaluate(heldout_examples, w_kept, np.array(kept))
                loso_results[name].append(ev)

        loso_summary = {}
        for name in loso_results:
            entry = {}
            for nt in neg_types + ["overall"]:
                vals = [r.get(nt, float("nan")) for r in loso_results[name]]
                entry[f"mean_{nt}"] = round(statistics.mean(vals), 4)
                entry[f"values_{nt}"] = vals
            loso_summary[name] = entry

        full_vals = {nt: loso_summary["full-5sig"][f"mean_{nt}"]
                     for nt in neg_types + ["overall"]}
        for name in loso_summary:
            if name == "full-5sig":
                print(f"  {'full-5sig':25s}" + "  ".join(
                    f"{nt}={loso_summary[name][f'mean_{nt}']:.4f}"
                    for nt in neg_types + ["overall"]), flush=True)
            else:
                deltas_pp = {nt: round((loso_summary[name][f"mean_{nt}"]
                                        - full_vals[nt]) * 100, 2)
                             for nt in neg_types + ["overall"]}
                print(f"  {name:25s}" + "  ".join(
                    f"{nt}={deltas_pp[nt]:+.2f}pp"
                    for nt in neg_types + ["overall"]), flush=True)

    # Save
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    report = {
        "experiment": f"corrective held-out eval ({args.mode})",
        "protocol": ("research/protocol-mert-sensitivity-v1.md"
                     if args.mode == "mert"
                     else "research/protocol-heldout-correction-v1.md"),
        "status": "post-hoc protocol correction, NOT confirmatory",
        "correction_note": ("Training on full 484 train sources per seed, "
                            "fixing protocol mismatch where original scripts "
                            "used val_fraction=0.25 internal split"),
        "items_file": str(args.items),
        "split_file": str(args.split),
        "split_sha256": split_data.get("sha256_heldout_ids", ""),
        "embedding_model": {
            "laion": "laion-clap-music",
            "msclap": "msclap-2023",
            "mert": "mert-v1-95m",
        }[args.mode],
        "embedding_dim": dim,
        "pair_seed": PAIR_SEED,
        "seeds": list(SEEDS),
        "source_weighted_bpr": use_source_weights,
        "neg_type_weights": NEG_TYPE_WEIGHTS if use_neg_weights else None,
        "training_note": "full train side, no internal val split",
        "heldout_summary": heldout_summary,
        "per_seed_weights": per_seed_weights,
        "bootstrap": bootstrap_results,
    }
    if loso_summary:
        report["loso"] = loso_summary

    with open(out / "sensitivity.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved to {out / 'sensitivity.json'}", flush=True)


if __name__ == "__main__":
    main()
