"""Multi-signal fusion: does combining audio cosine with music-theory
signals beat cosine alone?

Signals per (context, candidate):
  audio_cos_mean  cosine(mean context vector, candidate)
  audio_cos_max   max cosine(context_i, candidate)
  tempo           tempo_match(mean context bpm, candidate bpm)
  key             max key_match(context key_i, candidate key)
  tag_jaccard     |context_tags ∩ cand_tags| / |context_tags ∪ cand_tags|
  role_gap        candidate's zero-shot role fills a role missing from context
  harmonic        transpose-invariant chroma correlation vs session profile

The last two are SESSION-STRUCTURE signals (computed from what the context
ensemble is missing / how it aggregates), not pairwise item similarity —
they require --chroma and --role-prompts from extract_fsld_features.py and
are skipped (with a warning) when those files are absent.

Model: logistic fusion (5 weights + bias) trained with BPR. Deliberately
tiny — the claim is signal complementarity, not model capacity.

Honesty guard: "easy" negatives were MINED by tempo/key incompatibility, so
tempo/key features see the label-construction rule there. Accuracy is
reported per negative type; the claim must rest on hard_tempo_key (tempo and
key both compatible — those features are neutral) and hard_similar.

Usage:
  python research/run_fusion.py \
    --items research/data/fsld/items.jsonl \
    --output artifacts/fusion
"""

import argparse
import json
import pathlib
import statistics
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from ranking.features import key_match, tempo_match
from ranking.harmonic_probe import session_chroma, transpose_invariant_score
from ranking.role_probe import CONFIDENCE_THRESHOLD, RoleProbe
from ranking.weak_pairs import build_weak_pairs, split_sources

SEEDS = [20260725, 20260801, 20260802, 20260803, 20260804]
PAIR_SEED = 20260725
SIGNALS = ["audio_cos_mean", "audio_cos_max", "tempo", "key", "tag_jaccard",
           "role_gap", "harmonic"]


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

    # Session-structure signals (0.0 when precomputed features are absent)
    role_gap = 0.0
    roles = aux.get("roles")
    if roles is not None:
        present = {}
        for i in context_items:
            role, conf = roles[i["item_id"]]
            if conf >= CONFIDENCE_THRESHOLD:
                present[role] = max(present.get(role, 0.0), conf)
        cand_role, cand_conf = roles[candidate["item_id"]]
        if cand_role not in present and cand_conf >= CONFIDENCE_THRESHOLD:
            role_gap = cand_conf

    harmonic = 0.0
    chroma = aux.get("chroma")
    if chroma is not None:
        ctx_chromas = [chroma[i["item_id"]] for i in context_items
                       if i["item_id"] in chroma]
        cand_chroma = chroma.get(candidate["item_id"])
        if ctx_chromas and cand_chroma is not None:
            sess = session_chroma(ctx_chromas)
            harmonic, _shift = transpose_invariant_score(sess, cand_chroma)

    return np.array([
        float(mean_ctx @ cand_vec),
        float((ctx_vecs @ cand_vec).max()),
        tempo_match(ctx_bpm, candidate.get("bpm")),
        max((key_match(k, candidate.get("key")) for k in ctx_keys), default=0.0),
        jaccard,
        role_gap,
        harmonic,
    ])


def build_feature_examples(items, seed, aux):
    """Rebuild pairs and attach per-candidate signal vectors.

    build_weak_pairs stores references to the same embedding list objects the
    items carry, so id() maps every embedding back to its item in-process.
    """
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
        })
    return examples


def train_logistic(train, feature_idx, seed, epochs=300, lr=0.05):
    rng = np.random.default_rng(seed)
    dim = len(feature_idx)
    # No bias term: it cancels in the BPR pairwise difference.
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
                grad = -(1.0 - sig) * diff  # d(-log sigmoid(z))/dw
                t += 1
                m_w = beta1 * m_w + (1 - beta1) * grad
                v_w = beta2 * v_w + (1 - beta2) * grad**2
                m_hat = m_w / (1 - beta1**t)
                v_hat = v_w / (1 - beta2**t)
                w -= lr * m_hat / (np.sqrt(v_hat) + eps)
    return w


