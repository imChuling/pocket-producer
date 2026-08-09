"""Grouped bootstrap CI for held-out fusion−cosine delta.

Resamples at the SOURCE level (pack/user) to respect within-source
correlation.  Uses saved weights from artifacts/heldout-eval/weights.json
— no retraining.

Pre-registers three wording tiers BEFORE seeing the interval:
  - entirely > 0 → "small but positive held-out gain"
  - crosses 0   → "the held-out difference was small and uncertain"
  - entirely < 0 → "did not replicate"

Usage:
  backend/.venv/bin/python research/bootstrap_heldout.py \
    --items research/data/fsld/items_laion-clap-music.jsonl \
    --split artifacts/heldout-split/split.json \
    --weights artifacts/heldout-eval/weights.json \
    --output artifacts/heldout-eval/bootstrap.json
"""

import argparse
import json
import pathlib
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from run_fusion import PAIR_SEED, build_feature_examples, load_items
from run_heldout_eval import COSINE_IDX, FUSION_5SIG_IDX, load_aux

N_BOOTSTRAP = 10_000
ALPHA = 0.05


def pair_results_by_source(examples, w_fusion, w_cosine):
    """Compute per-pair win/loss for fusion and cosine, grouped by source."""
    fidx = np.array(FUSION_5SIG_IDX)
    cidx = np.array(COSINE_IDX)
    by_source = defaultdict(list)

    for ex in examples:
        sp_f = w_fusion @ ex["pos"][fidx]
        sp_c = w_cosine @ ex["pos"][cidx]
        for neg, ntype in zip(ex["negs"], ex["neg_types"]):
            sn_f = w_fusion @ neg[fidx]
            sn_c = w_cosine @ neg[cidx]
            f_win = 1.0 if sp_f > sn_f else (0.5 if sp_f == sn_f else 0.0)
            c_win = 1.0 if sp_c > sn_c else (0.5 if sp_c == sn_c else 0.0)
            by_source[ex["source_id"]].append({
                "ntype": ntype,
                "fusion_win": f_win,
                "cosine_win": c_win,
            })
    return by_source


def aggregate_delta(pairs, neg_type):
    """Compute fusion−cosine accuracy delta for a given negative type."""
    f_total = c_total = count = 0.0
    for p in pairs:
        if p["ntype"] == neg_type:
            f_total += p["fusion_win"]
            c_total += p["cosine_win"]
            count += 1
    if count == 0:
        return float("nan")
    return (f_total - c_total) / count


