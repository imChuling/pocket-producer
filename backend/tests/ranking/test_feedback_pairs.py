"""Decision pairs from proposal logs, and anchored fine-tuning of the fusion."""

import numpy as np

from ranking.research.feedback_pairs import (
    build_feedback_pairs,
    finetune_weights,
    pairwise_accuracy,
)

SIG_A = [0.9, 0.9, 1.0, 0.0, 0.5]
SIG_B = [0.2, 0.3, 0.0, 0.0, 0.0]
SIG_C = [0.5, 0.6, 1.0, 0.0, 0.0]


def served(request_id, ids, signals, model_id="fusion-5sig-v1"):
    return {
        "request_id": request_id,
        "model_id_served": model_id,
        "fragment_ids": ids,
        "candidate_signals": signals,
    }


def event(request_id, fragment_id, name):
    return {"request_id": request_id, "fragment_id": fragment_id, "event": name}


def test_accept_vs_reject_within_one_list_forms_a_pair():
    pairs = build_feedback_pairs(
        [served("r1", ["a", "b", "c"], [SIG_A, SIG_B, SIG_C])],
        [event("r1", "a", "preview"), event("r1", "a", "insert"), event("r1", "b", "reject")],
    )
    assert [(p["positive"], p["negative"]) for p in pairs] == [("a", "b")]
    assert pairs[0]["pos"] == SIG_A and pairs[0]["neg"] == SIG_B


def test_undo_cancels_the_positive_and_preview_is_not_a_decision():
    pairs = build_feedback_pairs(
        [served("r1", ["a", "b", "c"], [SIG_A, SIG_B, SIG_C])],
        [
            event("r1", "a", "insert"),
            event("r1", "a", "undo"),
            event("r1", "c", "preview"),
            event("r1", "b", "reject"),
        ],
    )
    assert pairs == []


def test_reject_then_insert_counts_as_positive_only():
    pairs = build_feedback_pairs(
        [served("r1", ["a", "b"], [SIG_A, SIG_B])],
        [event("r1", "a", "reject"), event("r1", "a", "insert"), event("r1", "b", "reject")],
    )
    assert [(p["positive"], p["negative"]) for p in pairs] == [("a", "b")]


def test_lists_from_other_models_or_without_signals_are_skipped():
    pairs = build_feedback_pairs(
        [
            served("rules", ["a", "b"], [None, None], model_id="rules-v1"),
            served("nosig", ["a", "b"], [None, None]),
            served("short", ["a", "b"], [SIG_A]),
        ],
        [event(r, "a", "insert") for r in ("rules", "nosig", "short")]
        + [event(r, "b", "reject") for r in ("rules", "nosig", "short")],
    )
    assert pairs == []


def test_events_without_a_logged_exposure_are_dropped():
    pairs = build_feedback_pairs(
        [served("r1", ["a", "b"], [SIG_A, SIG_B])],
        [event("ghost", "a", "insert"), event("ghost", "b", "reject")],
    )
    assert pairs == []


def test_finetune_moves_toward_decisions_but_stays_anchored():
    # Decisions contradict w0 on the tempo signal: musicians keep rejecting
    # the tempo-matched fragment in favour of the timbral match.
    w0 = np.array([1.0, 1.0, 4.0, 0.0, 1.0])
    pos = [0.9, 0.9, 0.0, 0.0, 0.0]
    neg = [0.4, 0.4, 1.0, 0.0, 0.0]
    pairs = [{"request_id": f"r{i}", "positive": "p", "negative": "n", "pos": pos, "neg": neg}
             for i in range(30)]
    assert pairwise_accuracy(w0, pairs) == 0.0

    w_free = finetune_weights(w0, pairs, seed=1, lr=0.05, epochs=100, l2=0.0)
    assert pairwise_accuracy(w_free, pairs) == 1.0

    w_anchored = finetune_weights(w0, pairs, seed=1, lr=0.05, epochs=100, l2=50.0)
    assert np.linalg.norm(w_anchored - w0) < np.linalg.norm(w_free - w0)


def test_finetune_is_deterministic_for_a_seed():
    w0 = np.array([1.0, 1.0, 1.0, 0.0, 1.0])
    pairs = [{"request_id": "r", "positive": "p", "negative": "n", "pos": SIG_A, "neg": SIG_B}]
    first = finetune_weights(w0, pairs, seed=7)
    second = finetune_weights(w0, pairs, seed=7)
    assert np.array_equal(first, second)


def test_pairwise_accuracy_counts_ties_as_half():
    pairs = [{"request_id": "r", "positive": "p", "negative": "n", "pos": SIG_A, "neg": SIG_A}]
    assert pairwise_accuracy(np.ones(5), pairs) == 0.5
    assert pairwise_accuracy(np.ones(5), []) is None