def evaluate(examples, w, feature_idx):
    overall_wins, overall_total = 0.0, 0
    by_type = {}
    for ex in examples:
        sp = w @ ex["pos"][feature_idx]
        for neg, ntype in zip(ex["negs"], ex["neg_types"]):
            sn = w @ neg[feature_idx]
            win = 1.0 if sp > sn else (0.5 if sp == sn else 0.0)
            overall_wins += win
            overall_total += 1
            bucket = by_type.setdefault(ntype, [0.0, 0])
            bucket[0] += win
            bucket[1] += 1
    result = {"overall": round(overall_wins / overall_total, 4)}
    for ntype, (wins, total) in sorted(by_type.items()):
        result[ntype] = round(wins / total, 4)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--chroma", default="research/data/fsld/chroma.jsonl")
    parser.add_argument("--role-prompts", default="research/data/fsld/role_prompts.json")
    parser.add_argument("--output", default="artifacts/fusion")
    args = parser.parse_args()

    items = load_items(args.items)
    dim = len(items[0]["embedding"])
    print(f"Loaded {len(items)} items, embedding dim={dim}", flush=True)

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
        print(f"  WARNING: no chroma at {chroma_path}; harmonic signal = 0", flush=True)

    prompts_path = pathlib.Path(args.role_prompts)
    if prompts_path.exists():
        prompt_map = json.loads(prompts_path.read_text())
        probe = RoleProbe(np.array(list(prompt_map.values())))
        aux["roles"] = {
            item["item_id"]: probe.classify(item["embedding"]) for item in items
        }
        n_conf = sum(1 for _, c in aux["roles"].values() if c >= CONFIDENCE_THRESHOLD)
        print(f"  roles classified; {n_conf}/{len(items)} above threshold", flush=True)
    else:
        print(f"  WARNING: no role prompts at {prompts_path}; role_gap = 0", flush=True)

    print("Building feature examples...", flush=True)
    examples = build_feature_examples(items, seed=PAIR_SEED, aux=aux)
    print(f"  {len(examples)} examples", flush=True)

    n_with_bpm = sum(1 for i in items if i.get("bpm"))
    n_with_key = sum(1 for i in items if i.get("key"))
    n_with_tags = sum(1 for i in items if i.get("tags"))
    print(f"  items with bpm={n_with_bpm}, key={n_with_key}, tags={n_with_tags}", flush=True)

    conditions = {
        "cosine-only": [0],                       # audio_cos_mean
        "cosine+theory": [0, 2, 3],               # + tempo, key
        "cosine+tags": [0, 4],                    # + tag_jaccard
        "fusion-5sig": [0, 1, 2, 3, 4],           # item-level signals only
        "cosine+session": [0, 5, 6],              # + role_gap, harmonic
        "fusion-7sig": [0, 1, 2, 3, 4, 5, 6],     # everything
    }

    results = {name: [] for name in conditions}
    per_type_last = {}

    for seed in SEEDS:
        train_sources, val_sources = split_sources(
            [e["source_id"] for e in examples], seed=seed, val_fraction=0.25
        )
        train = [e for e in examples if e["source_id"] in set(train_sources)]
        val = [e for e in examples if e["source_id"] in set(val_sources)]
        print(f"\n--- Seed {seed} (train={len(train)}, val={len(val)}) ---", flush=True)

        for name, fidx in conditions.items():
            fidx_arr = np.array(fidx)
            if name == "cosine-only":
                w = np.ones(1)  # no training needed: single monotone signal
            else:
                w = train_logistic(train, fidx_arr, seed)
            ev = evaluate(val, w, fidx_arr)
            results[name].append(ev)
            weights_str = np.array2string(w, precision=3)
            print(f"  {name:15s} overall={ev['overall']:.4f}  "
                  + "  ".join(f"{k}={v:.3f}" for k, v in ev.items() if k != "overall")
                  + f"  w={weights_str}", flush=True)

    print("\n=== Summary over 5 seeds (val overall) ===\n", flush=True)
    summary = {}
    for name in conditions:
        overalls = [r["overall"] for r in results[name]]
        mean = statistics.mean(overalls)
        std = statistics.stdev(overalls)
        summary[name] = {"mean": round(mean, 4), "std": round(std, 4),
                         "values": overalls}
        print(f"  {name:15s} {mean:.4f} ± {std:.4f}", flush=True)

    print("\n=== Per-negative-type (mean over seeds) ===\n", flush=True)
    per_type_summary = {}
    neg_types = sorted({k for r in results["fusion-7sig"] for k in r if k != "overall"})
    header = "  " + " " * 15 + "  ".join(f"{t:>16s}" for t in neg_types)
    print(header, flush=True)
    for name in conditions:
        row = {}
        for t in neg_types:
            vals = [r[t] for r in results[name] if t in r]
            row[t] = round(statistics.mean(vals), 4) if vals else None
        per_type_summary[name] = row
        print(f"  {name:15s}" + "  ".join(f"{row[t]:16.4f}" for t in neg_types), flush=True)

    report = {
        "experiment": "multi-signal fusion vs cosine",
        "items_file": str(args.items),
        "pair_seed": PAIR_SEED,
        "signals": SIGNALS,
        "conditions": {k: [SIGNALS[i] for i in v] for k, v in conditions.items()},
        "seeds": SEEDS,
        "summary": summary,
        "per_negative_type": per_type_summary,
        "caveat": "easy negatives were mined by tempo/key incompatibility; "
                  "claims rest on hard_tempo_key and hard_similar columns",
    }
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    out_path = out / "fusion.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n→ {out_path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
