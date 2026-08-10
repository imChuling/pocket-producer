"""Leave-one-signal-out ablation over the FULL 7-signal fusion.

Answers the question the 5-signal ablation (run_ablation.py) cannot:
what is the measured marginal contribution of each session-structure
signal (role_gap, harmonic) inside the 7-signal fusion?

Reuses the exact feature builder, pair construction, seeds, and trainer
from run_fusion.py so results are directly comparable to
artifacts/fusion-7sig/fusion.json.

Produces artifacts/ablation-7sig/ablation.json:
  full-7sig + one minus-<signal> condition per signal,
  5-seed mean overall / per-negative-type accuracy and deltas.

Usage:
  python research/run_ablation_7sig.py \
    --items research/data/fsld/items_laion-clap-music.jsonl \
    --output artifacts/ablation-7sig
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.role_probe import CONFIDENCE_THRESHOLD, RoleProbe  # noqa: F401
from ranking.weak_pairs import split_sources

from run_fusion import (  # noqa: E402
    SEEDS,
    PAIR_SEED,
    SIGNALS,
    build_feature_examples,
    evaluate,
    load_items,
    train_logistic,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--chroma", default="research/data/fsld/chroma.jsonl")
    parser.add_argument("--role-prompts", default="research/data/fsld/role_prompts.json")
    parser.add_argument("--output", default="artifacts/ablation-7sig")
    args = parser.parse_args()

    items = load_items(args.items)
    print(f"Loaded {len(items)} items, dim={len(items[0]['embedding'])}", flush=True)

    aux = {}
    chroma_path = pathlib.Path(args.chroma)
    if chroma_path.exists():
        aux["chroma"] = {}
        for line in chroma_path.open():
            if line.strip():
                row = json.loads(line)
                aux["chroma"][row["item_id"]] = row["chroma"]
        print(f"  chroma for {len(aux['chroma'])} items", flush=True)
    else:
        sys.exit(f"ABORT: chroma required for 7-signal ablation ({chroma_path})")

    prompts_path = pathlib.Path(args.role_prompts)
    if prompts_path.exists():
        prompt_map = json.loads(prompts_path.read_text())
        probe = RoleProbe(np.array(list(prompt_map.values())))
        aux["roles"] = {
            item["item_id"]: probe.classify(item["embedding"]) for item in items
        }
        print("  roles classified", flush=True)
    else:
        sys.exit(f"ABORT: role prompts required for 7-signal ablation ({prompts_path})")

    print("Building 7-dim feature examples...", flush=True)
    examples = build_feature_examples(items, seed=PAIR_SEED, aux=aux)
    print(f"  {len(examples)} examples", flush=True)

    all_idx = list(range(len(SIGNALS)))
    conditions = {"full-7sig": all_idx}
    for i, sig in enumerate(SIGNALS):
        conditions[f"minus-{sig}"] = [j for j in all_idx if j != i]

    results = {name: [] for name in conditions}

    for seed in SEEDS:
        train_sources, val_sources = split_sources(
            [e["source_id"] for e in examples], seed=seed, val_fraction=0.25
        )
        train = [e for e in examples if e["source_id"] in set(train_sources)]
        val = [e for e in examples if e["source_id"] in set(val_sources)]
        print(f"\n--- Seed {seed} (train={len(train)}, val={len(val)}) ---", flush=True)

        for name, fidx in conditions.items():
            w = train_logistic(train, np.array(fidx), seed)
            ev = evaluate(val, w, np.array(fidx))
            results[name].append(ev)
            print(f"  {name:22s} overall={ev['overall']:.4f}  "
                  f"hard_sim={ev.get('hard_similar', float('nan')):.4f}", flush=True)

    summary = {}
    full_overall = statistics.mean(r["overall"] for r in results["full-7sig"])
    full_hs = statistics.mean(r["hard_similar"] for r in results["full-7sig"])
    for name in conditions:
        overalls = [r["overall"] for r in results[name]]
        hs = [r["hard_similar"] for r in results[name]]
        htk = [r["hard_tempo_key"] for r in results[name]]
        entry = {
            "overall_mean": round(statistics.mean(overalls), 4),
            "overall_std": round(statistics.stdev(overalls), 4),
            "hard_similar_mean": round(statistics.mean(hs), 4),
            "hard_tempo_key_mean": round(statistics.mean(htk), 4),
            "values_overall": overalls,
            "values_hard_similar": hs,
        }
        if name != "full-7sig":
            entry["delta_overall"] = round(statistics.mean(overalls) - full_overall, 4)
            entry["delta_hard_similar"] = round(statistics.mean(hs) - full_hs, 4)
        summary[name] = entry

    print("\n=== 7-signal LOSO summary (5 seeds) ===\n", flush=True)
    print(f"{'condition':24s} {'overall':>8s} {'hard_sim':>9s} "
          f"{'d_overall':>10s} {'d_hardsim':>10s}")
    for name, e in summary.items():
        d_o = e.get("delta_overall", 0.0)
        d_h = e.get("delta_hard_similar", 0.0)
        print(f"{name:24s} {e['overall_mean']:8.4f} {e['hard_similar_mean']:9.4f} "
              f"{d_o:+10.4f} {d_h:+10.4f}")

    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": "7-signal leave-one-signal-out ablation",
        "items_file": str(args.items),
        "pair_seed": PAIR_SEED,
        "seeds": SEEDS,
        "signals": SIGNALS,
        "ablation": summary,
        "note": ("Deltas are (minus-X mean) - (full-7sig mean) over the same "
                 "5 source-grouped splits; negative delta = removing X hurts."),
    }
    (out / "ablation.json").write_text(json.dumps(payload, indent=2))
    print(f"\n-> {out / 'ablation.json'}", flush=True)


if __name__ == "__main__":
    main()
