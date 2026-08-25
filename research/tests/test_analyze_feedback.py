import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from analyze_feedback import analyze, join_events


def _request(request_id, model="rules-v1", fragments=("f1", "f2", "f3")):
    return {
        "request_id": request_id,
        "model_id_served": model,
        "fragment_ids": list(fragments),
    }


def _event(request_id, fragment_id, event, rank=1):
    return {
        "request_id": request_id,
        "fragment_id": fragment_id,
        "event": event,
        "rank_position": rank,
    }


def test_join_drops_and_counts_orphans():
    joined, orphans = join_events(
        [_request("r1")], [_event("r1", "f1", "accept"), _event("rX", "f1", "accept")]
    )
    assert orphans == 1
    assert len(joined[0]["events"]) == 1


def test_metrics_basic_rates():
    requests = [_request("r1"), _request("r2")]
    feedback = [
        _event("r1", "f1", "preview", rank=1),
        _event("r1", "f1", "insert", rank=1),
        _event("r1", "f2", "preview", rank=2),
        _event("r1", "f2", "reject", rank=2),
        # r2: no interaction at all
    ]
    m = analyze(requests, feedback)["models"]["rules-v1"]
    assert m["n_requests"] == 2
    assert m["n_proposals"] == 6
    assert m["list_acceptance"] == 0.5
    assert m["item_accept_rate"] == 1 / 6
    assert m["undo_per_insert"] == 0.0
    assert m["preview_reject_rate"] == 0.5
    assert m["mean_accepted_rank"] == 1.0


def test_undo_per_insert_and_model_split():
    requests = [_request("r1", model="fusion-5sig"), _request("r2", model="rules-v1")]
    feedback = [
        _event("r1", "f1", "insert"),
        _event("r1", "f1", "undo"),
        _event("r2", "f3", "accept", rank=3),
    ]
    models = analyze(requests, feedback)["models"]
    assert models["fusion-5sig"]["undo_per_insert"] == 1.0
    assert models["rules-v1"]["undo_per_insert"] is None  # no inserts
    assert models["rules-v1"]["mean_accepted_rank"] == 3.0


def test_empty_denominators_are_none_not_zero_division():
    result = analyze([_request("r1", fragments=())], [])
    m = result["models"]["rules-v1"]
    assert m["item_accept_rate"] is None
    assert m["preview_reject_rate"] is None
    assert m["mean_accepted_rank"] is None


def test_bootstrap_ci_present_and_ordered():
    requests = [_request(f"r{i}") for i in range(10)]
    feedback = [_event(f"r{i}", "f1", "accept") for i in range(5)]
    m = analyze(requests, feedback)["models"]["rules-v1"]
    ci = m["ci"]["list_acceptance"]
    assert ci is not None
    assert 0.0 <= ci["lo"] <= 0.5 <= ci["hi"] <= 1.0
