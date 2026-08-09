"""Leave-one-signal-out ablation, error analysis, and bootstrap CIs.

Produces artifacts/ablation/ablation.json with:
  1. Ablation table: full-fusion vs each leave-one-out condition
  2. Error analysis: examples where fusion wins but cosine loses (and vice versa)
  3. Bootstrap 95% CIs on per-negative-type accuracy

Usage:
  python research/run_ablation.py \
    --items research/data/fsld/items_laion-clap-music.jsonl \
    --output artifacts/ablation
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.features import key_match, tempo_match
from ranking.harmonic_probe import session_chroma, transpose_invariant_score
from ranking.role_probe import CONFIDENCE_THRESHOLD, RoleProbe
from ranking.weak_pairs import build_weak_pairs, split_sources

SEEDS = [20260725, 20260801, 20260802, 20260803, 20260804]
PAIR_SEED = 20260725
SIGNALS = ["audio_cos_mean", "audio_cos_max", "tempo", "key", "tag_jaccard"]
BOOTSTRAP_SEEDS = list(range(2000))


def load_items(path):
    items = []
    for line in pathlib.Path(path).open():
        if not line.strip():
            continue
        row = json.loads(line)
        items.append({
            "item_id": row["item_id"],
            "source_id": row["source_id"],
            "embedding": row["embedding"],
            "bpm": row.get("bpm"),
            "key": row.get("key"),
            "tags": row.get("tags") or [],
            "duration_seconds": row.get("duration_seconds") or 0.0,
        })
    return items


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / (np.linalg.norm(v) + 1e-9)


def candidate_signals(context_items, candidate, aux):
    ctx_vecs = np.stack([_unit(i["embedding"]) for i in context_items])
    mean_ctx = _unit(ctx_vecs.mean(axis=0))
    cand_vec = _unit(candidate["embedding"])

    bpms = [i["bpm"] for i in context_items if i.get("bpm")]
    ctx_bpm = float(np.mean(bpms)) if bpms else None
    ctx_keys = [i["key"] for i in context_items if i.get("key")]

    ctx_tags = set()
    for i in context_items:
        ctx_tags.update(t.lower() for t in i.get("tags") or [])
    cand_tags = {t.lower() for t in candidate.get("tags") or []}
    union = ctx_tags | cand_tags
    jaccard = len(ctx_tags & cand_tags) / len(union) if union else 0.0

    return np.array([
        float(mean_ctx @ cand_vec),
        float((ctx_vecs @ cand_vec).max()),
        tempo_match(ctx_bpm, candidate.get("bpm")),
        max((key_match(k, candidate.get("key")) for k in ctx_keys), default=0.0),
        jaccard,
    ])


def build_feature_examples(items, seed, aux):
    lookup = {id(item["embedding"]): item for item in items}
    pairs = build_weak_pairs(items, seed=seed)
    examples = []
    for ex in pairs:
        context_items = [lookup[id(e)] for e in ex["context_embeddings"]]
        positive = lookup[id(ex["positive_embedding"])]
        negatives = [lookup[id(e)] for e in ex["negative_embeddings"]]
        examples.append({
            "source_id": ex["source_id"],
            "pos": candidate_signals(context_items, positive, aux),
            "negs": [candidate_signals(context_items, n, aux) for n in negatives],
            "neg_types": ex["negative_types"],
            "pos_item": positive["item_id"],
            "neg_items": [n["item_id"] for n in negatives],
            "ctx_items": [c["item_id"] for c in context_items],
        })
    return examples


def train_logistic(train, feature_idx, seed, epochs=300, lr=0.05):
    rng = np.random.default_rng(seed)
    dim = len(feature_idx)
    w = np.zeros(dim)
    m_w = np.zeros(dim); v_w = np.zeros(dim)
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    t = 0
    for _ in range(epochs):
        order = rng.permutation(len(train))
        for idx in order:
            ex = train[int(idx)]
            fp = ex["pos"][feature_idx]
            for neg in ex["negs"]:
                fn = neg[feature_idx]
                diff = fp - fn
                z = w @ diff
                sig = 1.0 / (1.0 + np.exp(-z))
                grad = -(1.0 - sig) * diff
                t += 1
                m_w = beta1 * m_w + (1 - beta1) * grad
                v_w = beta2 * v_w + (1 - beta2) * grad**2
                m_hat = m_w / (1 - beta1**t)
                v_hat = v_w / (1 - beta2**t)
                w -= lr * m_hat / (np.sqrt(v_hat) + eps)
    return w


def evaluate_detailed(examples, w, feature_idx):
    """Returns per-pair results for error analysis."""
    pairs = []
    for ex in examples:
        sp = w @ ex["pos"][feature_idx]
        for j, (neg, ntype) in enumerate(zip(ex["negs"], ex["neg_types"])):
            sn = w @ neg[feature_idx]
            win = 1.0 if sp > sn else (0.5 if sp == sn else 0.0)
            pairs.append({
                "win": win,
                "neg_type": ntype,
                "score_pos": float(sp),
                "score_neg": float(sn),
                "margin": float(sp - sn),
                "source_id": ex["source_id"],
                "pos_item": ex["pos_item"],
                "neg_item": ex["neg_items"][j],
                "ctx_items": ex["ctx_items"],
                "pos_signals": ex["pos"][feature_idx].tolist(),
                "neg_signals": neg[feature_idx].tolist(),
            })
    return pairs


def aggregate(pairs):
    overall_wins = sum(p["win"] for p in pairs)
    by_type = {}
    for p in pairs:
        bucket = by_type.setdefault(p["neg_type"], [0.0, 0])
        bucket[0] += p["win"]
        bucket[1] += 1
    result = {"overall": round(overall_wins / len(pairs), 4)}
    for ntype, (wins, total) in sorted(by_type.items()):
        result[ntype] = round(wins / total, 4)
    return result


def _grouped_boot(values_by_source, n_boot, alpha):
    """Source-grouped bootstrap of a mean: resample SOURCES with replacement.

    Pairs within a source are correlated (shared context and positives),
    so the source is the exchangeable unit, not the pair.
    """
    sources = sorted(values_by_source)
    sums = np.array([sum(values_by_source[s]) for s in sources])
    counts = np.array([len(values_by_source[s]) for s in sources])
    n = len(sources)

    boot_means = []
    for seed in BOOTSTRAP_SEEDS[:n_boot]:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, n, size=n)
        total = counts[idx].sum()
        if total == 0:
            continue
        boot_means.append(float(sums[idx].sum() / total))
    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return float(sums.sum() / counts.sum()), lo, hi, n


def bootstrap_ci(pairs, n_boot=2000, alpha=0.05):
    """Source-grouped bootstrap per neg_type (and overall)."""
    grouped = {}
    for p in pairs:
        grouped.setdefault(p["neg_type"], {}).setdefault(p["source_id"], []).append(
            p["win"]
        )
        grouped.setdefault("overall", {}).setdefault(p["source_id"], []).append(
            p["win"]
        )

    cis = {}
    for ntype, by_source in sorted(grouped.items()):
        mean, lo, hi, n_src = _grouped_boot(by_source, n_boot, alpha)
        cis[ntype] = {
            "mean": round(mean, 4),
            "ci_lo": round(lo, 4),
            "ci_hi": round(hi, 4),
            "n_sources": n_src,
        }
    return cis


def bootstrap_paired_diff_ci(pairs_a, pairs_b, n_boot=2000, alpha=0.05):
    """Source-grouped bootstrap CI on the paired per-pair difference (a - b)."""
    grouped = {}
    for pa, pb in zip(pairs_a, pairs_b):
        d = pa["win"] - pb["win"]
        grouped.setdefault(pa["neg_type"], {}).setdefault(
            pa["source_id"], []
        ).append(d)
        grouped.setdefault("overall", {}).setdefault(pa["source_id"], []).append(d)

    cis = {}
    for ntype, by_source in sorted(grouped.items()):
        mean, lo, hi, n_src = _grouped_boot(by_source, n_boot, alpha)
        cis[ntype] = {
            "mean_diff": round(mean, 4),
            "ci_lo": round(lo, 4),
            "ci_hi": round(hi, 4),
            "n_sources": n_src,
        }
    return cis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--output", default="artifacts/ablation")
    args = parser.parse_args()

    items = load_items(args.items)
    print(f"Loaded {len(items)} items", flush=True)

    aux = {}
    print("Building feature examples...", flush=True)
    examples = build_feature_examples(items, seed=PAIR_SEED, aux=aux)
    print(f"  {len(examples)} examples", flush=True)

    full_idx = np.arange(len(SIGNALS))
    cosine_idx = np.array([0])

    all_ablation = {}
    all_errors = {}
    all_cis = {}

    for seed in SEEDS:
        train_sources, val_sources = split_sources(
            [e["source_id"] for e in examples], seed=seed, val_fraction=0.25
        )
        train = [e for e in examples if e["source_id"] in set(train_sources)]
        val = [e for e in examples if e["source_id"] in set(val_sources)]
        print(f"\n--- Seed {seed} (train={len(train)}, val={len(val)}) ---", flush=True)

        # Full fusion
        w_full = train_logistic(train, full_idx, seed)
        pairs_full = evaluate_detailed(val, w_full, full_idx)
        acc_full = aggregate(pairs_full)
        print(f"  full-fusion:  {acc_full}", flush=True)

        # Cosine only
        w_cos = np.ones(1)
        pairs_cos = evaluate_detailed(val, w_cos, cosine_idx)
        acc_cos = aggregate(pairs_cos)
        print(f"  cosine-only:  {acc_cos}", flush=True)

        # --- 1. Ablation: leave-one-out ---
        ablation_seed = {"full-fusion": acc_full, "cosine-only": acc_cos}
        for drop_i, drop_name in enumerate(SIGNALS):
            keep = np.array([i for i in range(len(SIGNALS)) if i != drop_i])
            w_drop = train_logistic(train, keep, seed)
            pairs_drop = evaluate_detailed(val, w_drop, keep)
            acc_drop = aggregate(pairs_drop)
            label = f"minus-{drop_name}"
            ablation_seed[label] = acc_drop
            delta = round(acc_full["overall"] - acc_drop["overall"], 4)
            print(f"  {label:25s} overall={acc_drop['overall']:.4f} (delta={delta:+.4f})", flush=True)
        all_ablation[seed] = ablation_seed

        # --- 2. Error analysis (on this seed's val set) ---
        fusion_wins_cos_loses = []
        cos_wins_fusion_loses = []
        for pf, pc in zip(pairs_full, pairs_cos):
            if pf["win"] == 1.0 and pc["win"] == 0.0:
                fusion_wins_cos_loses.append({
                    "neg_type": pf["neg_type"],
                    "source_id": pf["source_id"],
                    "pos_item": pf["pos_item"],
                    "neg_item": pf["neg_item"],
                    "fusion_margin": round(pf["margin"], 4),
                    "cosine_margin": round(pc["margin"], 4),
                    "pos_signals": [round(x, 4) for x in pf["pos_signals"]],
                    "neg_signals": [round(x, 4) for x in pf["neg_signals"]],
                })
            elif pc["win"] == 1.0 and pf["win"] == 0.0:
                cos_wins_fusion_loses.append({
                    "neg_type": pf["neg_type"],
                    "source_id": pf["source_id"],
                    "pos_item": pf["pos_item"],
                    "neg_item": pf["neg_item"],
                    "fusion_margin": round(pf["margin"], 4),
                    "cosine_margin": round(pc["margin"], 4),
                    "pos_signals": [round(x, 4) for x in pf["pos_signals"]],
                    "neg_signals": [round(x, 4) for x in pf["neg_signals"]],
                })
        all_errors[seed] = {
            "fusion_wins_cosine_loses": len(fusion_wins_cos_loses),
            "cosine_wins_fusion_loses": len(cos_wins_fusion_loses),
            "net_gain": len(fusion_wins_cos_loses) - len(cos_wins_fusion_loses),
            "fusion_wins_by_type": {},
            "cosine_wins_by_type": {},
            "examples_fusion_wins": fusion_wins_cos_loses[:5],
            "examples_cosine_wins": cos_wins_fusion_loses[:5],
        }
        for ntype in sorted({p["neg_type"] for p in pairs_full}):
            fw = sum(1 for p in fusion_wins_cos_loses if p["neg_type"] == ntype)
            cw = sum(1 for p in cos_wins_fusion_loses if p["neg_type"] == ntype)
            all_errors[seed]["fusion_wins_by_type"][ntype] = fw
            all_errors[seed]["cosine_wins_by_type"][ntype] = cw
        print(f"  error analysis: fusion_wins={len(fusion_wins_cos_loses)}, "
              f"cosine_wins={len(cos_wins_fusion_loses)}, "
              f"net_gain={len(fusion_wins_cos_loses) - len(cos_wins_fusion_loses)}", flush=True)

        # --- 3. Bootstrap CIs ---
        ci_full = bootstrap_ci(pairs_full)
        ci_cos = bootstrap_ci(pairs_cos)
        ci_diff = bootstrap_paired_diff_ci(pairs_full, pairs_cos)
        all_cis[seed] = {"full-fusion": ci_full, "cosine-only": ci_cos, "paired-diff": ci_diff}
        for ntype in sorted(ci_full.keys()):
            f = ci_full[ntype]
            c = ci_cos[ntype]
            d = ci_diff[ntype]
            print(f"  CI {ntype:16s}  fusion={f['mean']:.4f} [{f['ci_lo']:.4f}, {f['ci_hi']:.4f}]  "
                  f"cosine={c['mean']:.4f} [{c['ci_lo']:.4f}, {c['ci_hi']:.4f}]  "
                  f"diff={d['mean_diff']:+.4f} [{d['ci_lo']:+.4f}, {d['ci_hi']:+.4f}]", flush=True)

    # --- Aggregate ablation across seeds ---
    print("\n=== Ablation summary (mean over 5 seeds) ===\n", flush=True)
    abl_summary = {}
    conditions = list(all_ablation[SEEDS[0]].keys())
    neg_types = sorted(k for k in all_ablation[SEEDS[0]]["full-fusion"].keys() if k != "overall")
    for cond in conditions:
        overalls = [all_ablation[s][cond]["overall"] for s in SEEDS]
        abl_summary[cond] = {
            "overall_mean": round(statistics.mean(overalls), 4),
            "overall_std": round(statistics.stdev(overalls), 4),
        }
        for nt in neg_types:
            vals = [all_ablation[s][cond].get(nt, 0) for s in SEEDS]
            abl_summary[cond][nt + "_mean"] = round(statistics.mean(vals), 4)
        if cond.startswith("minus-"):
            delta = round(abl_summary["full-fusion"]["overall_mean"] - abl_summary[cond]["overall_mean"], 4)
            abl_summary[cond]["delta_overall"] = delta
        print(f"  {cond:25s} overall={abl_summary[cond]['overall_mean']:.4f} ± {abl_summary[cond]['overall_std']:.4f}"
              + (f"  delta={abl_summary[cond].get('delta_overall', 0):+.4f}" if cond.startswith("minus-") else ""),
              flush=True)

    # --- Aggregate error analysis ---
    print("\n=== Error analysis summary (mean over 5 seeds) ===\n", flush=True)
    err_summary = {
        "mean_fusion_wins": round(statistics.mean([all_errors[s]["fusion_wins_cosine_loses"] for s in SEEDS]), 1),
        "mean_cosine_wins": round(statistics.mean([all_errors[s]["cosine_wins_fusion_loses"] for s in SEEDS]), 1),
        "mean_net_gain": round(statistics.mean([all_errors[s]["net_gain"] for s in SEEDS]), 1),
    }
    for nt in neg_types:
        fw = statistics.mean([all_errors[s]["fusion_wins_by_type"].get(nt, 0) for s in SEEDS])
        cw = statistics.mean([all_errors[s]["cosine_wins_by_type"].get(nt, 0) for s in SEEDS])
        err_summary[f"{nt}_fusion_wins"] = round(fw, 1)
        err_summary[f"{nt}_cosine_wins"] = round(cw, 1)
        err_summary[f"{nt}_net"] = round(fw - cw, 1)
    print(f"  Fusion fixes per seed: {err_summary['mean_fusion_wins']}", flush=True)
    print(f"  Cosine fixes per seed: {err_summary['mean_cosine_wins']}", flush=True)
    print(f"  Net gain per seed: {err_summary['mean_net_gain']}", flush=True)
    for nt in neg_types:
        print(f"    {nt}: fusion_wins={err_summary[f'{nt}_fusion_wins']}, "
              f"cosine_wins={err_summary[f'{nt}_cosine_wins']}, "
              f"net={err_summary[f'{nt}_net']}", flush=True)

    # --- Per-seed bootstrap CIs (NOT pooled) ---
    # Each seed has a different validation split, so seeds are separate
    # experiments here. Averaging CI endpoints across seeds is not a valid
    # pooled bootstrap and was removed; inference across seeds is reserved
    # for the held-out evaluation (joint source resampling in
    # bootstrap_heldout.py).
    print("\n=== Per-seed source-grouped CIs (no cross-seed pooling) ===\n",
          flush=True)
    for s in SEEDS:
        d = all_cis[s]["paired-diff"]
        line = "  ".join(
            f"{nt}={v['mean_diff']:+.4f}[{v['ci_lo']:+.3f},{v['ci_hi']:+.3f}]"
            for nt, v in sorted(d.items())
        )
        print(f"  seed {s}: {line}", flush=True)

    report = {
        "experiment": "ablation + error analysis + per-seed source-grouped CIs",
        "signals": SIGNALS,
        "seeds": SEEDS,
        "ablation": abl_summary,
        "error_analysis": err_summary,
        "error_analysis_per_seed": {str(s): all_errors[s] for s in SEEDS},
        "bootstrap_ci_per_seed": {str(s): all_cis[s] for s in SEEDS},
        "bootstrap_note": (
            "Source-grouped resampling within each seed's validation split. "
            "No cross-seed pooling: seeds use different validation splits, "
            "and averaging CI endpoints is not a valid pooled bootstrap."
        ),
        "bootstrap_n": 2000,
    }
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    out_path = out / "ablation.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n→ {out_path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
