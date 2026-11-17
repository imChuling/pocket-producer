"""Grouping threshold for the pairwise fusion score on the frozen pack split.

Protocol: research/protocol-grouping-threshold-v1.md. Scores every pair of
items on each side of the frozen pack-only split with the deployed fusion
weights (backend/ranking/grouping.py) and with plain MS-CLAP cosine, picks
each score's threshold on the train packs, and reports held-out precision,
recall and average precision once, with pack-level bootstrap intervals.

  backend/.venv/bin/python research/run_grouping_threshold.py \
    --items research/data/fsld/items_msclap_packonly.jsonl \
    --manifest research/data/fsld/manifest.jsonl \
    --output artifacts/grouping-threshold/grouping_threshold.json

The output holds counts and scores only, no uploader names.
"""

import argparse
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from ranking.features import serving_key  # noqa: E402
from ranking.grouping import pair_fusion_score  # noqa: E402

SPLIT = ROOT / "artifacts" / "heldout-split-packonly" / "split.json"
WEIGHTS = ROOT / "artifacts" / "fusion-deploy" / "weights.json"
TARGET_PRECISION = 0.50
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 20261117
ALPHA = 0.05
TEMPO_TOLERANCE = 0.25
N_PARITY_CHECKS = 500


def load_items(path):
    items = []
    with open(path) as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                items.append({
                    "item_id": row["item_id"],
                    "source_id": row["source_id"],
                    "embedding": row["embedding"],
                    "bpm": row.get("bpm"),
                    "key": row.get("key"),
                    "tags": row.get("tags") or [],
                })
    return items


def uploader_by_source(items, manifest_path):
    by_id = {}
    with open(manifest_path) as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                by_id[str(row["freesound_id"])] = row["username"]
    out = {}
    for item in items:
        user = by_id.get(str(item["item_id"]).split(":")[-1])
        if user is not None:
            out.setdefault(item["source_id"], user)
    return out


def _tempo_matrix(bpms):
    """tempo_match(a, b) for every ordered pair, 0 where either is missing."""
    b = np.array([x if x else np.nan for x in bpms], dtype=np.float64)
    diff = np.abs(b[:, None] - b[None, :])
    ratio = diff / np.maximum(b[:, None], 1.0)
    out = np.clip(1.0 - ratio / TEMPO_TOLERANCE, 0.0, None)
    return np.nan_to_num(out, nan=0.0)


def pair_matrices(items, weights):
    """Fusion and cosine score matrices for one side of the split."""
    emb = np.asarray([it["embedding"] for it in items], dtype=np.float64)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    cos = emb @ emb.T

    tm = _tempo_matrix([it["bpm"] for it in items])
    tempo = (tm + tm.T) / 2.0

    keys = [serving_key(it["key"]) for it in items]
    codes = {k: i for i, k in enumerate(sorted({k for k in keys if k is not None}))}
    kc = np.array([codes[k] if k is not None else -1 for k in keys])
    key = ((kc[:, None] == kc[None, :]) & (kc[:, None] >= 0)).astype(np.float64)

    tag_sets = [{t.lower() for t in it["tags"]} for it in items]
    vocab = {t: i for i, t in enumerate(sorted(set().union(*tag_sets)))}
    tags = np.zeros((len(items), max(len(vocab), 1)))
    for i, s in enumerate(tag_sets):
        for t in s:
            tags[i, vocab[t]] = 1.0
    inter = tags @ tags.T
    sizes = tags.sum(axis=1)
    union = sizes[:, None] + sizes[None, :] - inter
    jac = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)

    w = np.asarray(weights, dtype=np.float64)
    fusion = (w[0] + w[1]) * cos + w[2] * tempo + w[3] * key + w[4] * jac
    return fusion, cos


def check_parity(items, fusion, weights, rng):
    """The vectorised scores must equal the function the product calls."""
    n = len(items)
    worst = 0.0
    for _ in range(N_PARITY_CHECKS):
        i, j = rng.choice(n, size=2, replace=False)
        a, b = items[i], items[j]
        ref = pair_fusion_score(
            weights, a["embedding"], b["embedding"], a["bpm"], b["bpm"],
            a["key"], b["key"], a["tags"], b["tags"],
        )
        worst = max(worst, abs(ref - fusion[i, j]))
    if worst > 1e-6:
        raise AssertionError(f"vectorised fusion differs from grouping.py by {worst}")
    return worst


