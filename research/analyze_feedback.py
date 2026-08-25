"""Aggregate proposal telemetry into per-model acceptance metrics.

Joins the served-list log (ranking_requests) with interaction events
(ranking_feedback), both as JSONL dumps produced by mongoexport:

  mongoexport --collection ranking_requests --out requests.jsonl
  mongoexport --collection ranking_feedback --out feedback.jsonl

Per model_id_served:
  n_requests            served lists (the exposure denominator)
  n_proposals           proposals shown (sum of list lengths)
  list_acceptance       fraction of lists with >=1 accept or insert
  item_accept_rate      accepts+inserts / proposals
  undo_per_insert       undos / inserts
  preview_reject_rate   previewed proposals later rejected / previewed
  mean_accepted_rank    mean rank_position over accept+insert events
Bootstrap CIs (percentile, resampled over requests) are reported for
list_acceptance and undo_per_insert.

Usage:
  backend/.venv/bin/python research/analyze_feedback.py \
    --requests requests.jsonl --feedback feedback.jsonl \
    --output artifacts/telemetry-pilot/metrics.json
"""

import argparse
import json
import pathlib
from collections import defaultdict

import numpy as np

ACCEPT_EVENTS = ("accept", "insert")
N_BOOTSTRAP = 10_000
ALPHA = 0.05
BOOTSTRAP_SEED = 20260825


def load_jsonl(path):
    rows = []
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def join_events(requests, feedback):
    """Attach feedback events to their served request; return orphan count.

    Events whose request_id has no logged exposure are dropped (they have
    no denominator) and counted, so a pipeline gap is visible in output.
    """
    by_request = {r["request_id"]: dict(r, events=[]) for r in requests}
    orphans = 0
    for event in feedback:
        req = by_request.get(event.get("request_id"))
        if req is None:
            orphans += 1
            continue
        req["events"].append(event)
    return list(by_request.values()), orphans


def _request_stats(req):
    """Per-request counters used by both point estimates and bootstrap."""
    events = req["events"]
    accepts = [e for e in events if e["event"] in ACCEPT_EVENTS]
    inserts = [e for e in events if e["event"] == "insert"]
    undos = [e for e in events if e["event"] == "undo"]
    previewed = {e["fragment_id"] for e in events if e["event"] == "preview"}
    rejected = {e["fragment_id"] for e in events if e["event"] == "reject"}
    return {
        "n_proposals": len(req.get("fragment_ids", [])),
        "accepted_list": 1 if accepts else 0,
        "n_accepts": len(accepts),
        "n_inserts": len(inserts),
        "n_undos": len(undos),
        "n_previewed": len(previewed),
        "n_preview_rejected": len(previewed & rejected),
        "accepted_ranks": [e["rank_position"] for e in accepts],
    }


def _ratio(num, den):
    return num / den if den else None


def _metrics_from_stats(stats):
    n_requests = len(stats)
    n_proposals = sum(s["n_proposals"] for s in stats)
    n_accepts = sum(s["n_accepts"] for s in stats)
    n_inserts = sum(s["n_inserts"] for s in stats)
    n_undos = sum(s["n_undos"] for s in stats)
    ranks = [r for s in stats for r in s["accepted_ranks"]]
    return {
        "n_requests": n_requests,
        "n_proposals": n_proposals,
        "list_acceptance": _ratio(sum(s["accepted_list"] for s in stats), n_requests),
        "item_accept_rate": _ratio(n_accepts, n_proposals),
        "undo_per_insert": _ratio(n_undos, n_inserts),
        "preview_reject_rate": _ratio(
            sum(s["n_preview_rejected"] for s in stats),
            sum(s["n_previewed"] for s in stats),
        ),
        "mean_accepted_rank": float(np.mean(ranks)) if ranks else None,
    }


def bootstrap_ci(stats, metric, rng, n_bootstrap=N_BOOTSTRAP, alpha=ALPHA):
    """Percentile CI, resampling whole requests with replacement."""
    if not stats:
        return None
    values = []
    indices = np.arange(len(stats))
    for _ in range(n_bootstrap):
        sample = [stats[i] for i in rng.choice(indices, size=len(indices))]
        value = _metrics_from_stats(sample)[metric]
        if value is not None:
            values.append(value)
    if not values:
        return None
    lo, hi = np.percentile(values, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"lo": float(lo), "hi": float(hi), "n_resamples": len(values)}


def analyze(requests, feedback):
    joined, orphans = join_events(requests, feedback)
    by_model = defaultdict(list)
    for req in joined:
        by_model[req.get("model_id_served", "unknown")].append(_request_stats(req))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    models = {}
    for model_id in sorted(by_model):
        stats = by_model[model_id]
        metrics = _metrics_from_stats(stats)
        metrics["ci"] = {
            "list_acceptance": bootstrap_ci(stats, "list_acceptance", rng),
            "undo_per_insert": bootstrap_ci(stats, "undo_per_insert", rng),
        }
        models[model_id] = metrics
    return {
        "models": models,
        "orphan_feedback_events": orphans,
        "n_bootstrap": N_BOOTSTRAP,
        "alpha": ALPHA,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "resampling_unit": "request",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", required=True)
    parser.add_argument("--feedback", required=True)
    parser.add_argument("--output", default="artifacts/telemetry-pilot/metrics.json")
    args = parser.parse_args()

    result = analyze(load_jsonl(args.requests), load_jsonl(args.feedback))
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {out}")
    for model_id, m in result["models"].items():
        print(
            f"{model_id}: {m['n_requests']} lists, "
            f"list_acceptance={m['list_acceptance']}, "
            f"undo_per_insert={m['undo_per_insert']}"
        )
    if result["orphan_feedback_events"]:
        print(f"WARNING: {result['orphan_feedback_events']} feedback events "
              "had no logged exposure (predate exposure logging?)")


if __name__ == "__main__":
    main()
