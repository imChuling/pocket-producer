"""2x2 factorial: representation (LAION vs MS-CLAP) x training (uniform vs source-weighted BPR).

Runs on the 484 train sources only (dev-set 5-fold CV). Does NOT touch
the 121 held-out sources.

Protocol: research/protocol-factorial-v1.md

Usage:
  backend/.venv/bin/python research/run_factorial.py \
    --laion research/data/fsld/items_laion-clap-music_packonly_train.jsonl \
    --msclap research/data/fsld/items_msclap_packonly_train.jsonl \
    --output artifacts/factorial
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from run_fusion import (
    PAIR_SEED,
    SEEDS,
    build_feature_examples,
    compute_source_weights,
    evaluate,
    load_items,
    train_logistic,
)
from ranking.weak_pairs import split_sources

FUSION_5SIG_IDX = np.array([0, 1, 2, 3, 4])
SIGNAL_NAMES = ["audio_cos_mean", "audio_cos_max", "tempo", "key", "tag_jaccard"]
RULES_WEIGHTS = np.array([0.353, 0.235, 0.412])
RULES_IDX = np.array([2, 3, 4])


def run_condition(items, condition_name, use_source_weighting, seeds, pair_seed):
    """Run 5-fold CV for one condition, return per-seed val results."""
    examples = build_feature_examples(items, seed=pair_seed, aux={})
    print(f"\n{'='*60}")
    print(f"  Condition: {condition_name}")
    print(f"  {len(examples)} examples, source_weighting={use_source_weighting}")
    print(f"{'='*60}")

    sw = compute_source_weights(examples) if use_source_weighting else None
    ntw = {"hard_similar": 2.0} if use_source_weighting else None

    all_results = {"rules": [], "cosine": [], "fusion": []}
    all_weights = []

    for seed in seeds:
        train_sources, val_sources = split_sources(
            [e["source_id"] for e in examples], seed=seed, val_fraction=0.25
        )
        train_set = set(train_sources)
        train = [e for e in examples if e["source_id"] in train_set]
        val = [e for e in examples if e["source_id"] not in train_set]

        # Rules baseline (no training)
        ev_rules = evaluate(val, RULES_WEIGHTS, RULES_IDX)
        all_results["rules"].append(ev_rules)

        # Cosine baseline (no training)
        ev_cos = evaluate(val, np.ones(1), np.array([0]))
        all_results["cosine"].append(ev_cos)

        # Fusion-5sig
        w = train_logistic(train, FUSION_5SIG_IDX, seed,
                           source_weights=sw, neg_type_weights=ntw)
        ev_fus = evaluate(val, w, FUSION_5SIG_IDX)
        all_results["fusion"].append(ev_fus)
        all_weights.append(w)

        print(f"  seed {seed}: cos={ev_cos['overall']:.4f} "
              f"fus={ev_fus['overall']:.4f} "
              f"hs_cos={ev_cos.get('hard_similar', 0):.3f} "
              f"hs_fus={ev_fus.get('hard_similar', 0):.3f} "
              f"w={np.array2string(w, precision=3)}")

    return all_results, all_weights


def summarize(results):
    """Compute mean/std over seeds for each regime."""
    summary = {}
    for method, seed_results in results.items():
        neg_types = sorted({k for r in seed_results for k in r})
        method_summary = {}
        for nt in neg_types:
            vals = [r[nt] for r in seed_results if nt in r]
            method_summary[nt] = {
                "mean": round(statistics.mean(vals), 4),
                "std": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
                "values": vals,
            }
        summary[method] = method_summary
    return summary


def compute_deltas(summary):
    """Fusion-cosine deltas per regime."""
    deltas = {}
    for nt in summary["fusion"]:
        fus_mean = summary["fusion"][nt]["mean"]
        cos_mean = summary["cosine"][nt]["mean"]
        deltas[nt] = round((fus_mean - cos_mean) * 100, 2)
    return deltas


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--laion", required=True)
    parser.add_argument("--msclap", required=True)
    parser.add_argument("--output", default="artifacts/factorial")
    args = parser.parse_args()

    laion_items = load_items(args.laion)
    msclap_items = load_items(args.msclap)
    print(f"LAION items: {len(laion_items)}, dim={len(laion_items[0]['embedding'])}")
    print(f"MS-CLAP items: {len(msclap_items)}, dim={len(msclap_items[0]['embedding'])}")

    conditions = {
        "A_laion_uniform": (laion_items, False),
        "B_laion_sourceweighted": (laion_items, True),
        "C_msclap_uniform": (msclap_items, False),
        "D_msclap_sourceweighted": (msclap_items, True),
    }

    all_summaries = {}
    all_deltas = {}
    all_mean_weights = {}

    for name, (items, use_sw) in conditions.items():
        results, weights = run_condition(items, name, use_sw, SEEDS, PAIR_SEED)
        summary = summarize(results)
        deltas = compute_deltas(summary)
        mean_w = np.mean(weights, axis=0)

        all_summaries[name] = summary
        all_deltas[name] = deltas
        all_mean_weights[name] = [round(float(x), 4) for x in mean_w]

    # Main effects and interaction on hard_similar
    print("\n" + "=" * 60)
    print("  FACTORIAL ANALYSIS")
    print("=" * 60)

    regimes = ["overall", "hard_similar", "hard_tempo_key"]
    effects = {}

    for regime in regimes:
        a = all_summaries["A_laion_uniform"]["fusion"][regime]["mean"]
        b = all_summaries["B_laion_sourceweighted"]["fusion"][regime]["mean"]
        c = all_summaries["C_msclap_uniform"]["fusion"][regime]["mean"]
        d = all_summaries["D_msclap_sourceweighted"]["fusion"][regime]["mean"]

        repr_effect = ((c + d) / 2 - (a + b) / 2) * 100
        train_effect = ((b + d) / 2 - (a + c) / 2) * 100
        interaction = (d - c - b + a) * 100

        effects[regime] = {
            "A_laion_uniform": round(a, 4),
            "B_laion_sourceweighted": round(b, 4),
            "C_msclap_uniform": round(c, 4),
            "D_msclap_sourceweighted": round(d, 4),
            "representation_effect_pp": round(repr_effect, 2),
            "training_effect_pp": round(train_effect, 2),
            "interaction_pp": round(interaction, 2),
        }

        print(f"\n  {regime}:")
        print(f"    A (LAION+uniform):    {a:.4f}")
        print(f"    B (LAION+sw):         {b:.4f}")
        print(f"    C (MSCLAP+uniform):   {c:.4f}")
        print(f"    D (MSCLAP+sw):        {d:.4f}")
        print(f"    Representation:       {repr_effect:+.2f} pp")
        print(f"    Training:             {train_effect:+.2f} pp")
        print(f"    Interaction:          {interaction:+.2f} pp")

    # Also show fusion-cosine deltas
    print("\n  Fusion-cosine deltas (pp):")
    for regime in regimes:
        row = "    "
        for name in conditions:
            row += f"{name}: {all_deltas[name].get(regime, '?'):+.2f}  "
        print(row)

    # Save
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment": "2x2 factorial: representation x training",
        "protocol": "research/protocol-factorial-v1.md",
        "status": "dev-set analysis, no held-out sources touched",
        "laion_items": args.laion,
        "msclap_items": args.msclap,
        "pair_seed": PAIR_SEED,
        "seeds": SEEDS,
        "conditions": {
            "A_laion_uniform": {"embedding": "laion-clap-music", "training": "uniform_bpr"},
            "B_laion_sourceweighted": {"embedding": "laion-clap-music", "training": "source_weighted_bpr_hs2.0"},
            "C_msclap_uniform": {"embedding": "msclap-2023", "training": "uniform_bpr"},
            "D_msclap_sourceweighted": {"embedding": "msclap-2023", "training": "source_weighted_bpr_hs2.0"},
        },
        "baselines": {
            "rules": {"signals": ["tempo", "key", "tag_jaccard"], "weights": [0.353, 0.235, 0.412]},
            "cosine": {"signals": ["audio_cos_mean"], "weights": [1.0]},
        },
        "summaries": all_summaries,
        "fusion_cosine_deltas_pp": all_deltas,
        "mean_weights": all_mean_weights,
        "factorial_effects": effects,
    }
    out_path = out / "factorial.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