class Side:
    """All within-side pairs, with pack labels kept for the bootstrap."""

    def __init__(self, items, fusion, cos, packs=None):
        keep = np.arange(len(items))
        if packs is not None:
            keep = np.array([i for i, it in enumerate(items) if it["source_id"] in packs])
        sources = sorted({items[i]["source_id"] for i in keep})
        index = {s: k for k, s in enumerate(sources)}
        pack = np.array([index[items[i]["source_id"]] for i in keep])
        iu, ju = np.triu_indices(len(keep), k=1)
        self.n_packs = len(sources)
        self.n_items = len(keep)
        self.pa, self.pb = pack[iu], pack[ju]
        self.positive = self.pa == self.pb
        gi, gj = keep[iu], keep[ju]
        self.scores = {"fusion": fusion[gi, gj], "cosine": cos[gi, gj]}

    def counts(self):
        return {
            "packs": self.n_packs,
            "items": self.n_items,
            "positive_pairs": int(self.positive.sum()),
            "negative_pairs": int((~self.positive).sum()),
        }

    def pair_weights(self, pack_weights):
        """Multiplicity of each pair under a bootstrap draw of packs."""
        wa, wb = pack_weights[self.pa], pack_weights[self.pb]
        return np.where(self.positive, wa, wa * wb)


def precision_recall(scores, positive, threshold, weights=None):
    w = np.ones_like(scores) if weights is None else weights
    above = scores >= threshold
    tp = float(w[above & positive].sum())
    fp = float(w[above & ~positive].sum())
    pos = float(w[positive].sum())
    precision = tp / (tp + fp) if tp + fp > 0 else float("nan")
    recall = tp / pos if pos > 0 else float("nan")
    return precision, recall


def average_precision(order, positive, weights=None):
    """Weighted average precision over pairs sorted by descending score."""
    w = np.ones(len(order)) if weights is None else weights[order]
    pos = positive[order]
    tp = np.cumsum(w * pos)
    seen = np.cumsum(w)
    total = tp[-1]
    if total <= 0:
        return float("nan")
    precision = np.divide(tp, seen, out=np.zeros_like(tp), where=seen > 0)
    return float(np.sum(precision * w * pos) / total)


def choose_thresholds(scores, positive):
    """Primary (precision >= target, smallest) and F1-max thresholds."""
    order = np.argsort(-scores, kind="stable")
    s = scores[order]
    pos = positive[order]
    tp = np.cumsum(pos)
    seen = np.arange(1, len(s) + 1)
    # Only cut between distinct scores: everything tied at s[k] joins together.
    last_of_value = np.append(s[1:] != s[:-1], True)
    precision = tp / seen
    recall = tp / tp[-1]
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=precision + recall > 0)
    cuts = np.flatnonzero(last_of_value)
    f1_cut = cuts[np.argmax(f1[cuts])]
    reaching = cuts[precision[cuts] >= TARGET_PRECISION]
    out = {
        "f1_max": {
            "threshold": float(s[f1_cut]),
            "train_precision": float(precision[f1_cut]),
            "train_recall": float(recall[f1_cut]),
            "train_f1": float(f1[f1_cut]),
        }
    }
    if len(reaching):
        k = reaching.max()
        out["primary"] = {
            "rule": f"smallest threshold with train precision >= {TARGET_PRECISION}",
            "threshold": float(s[k]),
            "train_precision": float(precision[k]),
            "train_recall": float(recall[k]),
        }
    else:
        out["primary"] = dict(out["f1_max"], rule=(
            f"fallback: no threshold reached train precision {TARGET_PRECISION}; F1 max"))
    return out


