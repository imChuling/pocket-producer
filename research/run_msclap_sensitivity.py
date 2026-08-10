"""MS-CLAP sensitivity re-analysis (protocol-msclap-sensitivity-v1).

Three fixed baselines (rules, cosine, fusion) on the pack-only MS-CLAP
items with source-weighted BPR and hard_similar upweight=2.0.

Dev-set CV + held-out eval + source-grouped bootstrap + LOSO — all in
one script to ensure consistent data loading and weight handling.

Usage:
  python research/run_msclap_sensitivity.py \
    --items research/data/fsld/items_msclap_packonly.jsonl \
    --split artifacts/heldout-split-packonly/split.json \
    --output artifacts/msclap-sensitivity
"""

import argparse
import json
import pathlib
import statistics
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.weak_pairs import split_sources

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
RULES_IDX = [2, 3, 4]  # tempo, key, tag_jaccard

RULES_WEIGHTS = np.array([0.30, 0.20, 0.35])
RULES_WEIGHTS = RULES_WEIGHTS / RULES_WEIGHTS.sum()

HARD_SIMILAR_WEIGHT = 2.0
NEG_TYPE_WEIGHTS = {"hard_similar": HARD_SIMILAR_WEIGHT}

N_BOOTSTRAP = 10_000
ALPHA = 0.05
PROTOCOL = "research/protocol-msclap-sensitivity-v1.md"


def pair_results_by_source(examples, weights_dict, feature_indices_dict):
    """Compute per-pair win/loss for all baselines, grouped by source."""
    by_source = defaultdict(list)
    for ex in examples:
        results = {}
        for name, w in weights_dict.items():
            fidx = np.array(feature_indices_dict[name])
            sp = w @ ex["pos"][fidx]
            for i, (neg, ntype) in enumerate(zip(ex["negs"], ex["neg_types"])):
                sn = w @ neg[fidx]
                win = 1.0 if sp > sn else (0.5 if sp == sn else 0.0)
                key = (ex["source_id"], i, ntype)
                if key not in results:
                    results[key] = {"ntype": ntype}
                results[key][f"{name}_win"] = win
        for (sid, _, _), rec in results.items():
            by_source[sid].append(rec)
    return by_source


def bootstrap_delta(by_source, baseline_a, baseline_b, neg_types, n_boot, rng):
    """Source-grouped bootstrap CI for (A - B) accuracy delta."""
    sources = sorted(by_source.keys())
    n_src = len(sources)

    diff_by_src = {nt: np.zeros(n_src) for nt in neg_types + ["overall"]}
    cnt_by_src = {nt: np.zeros(n_src) for nt in neg_types + ["overall"]}

    for i, src in enumerate(sources):
        for p in by_source[src]:
            d = p[f"{baseline_a}_win"] - p[f"{baseline_b}_win"]
            diff_by_src[p["ntype"]][i] += d
            diff_by_src["overall"][i] += d
            cnt_by_src[p["ntype"]][i] += 1
            cnt_by_src["overall"][i] += 1

    result = {}
    for nt in neg_types + ["overall"]:
        total = cnt_by_src[nt].sum()
        if total == 0:
            result[nt] = {"point_delta": float("nan"), "ci_lo": float("nan"),
                          "ci_hi": float("nan")}
            continue
        point = float(diff_by_src[nt].sum() / total)
        deltas = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_src, size=n_src)
            t = cnt_by_src[nt][idx].sum()
            deltas[b] = diff_by_src[nt][idx].sum() / t if t > 0 else np.nan
        lo = float(np.nanpercentile(deltas, 100 * ALPHA / 2))
        hi = float(np.nanpercentile(deltas, 100 * (1 - ALPHA / 2)))
        result[nt] = {"point_delta": round(point, 6),
                      "ci_lo": round(lo, 6), "ci_hi": round(hi, 6)}
    return result


