"""Does per-signal standardization change the five-signal fusion?

The five signals live on different scales (CLAP cosines cluster in a narrow
band; tempo, key and tag overlap are [0, 1] with many exact zeros). This
trains fusion-5sig with and without dividing each signal by its train-set
standard deviation, on the same 5 source-grouped dev splits as run_fusion.py,
and reports val pairwise accuracy per negative regime plus the raw-scale
weights. Exploratory; not a paper number.

Usage:
  backend/.venv/bin/python research/run_standardize_check.py \
    --items research/data/fsld/items_laion-clap-music_packonly_train.jsonl \
    --mode laion --output artifacts/standardize-check
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.weak_pairs import split_sources  # noqa: E402

from run_fusion import (  # noqa: E402
    PAIR_SEED,
    SEEDS,
    SIGNALS,
    build_feature_examples,
    compute_source_weights,
    evaluate,
    feature_scale,
    load_items,
    train_logistic,
)

FUSION_5SIG_IDX = np.array([0, 1, 2, 3, 4])
NEG_TYPE_WEIGHTS = {"hard_similar": 2.0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--mode", required=True, choices=["laion", "msclap"],
                        help="msclap adds source-weighted BPR with hard_similar x2")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    items = load_items(args.items)
    examples = build_feature_examples(items, seed=PAIR_SEED, aux={})
    print(f"{len(items)} items, {len(examples)} examples, mode={args.mode}", flush=True)

    results = {"raw": [], "standardized": []}
    weights = {"raw": [], "standardized": []}
    scales = []
    for seed in SEEDS:
        train_src, _ = split_sources([e["source_id"] for e in examples], seed=seed,
                                     val_fraction=0.25)
        train_set = set(train_src)
        train = [e for e in examples if e["source_id"] in train_set]
        val = [e for e in examples if e["source_id"] not in train_set]
        sw = compute_source_weights(train) if args.mode == "msclap" else None
        ntw = NEG_TYPE_WEIGHTS if args.mode == "msclap" else None
        scales.append(feature_scale(train, FUSION_5SIG_IDX).tolist())
        for name, standardize in (("raw", False), ("standardized", True)):
            w = train_logistic(train, FUSION_5SIG_IDX, seed, source_weights=sw,
                               neg_type_weights=ntw, standardize=standardize)
            ev = evaluate(val, w, FUSION_5SIG_IDX)
            results[name].append(ev)
            weights[name].append(w.tolist())
            print(f"  seed {seed} {name:12s} overall={ev['overall']:.4f} "
                  + " ".join(f"{k}={v:.4f}" for k, v in ev.items() if k != "overall")
                  + f" w={np.array2string(w, precision=3)}", flush=True)

    neg_types = sorted({k for r in results["raw"] for k in r if k != "overall"})
    summary = {}
    for name in results:
        entry = {}
        for key in ["overall", *neg_types]:
            vals = [r[key] for r in results[name]]
            entry[f"mean_{key}"] = round(statistics.mean(vals), 4)
            entry[f"std_{key}"] = round(statistics.stdev(vals), 4)
        entry["mean_weights_raw_scale"] = [
            round(float(x), 4) for x in np.mean(weights[name], axis=0)
        ]
        summary[name] = entry
    delta = {
        key: round(summary["standardized"][f"mean_{key}"] - summary["raw"][f"mean_{key}"], 4)
        for key in ["overall", *neg_types]
    }
    print("\n=== standardized - raw (pp, 5-seed val means) ===")
    for key, value in delta.items():
        print(f"  {key:16s} {value * 100:+.2f}")

    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"standardize_{args.mode}.json").write_text(json.dumps({
        "experiment": "per-signal standardization check for fusion-5sig (dev side)",
        "items_file": args.items,
        "mode": args.mode,
        "pair_seed": PAIR_SEED,
        "seeds": SEEDS,
        "signals": [SIGNALS[i] for i in FUSION_5SIG_IDX],
        "mean_train_scale_1_over_std": [round(float(x), 4) for x in np.mean(scales, axis=0)],
        "summary": summary,
        "delta_standardized_minus_raw": delta,
        "per_seed": {"raw": results["raw"], "standardized": results["standardized"]},
        "note": "exploratory; the shipped weights and the paper's numbers use raw signals",
    }, indent=2))
    print(f"-> {out / f'standardize_{args.mode}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
