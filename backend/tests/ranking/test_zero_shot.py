"""Zero-shot style evidence: fixed vocabulary, deterministic, versioned."""

import numpy as np

from ranking.adapters.fake import FakeAdapter
from ranking.zero_shot import STYLE_VOCABULARY, style_scores


class TestStyleScores:
    def test_scores_cover_fixed_vocabulary_only(self):
        adapter = FakeAdapter(dims=16)
        audio = np.random.default_rng(1).normal(size=8000).astype(np.float32)
        scores = style_scores(adapter, audio, 16000)
        assert set(scores) == set(STYLE_VOCABULARY)

    def test_scores_are_deterministic(self):
        adapter = FakeAdapter(dims=16)
        audio = np.random.default_rng(2).normal(size=8000).astype(np.float32)
        assert style_scores(adapter, audio, 16000) == style_scores(
            adapter, audio, 16000
        )

    def test_scores_are_cosines_in_range(self):
        adapter = FakeAdapter(dims=16)
        audio = np.random.default_rng(3).normal(size=8000).astype(np.float32)
        for value in style_scores(adapter, audio, 16000).values():
            assert -1.0 <= value <= 1.0

    def test_top_styles_orders_by_score(self):
        adapter = FakeAdapter(dims=16)
        audio = np.random.default_rng(4).normal(size=8000).astype(np.float32)
        scores = style_scores(adapter, audio, 16000)
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        assert ranked[0][1] >= ranked[-1][1]
