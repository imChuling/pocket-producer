"""Fine-tune the deployed fusion weights on logged musician decisions.

Replaces (part of) the cold-start pack co-membership proxy with the evidence
the prototype was built to collect: within one served proposal list, an
accepted or inserted fragment is preferred over a rejected one. Pairs come
from the exposure log and feedback events as JSONL dumps:

  mongoexport --collection ranking_requests --out requests.jsonl
  mongoexport --collection ranking_feedback --out feedback.jsonl

Training warm-starts at the shipped weights and is L2-anchored to them, so a
few dozen decisions nudge the fusion rather than replace it. Accuracy is
reported on the same pairs that were trained on (train fit, not a held-out
estimate) and the output artifact says so.

Signals logged after the base five (for example chroma_beat_aligned and
onset_pattern) are named with --extra-signals and start at weight zero.
The result must then pass the behavioural guardrail
(research/compat_tests/guardrail.py) on a stored feature set; if it does
not, no weights file is written. The verdict is always written next to the
output as guardrail.json.

Usage:
  backend/.venv/bin/python research/finetune_from_feedback.py \
    --requests requests.jsonl --feedback feedback.jsonl \
    --weights artifacts/fusion-deploy/weights.json \
    --output artifacts/fusion-feedback/weights.json \
    [--extra-signals chroma_beat_aligned,onset_pattern] \
    [--guardrail-store /Volumes/Shirlene/Pocket_Producer/cache/musdb18_v1]
"""

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

from ranking.fusion_ranker import SIGNAL_NAMES, load_weights  # noqa: E402
from ranking.research.feedback_pairs import (  # noqa: E402
    build_feedback_pairs,
    finetune_weights,
    pairwise_accuracy,
)

SEEDS = [20260725, 20260801, 20260802, 20260803, 20260804]
MIN_PAIRS = 20


def load_jsonl(path):
    rows = []
    for line in pathlib.Path(path).read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", required=True)
    parser.add_argument("--feedback", required=True)
    parser.add_argument("--weights", default="artifacts/fusion-deploy/weights.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--l2", type=float, default=1.0)
    parser.add_argument("--min-pairs", type=int, default=MIN_PAIRS)
    parser.add_argument("--extra-signals", default="",
                        help="comma-separated signals logged after the base ones")
    parser.add_argument("--guardrail-store", type=pathlib.Path, default=None,
                        help="behavioural feature store (default: the MUSDB18-HQ store)")
    args = parser.parse_args()

    from research.compat_tests import guardrail

    base = load_weights(args.weights)
    names = list(base.get("signals") or SIGNAL_NAMES)
    names += [s for s in args.extra_signals.split(",") if s]
    w0 = np.zeros(len(names))
    w0[: len(base["weights"])] = base["weights"]
    store = args.guardrail_store or guardrail.DEFAULT_STORE
    if not store.is_dir():
        print(f"ABORT: guardrail feature store not found at {store}; nothing written.")
        return 1
    requests = load_jsonl(args.requests)
    feedback = load_jsonl(args.feedback)
    pairs = build_feedback_pairs(requests, feedback, model_id=base["model_id"])
    # Lists logged before the extra signals existed have shorter vectors.
    pairs = [p for p in pairs if len(p["pos"]) == len(names) == len(p["neg"])]
    n_requests = len({p["request_id"] for p in pairs})
    print(f"{len(requests)} served lists, {len(feedback)} events -> "
          f"{len(pairs)} decision pairs from {n_requests} lists", flush=True)
    if len(pairs) < args.min_pairs:
        print(f"ABORT: need at least {args.min_pairs} pairs; nothing written.", flush=True)
        return 1

    acc_before = pairwise_accuracy(w0, pairs)
    per_seed = []
    for seed in SEEDS:
        w = finetune_weights(w0, pairs, seed=seed, lr=args.lr, epochs=args.epochs, l2=args.l2)
        per_seed.append(w)
        print(f"  seed {seed}: train-fit {pairwise_accuracy(w, pairs):.4f} "
              f"w={np.array2string(w, precision=3)}", flush=True)
    mean_w = np.mean(per_seed, axis=0)
    acc_after = pairwise_accuracy(mean_w, pairs)
    print(f"pairwise accuracy on the training pairs: {acc_before:.4f} -> {acc_after:.4f}")
    print(f"mean weights: {np.array2string(mean_w, precision=4)}")

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    verdict = guardrail.check(
        guardrail.WeightSet.of(names, mean_w),
        guardrail.iter_store(store),
        guardrail.WeightSet.of(base.get("signals") or SIGNAL_NAMES, base["weights"]),
    )
    verdict["store"] = str(store)
    (out.parent / "guardrail.json").write_text(json.dumps(verdict, indent=2))
    if verdict["verdict"] != "accept":
        print("REJECTED by the behavioural guardrail; weights not written:")
        for reason in verdict["reasons"]:
            print(f"  - {reason}")
        print(f"-> {out.parent / 'guardrail.json'}")
        return 2
    print(f"guardrail: accept ({verdict['n_pairs']} stored pairs)")

    out.write_text(json.dumps({
        "model_id": base["model_id"],
        "signals": names,
        "weights": [round(float(x), 6) for x in mean_w],
        "per_seed_weights": {
            str(s): [round(float(x), 6) for x in w] for s, w in zip(SEEDS, per_seed)
        },
        "representation_model": base.get("representation_model"),
        "trained_on": (
            f"{base.get('trained_on')}; then fine-tuned on {len(pairs)} musician "
            f"decision pairs from {n_requests} served lists (BPR, warm start, "
            f"L2 {args.l2} toward the base weights, lr {args.lr}, {args.epochs} epochs, "
            f"mean over {len(SEEDS)} seeds)"
        ),
        "finetuned_from": {
            "weights_file": args.weights,
            "sha256": hashlib.sha256(pathlib.Path(args.weights).read_bytes()).hexdigest(),
        },
        "decision_pairs": len(pairs),
        "served_lists_with_decisions": n_requests,
        "train_fit_pairwise_accuracy": {"before": acc_before, "after": acc_after},
        "caveat": "train-fit accuracy on the decision pairs themselves, not a held-out estimate",
        "guardrail": {"verdict": verdict["verdict"], "store": str(store)},
    }, indent=2))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
