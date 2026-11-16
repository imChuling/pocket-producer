"""Held-out sensitivity to uploaders shared with the train side.

The frozen split (artifacts/heldout-split-packonly/split.json) groups by
pack. Each pack has one uploader, but an uploader can publish several packs,
so some held-out packs come from uploaders who also have packs on the train
side. A ranker could then score well on those queries by recognising an
uploader's sound rather than pack co-membership.

This re-scores the frozen held-out pairs with the committed per-seed weights
(no retraining) on two subsets: all queries, and queries whose pack's
uploader has no pack on the train side. Pairs, negatives and weights are
unchanged; only which queries are counted differs. Post hoc, descriptive.

  python research/run_uploader_overlap_check.py \
    --items research/data/fsld/items_msclap_packonly.jsonl \
    --sensitivity artifacts/msclap-sensitivity-correction/sensitivity.json \
    --output artifacts/uploader-overlap-check/msclap.json

  python research/run_uploader_overlap_check.py \
    --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
    --sensitivity artifacts/heldout-eval-correction/sensitivity.json \
    --output artifacts/uploader-overlap-check/laion.json

The output holds counts only, no uploader names.
"""

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from run_fusion import PAIR_SEED, build_feature_examples, load_items, rules_standin  # noqa: E402

FUSION_IDX = np.array([0, 1, 2, 3, 4])
COSINE_IDX = np.array([0])
RULES_IDX, RULES_WEIGHTS = rules_standin()
RULES_IDX = np.array(RULES_IDX)
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 42
ALPHA = 0.05


def uploader_by_source(items, manifest_path) -> dict[str, str]:
    """Pack (source_id) -> uploader, from the FSLD manifest."""
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


def shared_uploader_sources(train_sources, heldout_sources, uploader) -> set[str]:
    """Held-out packs whose uploader also has a pack on the train side."""
    train_users = {uploader[s] for s in train_sources if s in uploader}
    return {s for s in heldout_sources if uploader.get(s) in train_users}


def _wins(examples, w, idx):
    """Per comparison: (source_id, neg_type, win) with ties as half."""
    rows = []
    for ex in examples:
        sp = float(w @ ex["pos"][idx])
        for neg, ntype in zip(ex["negs"], ex["neg_types"]):
            sn = float(w @ neg[idx])
            rows.append((ex["source_id"], ntype, 1.0 if sp > sn else (0.5 if sp == sn else 0.0)))
    return rows


def _accuracy(rows):
    out = {"overall": round(float(np.mean([r[2] for r in rows])), 4)}
    for ntype in sorted({r[1] for r in rows}):
        out[ntype] = round(float(np.mean([r[2] for r in rows if r[1] == ntype])), 4)
    return out


def fusion_vs_cosine(examples, seed_weights):
    """Source-grouped bootstrap of fusion minus cosine, pooled over seeds."""
    sources = sorted({ex["source_id"] for ex in examples})
    index = {s: i for i, s in enumerate(sources)}
    cosine = _wins(examples, np.ones(1), COSINE_IDX)
    types = sorted({r[1] for r in cosine}) + ["overall"]
    diffs = {t: np.zeros((len(seed_weights), len(sources))) for t in types}
    counts = {t: np.zeros(len(sources)) for t in types}
    for si, w in enumerate(seed_weights):
        fusion = _wins(examples, np.asarray(w), FUSION_IDX)
        for (source, ntype, wf), (_, _, wc) in zip(fusion, cosine):
            i = index[source]
            for t in (ntype, "overall"):
                diffs[t][si, i] += wf - wc
                if si == 0:
                    counts[t][i] += 1
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    result = {}
    for t in types:
        total = counts[t].sum()
        point = float(np.mean([diffs[t][si].sum() / total for si in range(len(seed_weights))]))
        boot = np.empty(N_BOOTSTRAP)
        for b in range(N_BOOTSTRAP):
            pick = rng.integers(0, len(sources), size=len(sources))
            n = counts[t][pick].sum()
            boot[b] = np.nan if n == 0 else np.mean(diffs[t][:, pick].sum(axis=1) / n)
        result[t] = {
            "point_delta": round(point, 6),
            "ci_lo": round(float(np.nanpercentile(boot, 100 * ALPHA / 2)), 6),
            "ci_hi": round(float(np.nanpercentile(boot, 100 * (1 - ALPHA / 2))), 6),
            "n_comparisons": int(total),
        }
    return result