def bootstrap_ci(by_source, neg_type, n_boot, rng):
    sources = list(by_source.keys())
    n = len(sources)
    deltas = np.empty(n_boot)

    for b in range(n_boot):
        sampled = rng.choice(sources, size=n, replace=True)
        pairs = []
        for s in sampled:
            pairs.extend(by_source[s])
        deltas[b] = aggregate_delta(pairs, neg_type)

    lo = float(np.nanpercentile(deltas, 100 * ALPHA / 2))
    hi = float(np.nanpercentile(deltas, 100 * (1 - ALPHA / 2)))
    return deltas, lo, hi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--split", default="artifacts/heldout-split/split.json")
    parser.add_argument("--weights", default="artifacts/heldout-eval/weights.json")
    parser.add_argument("--chroma", default="research/data/fsld/chroma.jsonl")
    parser.add_argument("--role-prompts", default="research/data/fsld/role_prompts.json")
    parser.add_argument("--output", default="artifacts/heldout-eval/bootstrap.json")
    parser.add_argument("--n-boot", type=int, default=N_BOOTSTRAP)
    args = parser.parse_args()

    with open(args.split) as f:
        split_data = json.load(f)
    heldout_ids = set(split_data["heldout_source_ids"])

    all_items = load_items(args.items)
    heldout_items = [i for i in all_items if i["source_id"] in heldout_ids]
    print(f"{len(heldout_items)} held-out items from "
          f"{len(heldout_ids)} sources", flush=True)

    aux = load_aux(all_items, args.chroma, args.role_prompts)

    print("Building held-out examples...", flush=True)
    examples = build_feature_examples(heldout_items, seed=PAIR_SEED, aux=aux)
    print(f"  {len(examples)} examples", flush=True)

    with open(args.weights) as f:
        all_weights = json.load(f)

    w_cosine = np.ones(1)
    rng = np.random.default_rng(42)

    neg_types = ["hard_similar", "hard_tempo_key", "easy", "overall"]
    seed_results = []

    # Precompute per-seed pair results once; reused by per-seed CIs and
    # the pooled bootstrap below.
    by_source_per_seed = {}
    for sw in all_weights:
        w_fusion = np.array(sw["fusion-5sig"])
        by_source_per_seed[sw["seed"]] = pair_results_by_source(
            examples, w_fusion, w_cosine
        )

    for sw in all_weights:
        seed = sw["seed"]
        by_source = by_source_per_seed[seed]

        print(f"\n--- Seed {seed} ({len(by_source)} sources) ---", flush=True)
        seed_report = {"seed": seed}

        for nt in neg_types:
            if nt == "overall":
                point = aggregate_delta_all(by_source)
                deltas, lo, hi = bootstrap_ci_all(by_source, args.n_boot, rng)
            else:
                point = aggregate_delta(by_source_flat(by_source), nt)
                deltas, lo, hi = bootstrap_ci(by_source, nt, args.n_boot, rng)

            wording = ci_wording(lo, hi)
            seed_report[nt] = {
                "point_delta": round(point, 6),
                "ci_lo": round(lo, 6),
                "ci_hi": round(hi, 6),
                "wording": wording,
            }
            print(f"  {nt:20s} delta={point:+.4f}  "
                  f"95% CI [{lo:+.4f}, {hi:+.4f}]  → {wording}", flush=True)

        seed_results.append(seed_report)

    # Pooled across seeds: the seeds share one test set, so a single source
    # resample must be applied to ALL seeds within each bootstrap draw.
    # (Resampling per seed and averaging draws positionally would cancel
    # resampling variance across seeds and artificially narrow the CI.)
    print("\n=== POOLED (mean over 5 seeds, joint source resampling) ===",
          flush=True)
    seeds = [sw["seed"] for sw in all_weights]
    sources = sorted(by_source_per_seed[seeds[0]].keys())
    n_src = len(sources)

    # Per-source sufficient statistics: diff[seed][nt][i] = sum of
    # (fusion_win - cosine_win) over source i's pairs of that type;
    # cnt[nt][i] = pair count (identical across seeds).
    diff = {s: {nt: np.zeros(n_src) for nt in neg_types} for s in seeds}
    cnt = {nt: np.zeros(n_src) for nt in neg_types}
    for i, src in enumerate(sources):
        for seed in seeds:
            for p in by_source_per_seed[seed][src]:
                d = p["fusion_win"] - p["cosine_win"]
                diff[seed][p["ntype"]][i] += d
                diff[seed]["overall"][i] += d
        for p in by_source_per_seed[seeds[0]][src]:
            cnt[p["ntype"]][i] += 1
            cnt["overall"][i] += 1

    pooled_deltas = {nt: np.empty(args.n_boot) for nt in neg_types}
    for b in range(args.n_boot):
        idx = rng.integers(0, n_src, size=n_src)
        for nt in neg_types:
            total = cnt[nt][idx].sum()
            if total == 0:
                pooled_deltas[nt][b] = np.nan
                continue
            per_seed = [diff[s][nt][idx].sum() / total for s in seeds]
            pooled_deltas[nt][b] = np.mean(per_seed)

    pooled = {}
    for nt in neg_types:
        # Point estimate from the observed (non-resampled) data
        total = cnt[nt].sum()
        point = float(np.mean([diff[s][nt].sum() / total for s in seeds]))
        lo = float(np.nanpercentile(pooled_deltas[nt], 100 * ALPHA / 2))
        hi = float(np.nanpercentile(pooled_deltas[nt], 100 * (1 - ALPHA / 2)))
        wording = ci_wording(lo, hi)

        pooled[nt] = {
            "point_delta": round(point, 6),
            "ci_lo": round(lo, 6),
            "ci_hi": round(hi, 6),
            "wording": wording,
        }
        print(f"  {nt:20s} delta={point:+.4f}  "
              f"95% CI [{lo:+.4f}, {hi:+.4f}]  → {wording}", flush=True)

    report = {
        "method": "source-grouped bootstrap (pooled: joint source resampling shared across seeds)",
        "n_bootstrap": args.n_boot,
        "alpha": ALPHA,
        "neg_types": neg_types,
        "preregistered_wording": {
            "entirely_positive": "small but positive held-out gain",
            "crosses_zero": "the held-out difference was small and uncertain",
            "entirely_negative": "did not replicate",
        },
        "per_seed": seed_results,
        "pooled": pooled,
    }

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"\n-> {out}", flush=True)


def by_source_flat(by_source):
    """Flatten source-grouped pairs into a single list."""
    return [p for pairs in by_source.values() for p in pairs]


def aggregate_delta_all(by_source):
    """Overall fusion−cosine delta (all neg types pooled)."""
    pairs = by_source_flat(by_source)
    f_total = sum(p["fusion_win"] for p in pairs)
    c_total = sum(p["cosine_win"] for p in pairs)
    n = len(pairs)
    return (f_total - c_total) / n if n else float("nan")


def bootstrap_ci_all(by_source, n_boot, rng):
    """Bootstrap CI for overall delta (all neg types pooled)."""
    sources = list(by_source.keys())
    n = len(sources)
    deltas = np.empty(n_boot)
    for b in range(n_boot):
        sampled = rng.choice(sources, size=n, replace=True)
        f_total = c_total = count = 0.0
        for s in sampled:
            for p in by_source[s]:
                f_total += p["fusion_win"]
                c_total += p["cosine_win"]
                count += 1
        deltas[b] = (f_total - c_total) / count if count else float("nan")
    lo = float(np.nanpercentile(deltas, 100 * ALPHA / 2))
    hi = float(np.nanpercentile(deltas, 100 * (1 - ALPHA / 2)))
    return deltas, lo, hi


def ci_wording(lo, hi):
    if lo > 0:
        return "small but positive held-out gain"
    if hi < 0:
        return "did not replicate"
    return "the held-out difference was small and uncertain"


if __name__ == "__main__":
    raise SystemExit(main())
