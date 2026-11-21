"""Aggregate proposal telemetry into per-model acceptance metrics.

Joins the served-list log (ranking_requests) with interaction events
(ranking_feedback), both as the JSONL files written by the export script,
which keeps only allowlisted fields and replaces user IDs with a salted hash:

  cd backend && FEEDBACK_EXPORT_SALT=... .venv/bin/python -m scripts.export_feedback \
    --out ../artifacts/feedback-export

Do not dump the raw collections: they hold user IDs. Keep the export local.

Per served model and implementation revision:
  n_requests            served lists (the exposure denominator)
  n_proposals           proposals shown (sum of list lengths)
  list_acceptance       fraction of lists with >=1 accept or insert
  item_accept_rate      unique chosen proposals (accept or insert) / proposals
  item_retained_rate    proposals with at least one remaining logged insert / proposals
  undo_per_insert       matched undone placements / successful logged placements
  preview_reject_rate   previewed proposals later rejected / previewed
  mean_accepted_rank    mean served rank over unique chosen proposals
Bootstrap CIs (percentile, resampled over requests) are reported for
list_acceptance and undo_per_insert.

Usage:
  backend/.venv/bin/python research/analyze_feedback.py \
    --requests artifacts/feedback-export/requests.jsonl \
    --feedback artifacts/feedback-export/feedback.jsonl \
    --output artifacts/telemetry-pilot/metrics.json
"""

import argparse
import json
import pathlib
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from ranking.research.feedback_outcomes import matches_participant, proposal_outcomes  # noqa: E402

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

    Count events lacking a matching exposure, including server-rejected
    attribution and differing participant hashes when both hashes exist.
    """
    by_request = {r["request_id"]: dict(r, events=[]) for r in requests}
    orphans = 0
    for event in feedback:
        req = by_request.get(event.get("request_id"))
        if req is None or not matches_participant(event, req.get("participant_hash")):
            orphans += 1
            continue
        req["events"].append(event)
    return list(by_request.values()), orphans


def _request_stats(req):
    """Per-request counters used by both point estimates and bootstrap."""
    fragments = req.get("fragment_ids", [])
    outcomes = proposal_outcomes(fragments, req["events"])
    ranks = [
        index for index, fid in enumerate(fragments, 1)
        if fid in outcomes and outcomes[fid].chosen
    ]
    return {
        "n_proposals": len(fragments),
        "accepted_list": int(bool(ranks)),
        "n_accepts": len(ranks),
        "n_retained": sum(s.retained for s in outcomes.values()),
        "n_inserts": sum(s.inserts for s in outcomes.values()),
        "n_undos": sum(s.undos for s in outcomes.values()),
        "n_previewed": sum(s.previewed for s in outcomes.values()),
        "n_preview_rejected": sum(s.rejected_after_preview for s in outcomes.values()),
        "accepted_ranks": ranks,
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
        "item_retained_rate": _ratio(sum(s["n_retained"] for s in stats), n_proposals),
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


def _served_model(req):
    model = req.get("model_id_served", "unknown")
    revision = req.get("implementation_revision")
    if model == "beat-fit-v1" and not revision:
        # Older exports identify the measurement, but not the exact code revision.
        names = req.get("candidate_signal_names")
        if names == ["chroma_beat_aligned", "onset_pattern"]:
            revision = "legacy-full-grid"
        elif names == ["chroma_beat_aligned", "onset_pattern_shared_beats"]:
            revision = "legacy-shared-beats"
        else:
            revision = "unknown-revision"
    return f"{model}/{revision}" if revision else model


def analyze(requests, feedback):
    joined, orphans = join_events(requests, feedback)
    by_model = defaultdict(list)
    for req in joined:
        by_model[_served_model(req)].append(_request_stats(req))
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
              "had no matching verified exposure for this participant")


if __name__ == "__main__":
    main()