def summarise(examples, seed_weights):
    per_seed = {"rules": [], "cosine": [], "fusion-5sig": []}
    for w in seed_weights:
        per_seed["fusion-5sig"].append(_accuracy(_wins(examples, np.asarray(w), FUSION_IDX)))
    per_seed["cosine"] = [_accuracy(_wins(examples, np.ones(1), COSINE_IDX))] * len(seed_weights)
    per_seed["rules"] = [_accuracy(_wins(examples, RULES_WEIGHTS, RULES_IDX))] * len(seed_weights)
    means = {
        name: {k: round(float(np.mean([r[k] for r in rows])), 4) for k in rows[0]}
        for name, rows in per_seed.items()
    }
    return {
        "n_sources": len({ex["source_id"] for ex in examples}),
        "n_queries": len(examples),
        "mean_accuracy": means,
        "fusion_vs_cosine": fusion_vs_cosine(examples, seed_weights),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--sensitivity", required=True, help="committed run with per-seed weights")
    parser.add_argument("--split", default="artifacts/heldout-split-packonly/split.json")
    parser.add_argument("--manifest", default="research/data/fsld/manifest.jsonl")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    frozen = json.loads(pathlib.Path(args.sensitivity).read_text())
    seed_weights = [row["fusion-5sig"] for row in frozen["per_seed_weights"]]
    split = json.loads(pathlib.Path(args.split).read_text())
    heldout_ids = set(split["heldout_source_ids"])

    items = load_items(args.items)
    train_sources = {i["source_id"] for i in items if i["source_id"] not in heldout_ids}
    heldout_items = [i for i in items if i["source_id"] in heldout_ids]
    uploader = uploader_by_source(items, args.manifest)
    shared = shared_uploader_sources(train_sources, heldout_ids, uploader)

    examples = build_feature_examples(heldout_items, seed=PAIR_SEED, aux={})
    everything = summarise(examples, seed_weights)

    # The committed run must be reproduced before the subset means anything.
    frozen_fusion = frozen["heldout_summary"]["fusion-5sig"]
    for key, value in everything["mean_accuracy"]["fusion-5sig"].items():
        expected = frozen_fusion[f"mean_{key}"]
        if abs(value - expected) > 1e-3:
            raise SystemExit(f"does not reproduce {args.sensitivity}: {key} {value} vs {expected}")

    unshared = [ex for ex in examples if ex["source_id"] not in shared]
    report = {
        "experiment": "held-out sensitivity to uploaders shared with the train side",
        "status": "post hoc, descriptive; frozen pairs and committed weights, no retraining",
        "sensitivity_file": args.sensitivity,
        "split_sha256": split.get("sha256_heldout_ids", ""),
        "heldout_packs": len(heldout_ids),
        "heldout_packs_with_shared_uploader": len(shared),
        "heldout_items": len(heldout_items),
        "heldout_items_with_shared_uploader": sum(
            1 for i in heldout_items if i["source_id"] in shared
        ),
        "uploaders_on_both_sides": len(
            {uploader[s] for s in shared}
        ),
        "all_queries": everything,
        "queries_without_shared_uploader": summarise(unshared, seed_weights),
    }
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    for name in ("all_queries", "queries_without_shared_uploader"):
        hs = report[name]["fusion_vs_cosine"]["hard_similar"]
        print(f"{name}: queries={report[name]['n_queries']} hard_similar fusion-cosine "
              f"{hs['point_delta']:+.4f} [{hs['ci_lo']:+.4f}, {hs['ci_hi']:+.4f}]")
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
