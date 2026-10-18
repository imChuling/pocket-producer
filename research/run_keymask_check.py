"""How much does the train/serve key mismatch cost the deployed fusion?

Online the host DAW exposes no key, so the key signal is always 0, but the
shipped weights were trained with key present. On the dev splits this
compares, all under key = 0 at evaluation time:

  raw      weights trained with key present (the shipped recipe)
  masked   weights trained with key zeroed, as it is online

plus the raw weights evaluated with key present, as the reference the paper
reports. Deployed recipe only (MS-CLAP space, source-weighted BPR,
hard_similar x2) unless --mode laion. Exploratory; not a paper number.

Usage:
  backend/.venv/bin/python research/run_keymask_check.py \
    --items research/data/fsld/items_msclap_packonly_train.jsonl \
    --mode msclap --output artifacts/keymask-check
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ranking.weak_pairs import split_sources  # noqa: E402

from export_fusion_weights import FUSION_5SIG_IDX, NEG_TYPE_WEIGHTS, mask_key  # noqa: E402
from run_fusion import (  # noqa: E402
    PAIR_SEED,
    SEEDS,
    SIGNALS,
    build_feature_examples,
    compute_source_weights,
    evaluate,
    load_items,
    train_logistic,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--mode", required=True, choices=["laion", "msclap"])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    items = load_items(args.items)
    examples = build_feature_examples(items, seed=PAIR_SEED, aux={})
    masked = mask_key(examples)
    print(f"{len(items)} items, {len(examples)} examples, mode={args.mode}", flush=True)

    conditions = ["raw/key-present", "raw/key-zero", "masked/key-zero"]
    results = {c: [] for c in conditions}
    weights = {"raw": [], "masked": []}
    for seed in SEEDS:
        train_src, _ = split_sources([e["source_id"] for e in examples], seed=seed,
                                     val_fraction=0.25)
        train_set = set(train_src)
        train = [e for e in examples if e["source_id"] in train_set]
        val = [e for e in examples if e["source_id"] not in train_set]
        train_m = [e for e in masked if e["source_id"] in train_set]
        val_m = [e for e in masked if e["source_id"] not in train_set]
        sw = compute_source_weights(train) if args.mode == "msclap" else None
        ntw = NEG_TYPE_WEIGHTS if args.mode == "msclap" else None

        w_raw = train_logistic(train, FUSION_5SIG_IDX, seed, source_weights=sw,
                               neg_type_weights=ntw)
        w_masked = train_logistic(train_m, FUSION_5SIG_IDX, seed, source_weights=sw,
                                  neg_type_weights=ntw)
        weights["raw"].append(w_raw.tolist())
        weights["masked"].append(w_masked.tolist())
        evs = {
            "raw/key-present": evaluate(val, w_raw, FUSION_5SIG_IDX),
            "raw/key-zero": evaluate(val_m, w_raw, FUSION_5SIG_IDX),
            "masked/key-zero": evaluate(val_m, w_masked, FUSION_5SIG_IDX),
        }
        for name, ev in evs.items():
            results[name].append(ev)
        print(f"  seed {seed}: " + "  ".join(
            f"{n}={ev['overall']:.4f}/hs={ev['hard_similar']:.4f}" for n, ev in evs.items()),
            flush=True)
        print(f"    w_raw={np.array2string(w_raw, precision=3)} "
              f"w_masked={np.array2string(w_masked, precision=3)}", flush=True)

    neg_types = sorted({k for r in results[conditions[0]] for k in r if k != "overall"})
    summary = {}
    for name in conditions:
        entry = {}
        for key in ["overall", *neg_types]:
            vals = [r[key] for r in results[name]]
            entry[f"mean_{key}"] = round(statistics.mean(vals), 4)
            entry[f"std_{key}"] = round(statistics.stdev(vals), 4)
        summary[name] = entry
    for name in ("raw", "masked"):
        summary[f"mean_weights_{name}"] = [
            round(float(x), 4) for x in np.mean(weights[name], axis=0)
        ]
    delta = {
        key: round(summary["masked/key-zero"][f"mean_{key}"]
                   - summary["raw/key-zero"][f"mean_{key}"], 4)
        for key in ["overall", *neg_types]
    }
    cost = {
        key: round(summary["raw/key-zero"][f"mean_{key}"]
                   - summary["raw/key-present"][f"mean_{key}"], 4)
        for key in ["overall", *neg_types]
    }
    print("\n=== serving cost of key=0 with raw weights (raw/key-zero - raw/key-present, pp) ===")
    for key, value in cost.items():
        print(f"  {key:16s} {value * 100:+.2f}")
    print("=== recovered by masked training (masked/key-zero - raw/key-zero, pp) ===")
    for key, value in delta.items():
        print(f"  {key:16s} {value * 100:+.2f}")

    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"keymask_{args.mode}.json").write_text(json.dumps({
        "experiment": "train/serve key mismatch check for fusion-5sig (dev side)",
        "items_file": args.items,
        "mode": args.mode,
        "pair_seed": PAIR_SEED,
        "seeds": SEEDS,
        "signals": [SIGNALS[i] for i in FUSION_5SIG_IDX],
        "summary": summary,
        "serving_cost_of_key_zero_pp": {k: round(v * 100, 2) for k, v in cost.items()},
        "recovered_by_masked_training_pp": {k: round(v * 100, 2) for k, v in delta.items()},
        "per_seed": results,
        "note": "exploratory; the shipped weights and the paper's numbers use key present",
    }, indent=2))
    print(f"-> {out / f'keymask_{args.mode}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