def run_dev_cv(examples, aux):
    """Dev-set 5-fold source-grouped CV with three baselines."""
    conditions = {
        "rules": (RULES_IDX, RULES_WEIGHTS, False),
        "cosine": (COSINE_IDX, np.ones(1), False),
        "fusion-5sig": (FUSION_5SIG_IDX, None, True),
    }
    results = {name: [] for name in conditions}

    for seed in SEEDS:
        train_src, val_src = split_sources(
            [e["source_id"] for e in examples], seed=seed, val_fraction=0.25
        )
        train_set = set(train_src)
        val_set = set(val_src)
        train = [e for e in examples if e["source_id"] in train_set]
        val = [e for e in examples if e["source_id"] in val_set]
        print(f"\n--- Seed {seed} (train={len(train)}, val={len(val)}) ---",
              flush=True)

        sw = compute_source_weights(train)

        for name, (fidx, fixed_w, needs_training) in conditions.items():
            fidx_arr = np.array(fidx)
            if needs_training:
                w = train_logistic(train, fidx_arr, seed,
                                   source_weights=sw,
                                   neg_type_weights=NEG_TYPE_WEIGHTS)
            else:
                w = fixed_w
            ev = evaluate(val, w, fidx_arr)
            results[name].append(ev)
            print(f"  {name:15s} overall={ev['overall']:.4f}  "
                  + "  ".join(f"{k}={v:.3f}" for k, v in ev.items()
                             if k != "overall"),
                  flush=True)

    print("\n=== Dev-set Summary (mean ± std over 5 seeds) ===\n", flush=True)
    summary = {}
    neg_types = sorted({k for r in results["fusion-5sig"]
                        for k in r if k != "overall"})
    for name in conditions:
        overalls = [r["overall"] for r in results[name]]
        entry = {"mean_overall": round(statistics.mean(overalls), 4),
                 "std_overall": round(statistics.stdev(overalls), 4),
                 "values_overall": overalls}
        for nt in neg_types:
            vals = [r.get(nt, float("nan")) for r in results[name]]
            entry[f"mean_{nt}"] = round(statistics.mean(vals), 4)
            entry[f"values_{nt}"] = vals
        summary[name] = entry
        print(f"  {name:15s} overall={entry['mean_overall']:.4f}"
              f"±{entry['std_overall']:.4f}  "
              + "  ".join(f"{nt}={entry[f'mean_{nt}']:.4f}"
                         for nt in neg_types),
              flush=True)
    return summary


