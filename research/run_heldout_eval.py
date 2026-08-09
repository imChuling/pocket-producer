"""Held-out dual-track evaluation (protocol-heldout-v1).

Track 1: retrain 5-signal fusion on the 759-source TRAIN split, evaluate
pairwise accuracy on the 190-source HELD-OUT split.  Negative pools for
pair construction are restricted to items within each split — no leakage.

Track 2 prep: identify disagreement pairs (fusion correct + cosine wrong,
or vice versa) on hard_similar negatives from the held-out evaluation.
These pairs feed the human A/B study.

Usage:
  python research/run_heldout_eval.py \
    --items research/data/fsld/items_laion-clap-music.jsonl \
    --split artifacts/heldout-split/split.json \
    --output artifacts/heldout-eval
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
    SEEDS,
    PAIR_SEED,
    SIGNALS,
    build_feature_examples,
    candidate_signals,
    evaluate,
    load_items,
    train_logistic,
)

FUSION_5SIG_IDX = [0, 1, 2, 3, 4]  # audio_cos_mean, audio_cos_max, tempo, key, tag_jaccard
COSINE_IDX = [0]                     # audio_cos_mean only


def load_aux(items, chroma_path, role_prompts_path):
    aux = {}
    chroma_path = pathlib.Path(chroma_path)
    if chroma_path.exists():
        aux["chroma"] = {}
        for line in chroma_path.open():
            if line.strip():
                row = json.loads(line)
                aux["chroma"][row["item_id"]] = row["chroma"]
        print(f"  chroma for {len(aux['chroma'])} items", flush=True)
    else:
        print(f"  WARNING: no chroma at {chroma_path}; harmonic signal = 0", flush=True)

    prompts_path = pathlib.Path(role_prompts_path)
    if prompts_path.exists():
        from ranking.role_probe import CONFIDENCE_THRESHOLD, RoleProbe
        prompt_map = json.loads(prompts_path.read_text())
        probe = RoleProbe(np.array(list(prompt_map.values())))
        aux["roles"] = {
            item["item_id"]: probe.classify(item["embedding"]) for item in items
        }
        print(f"  roles classified", flush=True)
    else:
        print(f"  WARNING: no role prompts at {prompts_path}; role_gap = 0", flush=True)

    return aux


def find_disagreement_pairs(heldout_examples, w_fusion, w_cosine):
    """Find hard_similar pairs where fusion and cosine disagree."""
    fusion_idx = np.array(FUSION_5SIG_IDX)
    cosine_idx = np.array(COSINE_IDX)

    disagreements = []
    concordant_margins = []

    for ex in heldout_examples:
        hs_indices = [i for i, t in enumerate(ex["neg_types"]) if t == "hard_similar"]
        if not hs_indices:
            continue

        for ni in hs_indices:
            sp_f = w_fusion @ ex["pos"][fusion_idx]
            sn_f = w_fusion @ ex["negs"][ni][fusion_idx]
            fusion_correct = sp_f > sn_f

            sp_c = w_cosine @ ex["pos"][cosine_idx]
            sn_c = w_cosine @ ex["negs"][ni][cosine_idx]
            cosine_correct = sp_c > sn_c

            record = {
                "example_id": ex.get("example_id", ex["source_id"]),
                "source_id": ex["source_id"],
                "neg_index": ni,
                "fusion_correct": bool(fusion_correct),
                "cosine_correct": bool(cosine_correct),
                "fusion_margin": float(sp_f - sn_f),
                "cosine_margin": float(sp_c - sn_c),
            }

            if fusion_correct != cosine_correct:
                disagreements.append(record)
            else:
                concordant_margins.append(record)

    concordant_margins.sort(key=lambda r: abs(r["fusion_margin"]))
    return disagreements, concordant_margins


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--split", default="artifacts/heldout-split/split.json")
    parser.add_argument("--chroma", default="research/data/fsld/chroma.jsonl")
    parser.add_argument("--role-prompts", default="research/data/fsld/role_prompts.json")
    parser.add_argument("--output", default="artifacts/heldout-eval")
    args = parser.parse_args()

    with open(args.split) as f:
        split_data = json.load(f)
    heldout_ids = set(split_data["heldout_source_ids"])
    print(f"Split: {split_data['n_train_sources']} train, "
          f"{split_data['n_heldout_sources']} held-out sources", flush=True)

    all_items = load_items(args.items)
    train_items = [i for i in all_items if i["source_id"] not in heldout_ids]
    heldout_items = [i for i in all_items if i["source_id"] in heldout_ids]
    print(f"Items: {len(train_items)} train, {len(heldout_items)} held-out", flush=True)

    aux_all = load_aux(all_items, args.chroma, args.role_prompts)
    # aux is keyed by item_id, works for both splits

    print("\nBuilding train feature examples...", flush=True)
    train_examples = build_feature_examples(train_items, seed=PAIR_SEED, aux=aux_all)
    print(f"  {len(train_examples)} train examples", flush=True)

    print("Building held-out feature examples...", flush=True)
    heldout_examples = build_feature_examples(heldout_items, seed=PAIR_SEED, aux=aux_all)
    print(f"  {len(heldout_examples)} held-out examples", flush=True)

    # -- Track 1: train on train, evaluate on held-out --
    print("\n" + "=" * 60)
    print("TRACK 1: Offline held-out weak-label evaluation")
    print("=" * 60)

    conditions = {
        "cosine-only": COSINE_IDX,
        "fusion-5sig": FUSION_5SIG_IDX,
    }

    results = {name: [] for name in conditions}
    per_seed_weights = []

    for seed in SEEDS:
        # Internal train/val split WITHIN train sources for early stopping
        # (protocol: same source-grouped splits within train only)
        train_source_ids = [e["source_id"] for e in train_examples]
        int_train_src, int_val_src = split_sources(
            train_source_ids, seed=seed, val_fraction=0.25
        )
        int_train = [e for e in train_examples if e["source_id"] in set(int_train_src)]
        int_val = [e for e in train_examples if e["source_id"] in set(int_val_src)]
        print(f"\n--- Seed {seed} (int_train={len(int_train)}, int_val={len(int_val)}) ---",
              flush=True)

        seed_weights = {"seed": seed}
        for name, fidx in conditions.items():
            fidx_arr = np.array(fidx)
            if name == "cosine-only":
                w = np.ones(1)
            else:
                w = train_logistic(int_train, fidx_arr, seed)

            # Evaluate on HELD-OUT (never seen during training or val split selection)
            ev_heldout = evaluate(heldout_examples, w, fidx_arr)
            results[name].append(ev_heldout)

            # Also evaluate on internal val for comparison
            ev_intval = evaluate(int_val, w, fidx_arr)

            seed_weights[name] = w.tolist()
            print(f"  {name:15s} held-out={ev_heldout['overall']:.4f} "
                  f"(hs={ev_heldout.get('hard_similar', float('nan')):.4f})  "
                  f"int-val={ev_intval['overall']:.4f}", flush=True)

        per_seed_weights.append(seed_weights)

    # Summary
    print("\n=== TRACK 1 SUMMARY (held-out, 5 seeds) ===\n", flush=True)
    summary = {}
    neg_types = sorted({k for r in results["fusion-5sig"] for k in r if k != "overall"})

    for name in conditions:
        overalls = [r["overall"] for r in results[name]]
        entry = {
            "mean_overall": round(statistics.mean(overalls), 4),
            "std_overall": round(statistics.stdev(overalls), 4),
            "values_overall": overalls,
        }
        for nt in neg_types:
            vals = [r.get(nt, float("nan")) for r in results[name]]
            entry[f"mean_{nt}"] = round(statistics.mean(vals), 4)
            entry[f"values_{nt}"] = vals
        summary[name] = entry
        print(f"  {name:15s} overall={entry['mean_overall']:.4f}±{entry['std_overall']:.4f}  "
              + "  ".join(f"{nt}={entry[f'mean_{nt}']:.4f}" for nt in neg_types), flush=True)

    # Delta
    cosine_hs = summary["cosine-only"].get("mean_hard_similar", 0)
    fusion_hs = summary["fusion-5sig"].get("mean_hard_similar", 0)
    delta_hs = round(fusion_hs - cosine_hs, 4)
    cosine_overall = summary["cosine-only"]["mean_overall"]
    fusion_overall = summary["fusion-5sig"]["mean_overall"]
    delta_overall = round(fusion_overall - cosine_overall, 4)

    print(f"\n  Fusion - Cosine: overall={delta_overall:+.4f}, "
          f"hard_similar={delta_hs:+.4f}", flush=True)

    # Per-seed sign check
    n_positive_hs = sum(
        1 for f, c in zip(results["fusion-5sig"], results["cosine-only"])
        if f.get("hard_similar", 0) > c.get("hard_similar", 0)
    )
    print(f"  Seeds where fusion > cosine on hard_similar: {n_positive_hs}/5", flush=True)

    # -- Track 2 prep: disagreement pairs --
    print("\n" + "=" * 60)
    print("TRACK 2 PREP: Disagreement pair identification")
    print("=" * 60)

    # Use the median-performing seed's weights for disagreement selection
    hs_by_seed = [(i, results["fusion-5sig"][i].get("hard_similar", 0)) for i in range(5)]
    hs_by_seed.sort(key=lambda x: x[1])
    median_idx = hs_by_seed[2][0]  # middle seed
    median_seed = SEEDS[median_idx]
    w_fusion_median = np.array(per_seed_weights[median_idx]["fusion-5sig"])
    w_cosine = np.ones(1)

    print(f"\nUsing median seed {median_seed} for disagreement selection", flush=True)

    disagreements, concordant = find_disagreement_pairs(
        heldout_examples, w_fusion_median, w_cosine
    )

    n_fusion_right = sum(1 for d in disagreements if d["fusion_correct"])
    n_cosine_right = sum(1 for d in disagreements if d["cosine_correct"])
    print(f"  Disagreement pairs: {len(disagreements)}", flush=True)
    print(f"    Fusion correct: {n_fusion_right}", flush=True)
    print(f"    Cosine correct: {n_cosine_right}", flush=True)
    print(f"  Concordant pairs: {len(concordant)}", flush=True)

    # If fewer than 20 disagreements, supplement with closest-margin concordant
    supplement = []
    if len(disagreements) < 20:
        n_supplement = min(40 - len(disagreements), len(concordant))
        supplement = concordant[:n_supplement]
        print(f"  Supplementing with {n_supplement} closest-margin concordant pairs",
              flush=True)

    # -- Save results --
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    report = {
        "experiment": "held-out dual-track evaluation (protocol-heldout-v1)",
        "protocol": "research/protocol-heldout-v1.md",
        "split_file": args.split,
        "split_sha256": split_data["sha256_heldout_ids"],
        "items_file": str(args.items),
        "pair_seed": PAIR_SEED,
        "seeds": SEEDS,
        "signals_used": [SIGNALS[i] for i in FUSION_5SIG_IDX],
        "train_sources": split_data["n_train_sources"],
        "heldout_sources": split_data["n_heldout_sources"],
        "train_examples": len(train_examples),
        "heldout_examples": len(heldout_examples),
        "track1_summary": summary,
        "track1_delta": {
            "overall": delta_overall,
            "hard_similar": delta_hs,
            "n_positive_seeds_hs": n_positive_hs,
        },
        "track2_prep": {
            "median_seed": median_seed,
            "median_seed_idx": median_idx,
            "n_disagreement_pairs": len(disagreements),
            "n_fusion_correct": n_fusion_right,
            "n_cosine_correct": n_cosine_right,
            "n_concordant": len(concordant),
            "n_supplement": len(supplement),
        },
    }

    (out / "eval.json").write_text(json.dumps(report, indent=2))
    print(f"\n-> {out / 'eval.json'}", flush=True)

    # Save disagreement pairs for Track 2
    track2_pairs = {
        "median_seed": median_seed,
        "fusion_weights": w_fusion_median.tolist(),
        "disagreement_pairs": disagreements,
        "supplement_concordant": supplement,
    }
    (out / "track2_pairs.json").write_text(json.dumps(track2_pairs, indent=2))
    print(f"-> {out / 'track2_pairs.json'}", flush=True)

    # Save per-seed weights
    (out / "weights.json").write_text(json.dumps(per_seed_weights, indent=2))
    print(f"-> {out / 'weights.json'}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
