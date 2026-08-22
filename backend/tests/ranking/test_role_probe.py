"""Tests for zero-shot instrument-role classification probe."""

import numpy as np

from ranking.role_probe import CONFIDENCE_THRESHOLD, ROLE_VOCAB, RoleProbe


def _make_probe(n_dims: int = 8) -> RoleProbe:
    """Probe with synthetic orthogonal prompt embeddings."""
    rng = np.random.default_rng(42)
    n_roles = len(ROLE_VOCAB)
    prompts = rng.standard_normal((n_roles, n_dims))
    for i in range(n_roles):
        prompts[i] /= np.linalg.norm(prompts[i])
    return RoleProbe(prompts)


def _aligned_embedding(probe: RoleProbe, role_idx: int) -> np.ndarray:
    """Embedding aligned with a specific role's prompt direction."""
    noise = np.random.default_rng(99).normal(0, 0.01, probe._prompts.shape[1])
    return probe._prompts[role_idx] + noise


class TestRoleProbe:
    def test_classify_returns_valid_role(self):
        probe = _make_probe()
        role, conf = probe.classify(np.ones(8))
        assert role in ROLE_VOCAB
        assert 0.0 <= conf <= 1.0

    def test_aligned_embedding_classifies_correctly(self):
        probe = _make_probe(32)
        for i, expected_role in enumerate(ROLE_VOCAB):
            emb = probe._prompts[i] * 10
            role, conf = probe.classify(emb)
            assert role == expected_role

    def test_zero_embedding_returns_zero_confidence(self):
        probe = _make_probe()
        role, conf = probe.classify(np.zeros(8))
        assert conf == 0.0

    def test_confidence_sums_to_one(self):
        probe = _make_probe()
        emb = np.ones(8)
        audio = np.asarray(emb, dtype=np.float64)
        audio = audio / np.linalg.norm(audio)
        cosines = probe._prompts @ audio
        shifted = cosines - cosines.max()
        probs = np.exp(shifted) / np.exp(shifted).sum()
        assert abs(probs.sum() - 1.0) < 1e-10

    def test_threshold_boundary(self):
        probe = _make_probe(32)
        emb = probe._prompts[0] * 10
        _, conf = probe.classify(emb)
        assert conf >= CONFIDENCE_THRESHOLD


class TestSessionRoles:
    def test_present_roles_above_threshold(self):
        probe = _make_probe(32)
        embs = [probe._prompts[0] * 10, probe._prompts[1] * 10]
        present = probe.session_roles(embs)
        assert len(present) >= 1
        for role, conf in present.items():
            assert role in ROLE_VOCAB
            assert conf >= CONFIDENCE_THRESHOLD

    def test_empty_session_returns_empty(self):
        probe = _make_probe()
        present = probe.session_roles([])
        assert present == {}

    def test_max_confidence_per_role(self):
        probe = _make_probe(32)
        emb = probe._prompts[0] * 10
        present = probe.session_roles([emb, emb * 0.5])
        role = list(present.keys())[0]
        _, conf1 = probe.classify(emb)
        _, conf2 = probe.classify(emb * 0.5)
        assert present[role] == max(conf1, conf2)


class TestGapScore:
    def test_missing_role_returns_positive(self):
        probe = _make_probe(32)
        session_roles = {ROLE_VOCAB[0]: 0.5}
        candidate_emb = probe._prompts[1] * 10
        role, score = probe.gap_score(candidate_emb, session_roles)
        assert role is not None
        assert score > 0

    def test_present_role_returns_zero(self):
        probe = _make_probe(32)
        session_roles = {ROLE_VOCAB[0]: 0.5}
        candidate_emb = probe._prompts[0] * 10
        role, score = probe.gap_score(candidate_emb, session_roles)
        assert role is None
        assert score == 0.0

    def test_all_roles_filled_returns_zero(self):
        probe = _make_probe(32)
        session_roles = {r: 0.5 for r in ROLE_VOCAB}
        candidate_emb = probe._prompts[0] * 10
        role, score = probe.gap_score(candidate_emb, session_roles)
        assert role is None
        assert score == 0.0
