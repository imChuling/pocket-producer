"""Preference pairs from logged proposals and musician decisions.

Joins ranking_requests (served lists with per-candidate signal vectors) and
ranking_feedback (preview / accept / reject / insert / undo) by request_id.
Within one served list, a fragment the musician accepted or inserted and did
not undo is a positive; a fragment they rejected and never accepted is a
negative. Previews are not decisions. Lists served by another model, or
logged without signal vectors, contribute nothing.

These pairs are the interaction-derived evidence the cold-start proxy is
meant to be replaced by, so fine-tuning starts from the deployed weights and
is pulled back toward them: with few decisions the result stays close to
the proxy-trained fusion instead of overfitting a handful of clicks.
"""

import numpy as np

POSITIVE_EVENTS = frozenset({"accept", "insert"})
NEGATIVE_EVENTS = frozenset({"reject"})


def build_feedback_pairs(
    requests: list[dict], feedback: list[dict], model_id: str = "fusion-5sig-v1"
) -> list[dict]:
    vectors_by_request: dict[str, dict[str, list[float]]] = {}
    for req in requests:
        if req.get("model_id_served") != model_id:
            continue
        ids = req.get("fragment_ids") or []
        signals = req.get("candidate_signals") or []
        if len(signals) != len(ids):
            continue
        vectors = {fid: list(sig) for fid, sig in zip(ids, signals) if sig}
        if vectors:
            vectors_by_request[req["request_id"]] = vectors

    events: dict[str, dict[str, set[str]]] = {}
    for event in feedback:
        request_id = event.get("request_id")
        if request_id not in vectors_by_request:
            continue
        per_fragment = events.setdefault(request_id, {})
        per_fragment.setdefault(event.get("fragment_id"), set()).add(event.get("event"))

    pairs: list[dict] = []
    for request_id in sorted(events):
        vectors = vectors_by_request[request_id]
        per_fragment = events[request_id]
        positives = sorted(
            fid
            for fid, evs in per_fragment.items()
            if fid in vectors and evs & POSITIVE_EVENTS and "undo" not in evs
        )
        negatives = sorted(
            fid
            for fid, evs in per_fragment.items()
            if fid in vectors and evs & NEGATIVE_EVENTS and not evs & POSITIVE_EVENTS
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
