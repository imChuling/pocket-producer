"""Adapter protocol tests, driven entirely by the deterministic fake adapter."""

import numpy as np
import pytest

from ranking.adapters.base import (
    EmbeddingCache,
    encode_with_lineage,
    pool_windows_mean_l2,
)
from ranking.adapters.fake import FakeAdapter


def sine_wave(freq: float = 440.0, seconds: float = 1.0, sr: int = 16000):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


class TestFakeAdapter:
    def test_same_audio_same_embedding(self):
        adapter = FakeAdapter(dims=8)
        wave = sine_wave()
        first = adapter.encode_audio(wave, 16000)
        second = adapter.encode_audio(wave, 16000)
        np.testing.assert_array_equal(first, second)

    def test_different_audio_different_embedding(self):
        adapter = FakeAdapter(dims=8)
        a = adapter.encode_audio(sine_wave(440), 16000)
        b = adapter.encode_audio(sine_wave(880), 16000)
        assert not np.array_equal(a, b)

    def test_text_encoding_available_and_deterministic(self):
        adapter = FakeAdapter(dims=8)
        first = adapter.encode_text(["dark bass"])
        second = adapter.encode_text(["dark bass"])
        np.testing.assert_array_equal(first, second)


class TestEncodeWithLineage:
    def test_record_carries_full_lineage(self):
        adapter = FakeAdapter(dims=8)
        record = encode_with_lineage(adapter, sine_wave(), 16000)
        assert record.model_id == adapter.model_card.model_id
        assert record.revision == adapter.model_card.revision
        assert record.dims == 8
        assert len(record.input_sha256) == 64
        assert record.sample_rate == 16000

    def test_nan_output_rejected(self):
        adapter = FakeAdapter(dims=8, poison_with_nan=True)
        with pytest.raises(ValueError, match="non-finite"):
            encode_with_lineage(adapter, sine_wave(), 16000)


class TestEmbeddingCache:
    def test_identical_input_hits_cache_without_recompute(self):
        adapter = FakeAdapter(dims=8)
        cache = EmbeddingCache()
        wave = sine_wave()
        first = cache.get_or_encode(adapter, wave, 16000)
        calls_after_first = adapter.encode_calls
        second = cache.get_or_encode(adapter, wave, 16000)
        assert adapter.encode_calls == calls_after_first
        assert first.vector == second.vector

    def test_different_model_revision_is_a_cache_miss(self):
        wave = sine_wave()
        cache = EmbeddingCache()
        a = FakeAdapter(dims=8, revision="sha256:aaa")
        b = FakeAdapter(dims=8, revision="sha256:bbb")
        cache.get_or_encode(a, wave, 16000)
        cache.get_or_encode(b, wave, 16000)
        assert b.encode_calls == 1


class TestPooling:
    def test_pooled_vector_is_l2_normalized(self):
        windows = np.stack([np.ones(4), np.zeros(4) + 3.0])
        pooled = pool_windows_mean_l2(windows)
        assert pytest.approx(float(np.linalg.norm(pooled)), abs=1e-6) == 1.0

    def test_window_order_does_not_matter(self):
        w1 = np.random.default_rng(0).normal(size=(3, 4))
        pooled_a = pool_windows_mean_l2(w1)
        pooled_b = pool_windows_mean_l2(w1[::-1])
        np.testing.assert_allclose(pooled_a, pooled_b, atol=1e-12)

    def test_zero_vector_rejected(self):
        with pytest.raises(ValueError):
            pool_windows_mean_l2(np.zeros((2, 4)))
