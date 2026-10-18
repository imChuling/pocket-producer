"""Sample 40 pairs for the human listening evaluation.

Protocol: prereg_human_v1.md
Frozen before first data collection session.

Strata (all drawn from hard_similar pairs):
  1. Disagreement pairs (fusion vs cosine disagree on the winner)
  2. Non-disagreement hard_similar pairs to fill up to 40 total

Scoring uses the 5-seed mean fusion weights from the held-out
correction experiment, computed once and applied uniformly.

Output: research/data/listening_test/pairs.json

Usage:
  python research/sample_listening_pairs.py
"""

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.baselines import OFFLINE_STANDIN_WEIGHTS
from ranking.weak_pairs import build_weak_pairs

from run_fusion import PAIR_SEED, SIGNALS, candidate_signals, load_items

ROOT = pathlib.Path(__file__).resolve().parent.parent
ITEMS_PATH = ROOT / "research" / "data" / "fsld" / "items_laion-clap-music_packonly.jsonl"
SPLIT_PATH = ROOT / "artifacts" / "heldout-split-packonly" / "split.json"
WEIGHTS_PATH = ROOT / "artifacts" / "heldout-eval-correction" / "sensitivity.json"
OUT_DIR = ROOT / "research" / "data" / "listening_test"

SAMPLE_SEED = 20261017
TARGET_PAIRS = 40

FUSION_5SIG_IDX = np.array([0, 1, 2, 3, 4])

_STANDIN_SIGNAL = {"tempo_match": "tempo", "key_match": "key", "tag_overlap": "tag_jaccard"}


def _rules_indices_and_weights():
    names = list(OFFLINE_STANDIN_WEIGHTS)
    idx = np.array([SIGNALS.index(_STANDIN_SIGNAL[n]) for n in names])
    w = np.array([OFFLINE_STANDIN_WEIGHTS[n] for n in names])
    return idx, w / w.sum()


def _pick_label(score_pos: float, score_neg: float) -> str:
    return "positive" if score_pos > score_neg else "negative"


