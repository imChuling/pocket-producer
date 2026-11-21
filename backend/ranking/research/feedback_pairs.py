"""Preference pairs from logged proposals and musician decisions.

Joins ranking_requests (served lists with per-candidate signal vectors) and
ranking_feedback (preview / accept / reject / insert / undo) by request_id.
Within one served list, a positive needs at least one retained insertion.
An explicitly rejected fragment with no accept or insert provides a negative.
Lists served by another model, or logged without signal vectors, contribute nothing.

These pairs are the interaction-derived evidence the cold-start proxy is
meant to be replaced by, so fine-tuning starts from the deployed weights and
is pulled back toward them: with few decisions the result stays close to
the proxy-trained fusion instead of overfitting a handful of clicks.
"""

from collections import defaultdict

import numpy as np

from ranking.fusion_ranker import LOGGED_SIGNAL_NAMES, SIGNAL_NAMES
from ranking.research.feedback_outcomes import matches_participant, proposal_outcomes


def build_feedback_pairs(
    requests: list[dict],
    feedback: list[dict],
    model_id: str = "fusion-5sig-v1",
    *,
    signal_names: list[str] | None = None,
) -> list[dict]:
    requested = list(SIGNAL_NAMES if signal_names is None else signal_names)

    def validate_names(names):
        if (
            not names
            or any(not isinstance(n, str) or n not in LOGGED_SIGNAL_NAMES for n in names)
            or len(set(names)) != len(names)
        ):
            raise ValueError("signal names must be known, nonempty and unique")

    validate_names(requested)
    vectors_by_request: dict[str, dict[str, list[float]]] = {}
    participants = {}
    for req in requests:
        if req.get("model_id_served") != model_id:
            continue
        ids = req.get("fragment_ids") or []
        signals = req.get("candidate_signals") or []
        if len(signals) != len(ids):
            continue
        present = [sig for sig in signals if sig]
        if not present:
            continue
        names = req.get("candidate_signal_names")
        if names is None:
            if any(len(sig) != len(SIGNAL_NAMES) for sig in present):
                raise ValueError("unnamed extended signal vectors are ambiguous")
            names = SIGNAL_NAMES
            # Historical five-only lists cannot train newly introduced signals.
            if set(requested) - set(names):
                continue
        validate_names(names)
        if any(len(sig) != len(names) for sig in present):
            raise ValueError("signal names and vector lengths disagree")
        missing = set(requested) - set(names)
        if missing:
            raise ValueError(f"missing requested signals: {sorted(missing)}")
        indices = [names.index(name) for name in requested]
        masks = req.get("candidate_signal_available")
        if masks is not None:
            if len(masks) != len(ids):
                raise ValueError("signal availability masks must match named vectors")
            for mask in masks:
                if mask is not None and (
                    len(mask) != len(names) or any(type(v) is not bool for v in mask)
                ):
                    raise ValueError("signal availability masks must match named vectors")
        vectors = {}
        for i, (fid, sig) in enumerate(zip(ids, signals)):
            if not sig:
                continue
            if not np.isfinite(np.asarray(sig, dtype=np.float64)).all():
                raise ValueError("signal vectors must be finite")
            mask = masks[i] if masks is not None else None
            if mask is None and set(requested) - set(SIGNAL_NAMES):
                continue
            if mask is not None and not all(mask[j] for j in indices):
                continue
            vectors[fid] = [sig[j] for j in indices]
        if vectors:
            vectors_by_request[req["request_id"]] = vectors
            participants[req["request_id"]] = req.get("participant_hash")

    events = defaultdict(list)
    for event in feedback:
        request_id = event.get("request_id")
        if request_id in participants and matches_participant(event, participants[request_id]):
            events[request_id].append(event)

    pairs: list[dict] = []
    for request_id in sorted(events):
        vectors = vectors_by_request[request_id]
        outcomes = proposal_outcomes(vectors, events[request_id])
        positives = sorted(fid for fid, state in outcomes.items() if state.retained)
        negatives = sorted(
            fid for fid, state in outcomes.items() if state.rejected and not state.chosen
        )
        for positive in positives:
            for negative in negatives:
                pairs.append(
                    {
                        "request_id": request_id,
                        "positive": positive,
                        "negative": negative,
                        "pos": vectors[positive],
                        "neg": vectors[negative],
                    }
                )
    return pairs


def pairwise_accuracy(w, pairs: list[dict]) -> float | None:
    if not pairs:
        return None
    w = np.asarray(w, dtype=np.float64)
    wins = 0.0
    for pair in pairs:
        margin = w @ (np.asarray(pair["pos"]) - np.asarray(pair["neg"]))
        wins += 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
    return round(wins / len(pairs), 4)


def finetune_weights(
    w0,
    pairs: list[dict],
    seed: int,
    lr: float = 0.01,
    epochs: int = 50,
    l2: float = 1.0,
) -> np.ndarray:
    """BPR on decision pairs, warm-started at w0 and L2-anchored to it.

    Loss per pair: -log sigmoid(w . (pos - neg)) + (l2 / 2) * ||w - w0||^2.
    Same Adam settings as the offline trainer (research/run_fusion.py).
    """
    rng = np.random.default_rng(seed)
    w0 = np.asarray(w0, dtype=np.float64)
    w = w0.copy()
    diffs = [np.asarray(p["pos"], dtype=np.float64) - np.asarray(p["neg"], dtype=np.float64)
             for p in pairs]
    m_w = np.zeros_like(w)
    v_w = np.zeros_like(w)
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    t = 0
    for _ in range(epochs):
        for idx in rng.permutation(len(diffs)):
            diff = diffs[int(idx)]
            sig = 1.0 / (1.0 + np.exp(-(w @ diff)))
            grad = -(1.0 - sig) * diff + l2 * (w - w0)
            t += 1
            m_w = beta1 * m_w + (1 - beta1) * grad
            v_w = beta2 * v_w + (1 - beta2) * grad**2
            m_hat = m_w / (1 - beta1**t)
            v_hat = v_w / (1 - beta2**t)
            w -= lr * m_hat / (np.sqrt(v_hat) + eps)
    return w