def run_heldout(all_items, split_data, aux):
    """Single held-out evaluation with three baselines + bootstrap CIs."""
    heldout_ids = set(split_data["heldout_source_ids"])
    train_items = [i for i in all_items if i["source_id"] not in heldout_ids]
    heldout_items = [i for i in all_items if i["source_id"] in heldout_ids]

    print(f"\nItems: {len(train_items)} train, {len(heldout_items)} held-out",
          flush=True)

    train_examples = build_feature_examples(train_items, seed=PAIR_SEED, aux=aux)
    heldout_examples = build_feature_examples(heldout_items, seed=PAIR_SEED, aux=aux)
    print(f"Examples: {len(train_examples)} train, {len(heldout_examples)} held-out",
          flush=True)

    fidx_fusion = np.array(FUSION_5SIG_IDX)
    fidx_cosine = np.array(COSINE_IDX)
    fidx_rules = np.array(RULES_IDX)

    per_seed_weights = []
    heldout_results = {"rules": [], "cosine": [], "fusion-5sig": []}

    for seed in SEEDS:
        train_src_ids = [e["source_id"] for e in train_examples]
        int_train_src, int_val_src = split_sources(
            train_src_ids, seed=seed, val_fraction=0.25
        )
        int_train = [e for e in train_examples
                     if e["source_id"] in set(int_train_src)]

        sw = compute_source_weights(int_train)
        w_fusion = train_logistic(int_train, fidx_fusion, seed,
                                  source_weights=sw,
                                  neg_type_weights=NEG_TYPE_WEIGHTS)

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

        print(f"  seed {seed}: rules={ev_rules['overall']:.4f}  "
              f"cosine={ev_cosine['overall']:.4f}  "
              f"fusion={ev_fusion['overall']:.4f}  "
              f"(hs: r={ev_rules.get('hard_similar', 0):.4f} "
              f"c={ev_cosine.get('hard_similar', 0):.4f} "
              f"f={ev_fusion.get('hard_similar', 0):.4f})",
              flush=True)

    # Summary
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

    # Bootstrap CIs for pairwise deltas: fusion-cosine, fusion-rules, cosine-rules
    print("\n=== Bootstrap CIs (source-grouped, pooled over seeds) ===\n",
          flush=True)
    rng = np.random.default_rng(42)
    bootstrap_results = {}

    for contrast_name, (ba, bb) in [
        ("fusion_vs_cosine", ("fusion-5sig", "cosine")),
        ("fusion_vs_rules", ("fusion-5sig", "rules")),
        ("cosine_vs_rules", ("cosine", "rules")),
    ]:
        # Pooled across seeds with joint source resampling
        sources = sorted(set(e["source_id"] for e in heldout_examples))
        n_src = len(sources)
        src_idx = {s: i for i, s in enumerate(sources)}

        all_seed_diffs = {nt: np.zeros((len(SEEDS), n_src))
                         for nt in neg_types + ["overall"]}
        cnt = {nt: np.zeros(n_src) for nt in neg_types + ["overall"]}

        for si, sw_entry in enumerate(per_seed_weights):
            w_f = np.array(sw_entry["fusion-5sig"])
            for ex in heldout_examples:
                i = src_idx[ex["source_id"]]
                for neg, ntype in zip(ex["negs"], ex["neg_types"]):
                    if ba == "fusion-5sig":
                        sp_a = w_f @ ex["pos"][fidx_fusion]
                        sn_a = w_f @ neg[fidx_fusion]
                    elif ba == "cosine":
                        sp_a = ex["pos"][fidx_cosine][0]
                        sn_a = neg[fidx_cosine][0]
                    else:
                        sp_a = RULES_WEIGHTS @ ex["pos"][fidx_rules]
                        sn_a = RULES_WEIGHTS @ neg[fidx_rules]

                    if bb == "cosine":
                        sp_b = ex["pos"][fidx_cosine][0]
                        sn_b = neg[fidx_cosine][0]
                    elif bb == "rules":
                        sp_b = RULES_WEIGHTS @ ex["pos"][fidx_rules]
                        sn_b = RULES_WEIGHTS @ neg[fidx_rules]
                    else:
                        sp_b = w_f @ ex["pos"][fidx_fusion]
                        sn_b = w_f @ neg[fidx_fusion]

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

    return heldout_summary, per_seed_weights, heldout_examples, bootstrap_results