def main():
    items = load_items(str(ITEMS_PATH))
    split = json.load(SPLIT_PATH.open())
    heldout_ids = set(split["heldout_source_ids"])
    heldout = [i for i in items if i["source_id"] in heldout_ids]

    id_lookup = {id(item["embedding"]): item for item in heldout}
    pairs = build_weak_pairs(heldout, seed=PAIR_SEED)

    sens = json.load(WEIGHTS_PATH.open())
    per_seed = [np.array(sw["fusion-5sig"]) for sw in sens["per_seed_weights"]]
    mean_weights = np.mean(per_seed, axis=0)
    print(f"Using 5-seed mean weights: {mean_weights.tolist()}")

    rules_idx, rules_w = _rules_indices_and_weights()

    scored_pairs = []
    for pi, p in enumerate(pairs):
        for ni, nt in enumerate(p["negative_types"]):
            if nt != "hard_similar":
                continue

            ctx_items = [id_lookup[id(e)] for e in p["context_embeddings"]]
            pos_item = id_lookup[id(p["positive_embedding"])]
            neg_item = id_lookup[id(p["negative_embeddings"][ni])]

            aux = {}
            pos_feat = candidate_signals(ctx_items, pos_item, aux)
            neg_feat = candidate_signals(ctx_items, neg_item, aux)

            f_pos = float(mean_weights @ pos_feat[FUSION_5SIG_IDX])
            f_neg = float(mean_weights @ neg_feat[FUSION_5SIG_IDX])
            c_pos = float(pos_feat[0])
            c_neg = float(neg_feat[0])
            r_pos = float(rules_w @ pos_feat[rules_idx])
            r_neg = float(rules_w @ neg_feat[rules_idx])

            fusion_pick = _pick_label(f_pos, f_neg)
            cosine_pick = _pick_label(c_pos, c_neg)
            rules_pick = _pick_label(r_pos, r_neg)
            is_disagreement = (fusion_pick != cosine_pick)

            margin_diff = abs((f_pos - f_neg) - (c_pos - c_neg))

            scored_pairs.append({
                "pair_index": pi,
                "neg_index": ni,
                "source_id": p["source_id"],
                "is_disagreement": is_disagreement,
                "margin_diff": margin_diff,
                "fusion_pick": fusion_pick,
                "cosine_pick": cosine_pick,
                "rules_pick": rules_pick,
                "fusion_margin": float(f_pos - f_neg),
                "cosine_margin": float(c_pos - c_neg),
                "rules_margin": float(r_pos - r_neg),
                "ctx_items": ctx_items,
                "pos_item": pos_item,
                "neg_item": neg_item,
            })

    disagree_pool = [sp for sp in scored_pairs if sp["is_disagreement"]]
    agree_pool = [sp for sp in scored_pairs if not sp["is_disagreement"]]
    print(f"Hard_similar pairs: {len(scored_pairs)} total, "
          f"{len(disagree_pool)} disagreement, {len(agree_pool)} agreement")

    disagree_pool.sort(key=lambda x: -x["margin_diff"])
    agree_pool.sort(key=lambda x: -x["margin_diff"])

    selected = []
    used_sources = set()

    # Stratum 1: disagreement pairs, sorted by |margin diff| descending
    for cand in disagree_pool:
        if len(selected) >= TARGET_PAIRS:
            break
        if cand["source_id"] in used_sources and len(disagree_pool) - len(selected) > 5:
            continue
        selected.append((cand, "disagreement"))
        used_sources.add(cand["source_id"])

    n_stratum1 = len(selected)
    print(f"Stratum 1 (disagreement): {n_stratum1}")

    # Stratum 2: non-disagreement hard_similar pairs to fill remaining
    remaining = TARGET_PAIRS - n_stratum1
    print(f"Stratum 2: need {remaining} hard_similar (agreement) pairs")

    stratum2_count = 0
    for cand in agree_pool:
        if stratum2_count >= remaining:
            break
        if cand["source_id"] in used_sources and stratum2_count < remaining - 5:
            continue
        selected.append((cand, "hard_similar"))
        used_sources.add(cand["source_id"])
        stratum2_count += 1

    if stratum2_count < remaining:
        for cand in agree_pool:
            if stratum2_count >= remaining:
                break
            if not any(s[0] is cand for s in selected):
                selected.append((cand, "hard_similar"))
                stratum2_count += 1

    print(f"Stratum 2 (hard_similar): {stratum2_count}")
    print(f"Total pairs: {len(selected)}")

    output_pairs = []
    all_item_ids = set()
    for idx, (cand, stratum) in enumerate(selected):
        pair_id = f"{'d' if stratum == 'disagreement' else 'h'}{idx:03d}"
        entry = {
            "pair_id": pair_id,
            "stratum": stratum,
            "source_id": cand["source_id"],
            "neg_type": "hard_similar",
            "context_ids": [c["item_id"] for c in cand["ctx_items"]],
            "positive_id": cand["pos_item"]["item_id"],
            "negative_id": cand["neg_item"]["item_id"],
            "fusion_pick": cand["fusion_pick"],
            "cosine_pick": cand["cosine_pick"],
            "rules_pick": cand["rules_pick"],
            "fusion_margin": cand["fusion_margin"],
            "cosine_margin": cand["cosine_margin"],
            "rules_margin": cand["rules_margin"],
        }
        output_pairs.append(entry)
        all_item_ids.update(entry["context_ids"])
        all_item_ids.add(entry["positive_id"])
        all_item_ids.add(entry["negative_id"])

    n_disagree = sum(1 for p in output_pairs if p["stratum"] == "disagreement")
    n_hs = sum(1 for p in output_pairs if p["stratum"] == "hard_similar")
    n_sources = len({p["source_id"] for p in output_pairs})
    print(f"\nBy stratum: disagreement={n_disagree}, hard_similar={n_hs}")
    print(f"Distinct sources: {n_sources}")
    print(f"Unique items (need audio): {len(all_item_ids)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "protocol": "research/prereg_human_v1.md",
        "sample_seed": SAMPLE_SEED,
        "pair_seed": PAIR_SEED,
        "fusion_weights": mean_weights.tolist(),
        "fusion_weight_source": "5-seed mean from heldout-eval-correction",
        "rules_weights": {k: float(v) for k, v in OFFLINE_STANDIN_WEIGHTS.items()},
        "n_pairs": len(output_pairs),
        "n_stratum1_disagreement": n_disagree,
        "n_stratum2_hard_similar": n_hs,
        "n_unique_items": len(all_item_ids),
        "n_distinct_sources": n_sources,
        "pairs": output_pairs,
        "item_ids": sorted(all_item_ids),
    }
    out_path = OUT_DIR / "pairs.json"
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
