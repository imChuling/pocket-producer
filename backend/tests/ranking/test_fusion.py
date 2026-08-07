"""Tests for BPR logistic fusion training and evaluation."""

import numpy as np
import pytest


def _train_logistic(train, feature_idx, seed, epochs=300, lr=0.05):
    """Local copy of run_fusion.train_logistic for testing without importing
    the research script (which has side effects on sys.path)."""
    rng = np.random.default_rng(seed)
    dim = len(feature_idx)
    w = np.zeros(dim)
    m_w = np.zeros(dim)
    v_w = np.zeros(dim)
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
                grad = -(1.0 - sig) * diff
                t += 1
                m_w = beta1 * m_w + (1 - beta1) * grad
                v_w = beta2 * v_w + (1 - beta2) * grad**2
                m_hat = m_w / (1 - beta1**t)
                v_hat = v_w / (1 - beta2**t)
                w -= lr * m_hat / (np.sqrt(v_hat) + eps)
    return w


def _evaluate(examples, w, feature_idx):
    wins, total = 0.0, 0
    for ex in examples:
        sp = w @ ex["pos"][feature_idx]
        for neg in ex["negs"]:
            sn = w @ neg[feature_idx]
            wins += 1.0 if sp > sn else (0.5 if sp == sn else 0.0)
            total += 1
    return wins / total if total else 0.0


def _make_separable_data(n=100, seed=42):
    """Synthetic data where signal[0] perfectly separates pos from neg."""
    rng = np.random.default_rng(seed)
    examples = []
    for _ in range(n):
        pos = np.array([1.0, rng.random()])
        neg = np.array([0.0, rng.random()])
        examples.append({
            "pos": pos,
            "negs": [neg],
            "neg_types": ["easy"],
            "source_id": "s0",
        })
    return examples


def _make_complementary_data(n=100, seed=42):
    """Data where signal[0] alone fails on 50% but signal[1] rescues."""
    rng = np.random.default_rng(seed)
    examples = []
    for i in range(n):
        if i % 2 == 0:
            pos = np.array([1.0, 0.5])
            neg = np.array([0.0, 0.5])
        else:
            pos = np.array([0.5, 1.0])
            neg = np.array([0.5, 0.0])
        examples.append({
            "pos": pos,
            "negs": [neg],
            "neg_types": ["hard"],
            "source_id": "s0",
        })
    return examples


class TestBPRTraining:
    def test_converges_on_separable_data(self):
        data = _make_separable_data()
        fidx = np.array([0, 1])
        w = _train_logistic(data, fidx, seed=42)
        acc = _evaluate(data, w, fidx)
        assert acc > 0.95

    def test_weight_direction_correct(self):
        data = _make_separable_data()
        fidx = np.array([0, 1])
        w = _train_logistic(data, fidx, seed=42)
        assert w[0] > 0

    def test_complementary_signals_fused(self):
        data = _make_complementary_data()
        fidx = np.array([0, 1])
        w = _train_logistic(data, fidx, seed=42)
        acc = _evaluate(data, w, fidx)
        assert acc > 0.9
        assert w[0] > 0 and w[1] > 0

    def test_single_signal_perfect(self):
        data = _make_separable_data()
        fidx = np.array([0])
        w = _train_logistic(data, fidx, seed=42)
        acc = _evaluate(data, w, fidx)
        assert acc == 1.0

    def test_deterministic_across_runs(self):
        data = _make_separable_data()
        fidx = np.array([0, 1])
        w1 = _train_logistic(data, fidx, seed=42)
        w2 = _train_logistic(data, fidx, seed=42)
        np.testing.assert_array_equal(w1, w2)


class TestEvaluation:
    def test_perfect_ordering(self):
        examples = [{
            "pos": np.array([1.0]),
            "negs": [np.array([0.0])],
            "neg_types": ["easy"],
            "source_id": "s0",
        }]
        acc = _evaluate(examples, np.array([1.0]), np.array([0]))
        assert acc == 1.0

    def test_tie_scores_half(self):
        examples = [{
            "pos": np.array([0.5]),
            "negs": [np.array([0.5])],
            "neg_types": ["easy"],
            "source_id": "s0",
        }]
        acc = _evaluate(examples, np.array([1.0]), np.array([0]))
        assert acc == 0.5

    def test_inverted_ordering(self):
        examples = [{
            "pos": np.array([0.0]),
            "negs": [np.array([1.0])],
            "neg_types": ["easy"],
            "source_id": "s0",
        }]
        acc = _evaluate(examples, np.array([1.0]), np.array([0]))
        assert acc == 0.0