def run_loso(heldout_examples, per_seed_weights):
    """Leave-one-signal-out ablation on held-out data."""
    print("\n" + "=" * 60)
    print("LOSO ABLATION (held-out)")
    print("=" * 60)

    full_idx = np.array(FUSION_5SIG_IDX)
    loso_results = {}

    for si, sw_entry in enumerate(per_seed_weights):
        seed = sw_entry["seed"]
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

    neg_types = sorted({k for r in loso_results["full-5sig"]
                        for k in r if k != "overall"})
    loso_summary = {}
    for name in loso_results:
        entry = {}
        for nt in neg_types + ["overall"]:
            vals = [r.get(nt, float("nan")) for r in loso_results[name]]
            entry[f"mean_{nt}"] = round(statistics.mean(vals), 4)
            entry[f"values_{nt}"] = vals
        loso_summary[name] = entry

    print("\n  LOSO deltas (mean over 5 seeds, pp change from full):\n",
          flush=True)
    full_vals = {nt: loso_summary["full-5sig"][f"mean_{nt}"]
                 for nt in neg_types + ["overall"]}
    for name in loso_summary:
        if name == "full-5sig":
            print(f"  {'full-5sig':25s}" + "  ".join(
                f"{nt}={loso_summary[name][f'mean_{nt}']:.4f}"
                for nt in neg_types + ["overall"]), flush=True)
        else:
            deltas = {nt: round((loso_summary[name][f"mean_{nt}"]
                                 - full_vals[nt]) * 100, 2)
                      for nt in neg_types + ["overall"]}
            print(f"  {name:25s}" + "  ".join(
                f"{nt}={deltas[nt]:+.2f}pp" for nt in neg_types + ["overall"]),
                  flush=True)

    return loso_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", default="research/data/fsld/items_msclap_packonly.jsonl")
    parser.add_argument("--split", default="artifacts/heldout-split-packonly/split.json")
    parser.add_argument("--output", default="artifacts/msclap-sensitivity")
    args = parser.parse_args()

    all_items = load_items(args.items)
    dim = len(all_items[0]["embedding"])
    print(f"Loaded {len(all_items)} items, embedding dim={dim}", flush=True)

    aux = {}

    with open(args.split) as f:
        split_data = json.load(f)
    heldout_ids = set(split_data["heldout_source_ids"])

    train_items = [i for i in all_items if i["source_id"] not in heldout_ids]

    # === Phase 1: Dev-set CV (train side only) ===
    print("\n" + "=" * 60)
    print("PHASE 1: Dev-set CV (train side only, source-weighted BPR)")
    print("=" * 60)

    train_examples = build_feature_examples(train_items, seed=PAIR_SEED, aux=aux)
    print(f"  {len(train_examples)} train examples", flush=True)

    source_counts = Counter(e["source_id"] for e in train_examples)
    print(f"  {len(source_counts)} sources with examples "
          f"(min={min(source_counts.values())}, "
          f"max={max(source_counts.values())}, "
          f"median={sorted(source_counts.values())[len(source_counts)//2]})",
          flush=True)

    neg_type_counts = Counter()
    for ex in train_examples:
        for nt in ex["neg_types"]:
            neg_type_counts[nt] += 1
    print(f"  neg type distribution: {dict(neg_type_counts)}", flush=True)

    dev_summary = run_dev_cv(train_examples, aux)

    # === Phase 2: Held-out evaluation (single run) ===
    print("\n" + "=" * 60)
    print("PHASE 2: Held-out evaluation (sensitivity re-analysis)")
    print("=" * 60)

    (heldout_summary, per_seed_weights,
     heldout_examples, bootstrap_results) = run_heldout(all_items, split_data, aux)

    # === Phase 3: LOSO ablation on held-out ===
    loso_summary = run_loso(heldout_examples, per_seed_weights)

    # === Save everything ===
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    report = {
        "experiment": "MS-CLAP sensitivity re-analysis (protocol-msclap-sensitivity-v1)",
        "protocol": PROTOCOL,
        "status": "sensitivity re-analysis, NOT confirmatory",
        "items_file": str(args.items),
        "split_file": str(args.split),
        "split_sha256": split_data["sha256_heldout_ids"],
        "embedding_model": "msclap-2023",
        "embedding_dim": dim,
        "pair_seed": PAIR_SEED,
        "seeds": SEEDS,
        "baselines": {
            "rules": {"signals": [SIGNALS[i] for i in RULES_IDX],
                      "weights": RULES_WEIGHTS.tolist(),
                      "trained": False},
            "cosine": {"signals": [SIGNALS[i] for i in COSINE_IDX],
                       "weights": [1.0],
                       "trained": False},
            "fusion-5sig": {"signals": [SIGNALS[i] for i in FUSION_5SIG_IDX],
                            "trained": True,
                            "source_weighted": True,
                            "hard_similar_weight": HARD_SIMILAR_WEIGHT},
        },
        "train_sources": split_data["n_train_sources"],
        "heldout_sources": split_data["n_heldout_sources"],
        "dev_summary": dev_summary,
        "heldout_summary": heldout_summary,
        "bootstrap": bootstrap_results,
        "loso": loso_summary,
    }

    (out / "sensitivity.json").write_text(json.dumps(report, indent=2))
    print(f"\n-> {out / 'sensitivity.json'}", flush=True)

    (out / "weights.json").write_text(json.dumps(per_seed_weights, indent=2))
    print(f"-> {out / 'weights.json'}", flush=True)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