def _interval(values):
    lo, hi = np.nanpercentile(values, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    return [round(float(lo), 4), round(float(hi), 4)]


def evaluate(side, thresholds, rng):
    """Point estimates and pack-bootstrap intervals on one held-out subset."""
    orders = {name: np.argsort(-sc, kind="stable") for name, sc in side.scores.items()}
    point = {}
    for name, sc in side.scores.items():
        entry = {"average_precision": round(average_precision(orders[name], side.positive), 4)}
        for which in ("primary", "f1_max"):
            p, r = precision_recall(sc, side.positive, thresholds[name][which]["threshold"])
            entry[which] = {"precision": round(p, 4), "recall": round(r, 4)}
        point[name] = entry

    boot = {name: {"ap": [], "primary_p": [], "primary_r": []} for name in side.scores}
    for _ in range(N_BOOTSTRAP):
        draw = rng.integers(0, side.n_packs, side.n_packs)
        pack_w = np.bincount(draw, minlength=side.n_packs).astype(np.float64)
        w = side.pair_weights(pack_w)
        for name, sc in side.scores.items():
            boot[name]["ap"].append(average_precision(orders[name], side.positive, w))
            p, r = precision_recall(sc, side.positive, thresholds[name]["primary"]["threshold"], w)
            boot[name]["primary_p"].append(p)
            boot[name]["primary_r"].append(r)

    for name in side.scores:
        point[name]["average_precision_ci"] = _interval(boot[name]["ap"])
        point[name]["primary"]["precision_ci"] = _interval(boot[name]["primary_p"])
        point[name]["primary"]["recall_ci"] = _interval(boot[name]["primary_r"])
    diff = np.array(boot["fusion"]["ap"]) - np.array(boot["cosine"]["ap"])
    point["fusion_minus_cosine_ap"] = {
        "point": round(
            point["fusion"]["average_precision"] - point["cosine"]["average_precision"], 4
        ),
        "ci": _interval(diff),
    }
    return point


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/grouping-threshold/grouping_threshold.json")
    args = parser.parse_args()

    split = json.loads(SPLIT.read_text())
    weights_artifact = json.loads(WEIGHTS.read_text())
    weights = weights_artifact["weights"]
    heldout_ids = set(split["heldout_source_ids"])

    items = load_items(args.items)
    train_items = [it for it in items if it["source_id"] not in heldout_ids]
    heldout_items = [it for it in items if it["source_id"] in heldout_ids]
    uploader = uploader_by_source(items, args.manifest)
    train_users = {uploader[it["source_id"]] for it in train_items if it["source_id"] in uploader}
    heldout_packs = {it["source_id"] for it in heldout_items}
    disjoint_packs = {s for s in heldout_packs if uploader.get(s) not in train_users}

    rng = np.random.default_rng(BOOTSTRAP_SEED)

    train_fusion, train_cos = pair_matrices(train_items, weights)
    parity = check_parity(train_items, train_fusion, weights, rng)
    train = Side(train_items, train_fusion, train_cos)
    del train_fusion, train_cos
    thresholds = {name: choose_thresholds(sc, train.positive) for name, sc in train.scores.items()}
    for name in thresholds:
        thresholds[name]["train_average_precision"] = round(average_precision(
            np.argsort(-train.scores[name], kind="stable"), train.positive), 4)
    train_counts = train.counts()
    del train

    held_fusion, held_cos = pair_matrices(heldout_items, weights)
    check_parity(heldout_items, held_fusion, weights, rng)
    heldout = Side(heldout_items, held_fusion, held_cos)
    disjoint = Side(heldout_items, held_fusion, held_cos, packs=disjoint_packs)

    report = {
        "experiment": "grouping threshold for the pairwise fusion score",
        "protocol": "research/protocol-grouping-threshold-v1.md",
        "status": "threshold chosen on train packs; held-out computed once",
        "items_file": f"research/data/fsld/{pathlib.Path(args.items).name}",
        "split_sha256": split["sha256_heldout_ids"],
        "weights": {"file": "artifacts/fusion-deploy/weights.json",
                    "model_id": weights_artifact["model_id"], "values": weights},
        "score_function": "backend/ranking/grouping.py: pair_fusion_score",
        "parity_max_abs_diff": parity,
        "target_precision": TARGET_PRECISION,
        "bootstrap": {"unit": "pack", "resamples": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED,
                      "interval": "95% percentile"},
        "train": {"counts": train_counts, "thresholds": thresholds},
        "heldout": {"counts": heldout.counts(), "results": evaluate(heldout, thresholds, rng)},
        "heldout_uploader_disjoint": {
            "definition": "held-out packs whose uploader has no pack on the train side",
            "counts": disjoint.counts(),
            "results": evaluate(disjoint, thresholds, rng),
        },
    }
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("train", "heldout", "heldout_uploader_disjoint")},
                     indent=1))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
