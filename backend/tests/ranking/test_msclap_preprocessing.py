"""What the MS-CLAP adapter writes to disk before the model sees it.

No model weights involved: the model is replaced by a probe that reads the
temporary wav back and reports its shape.
"""

import numpy as np
import pytest
import soundfile

from ranking.adapters.msclap import MAX_SECONDS, MsClapAdapter, prepare_waveform

SR = 48000


class _ProbeModel:
    def __init__(self):
        self.seen = []

    def get_audio_embeddings(self, paths):
        audio, sr = soundfile.read(paths[0], dtype="float32", always_2d=True)
        self.seen.append((audio.shape, sr))
        return np.ones((1, 1024), dtype=np.float32)


def adapter_with_probe():
    adapter = MsClapAdapter()
    adapter._model = _ProbeModel()
    return adapter


def test_stereo_is_downmixed_not_interleaved():
    left = np.full(SR, 0.5, dtype=np.float32)
    right = np.full(SR, -0.5, dtype=np.float32)
    stereo = np.stack([left, right], axis=1)  # (frames, channels) as soundfile returns
    mono = prepare_waveform(stereo, SR)
    assert mono.shape == (SR,)
    assert np.allclose(mono, 0.0)


def test_channels_first_layout_is_downmixed_too():
    left = np.full(SR, 0.5, dtype=np.float32)
    right = np.full(SR, -0.5, dtype=np.float32)
    channels_first = np.stack([left, right], axis=0)
    mono = prepare_waveform(channels_first, SR)
    assert mono.shape == (SR,)
    assert np.allclose(mono, 0.0)


def test_long_clips_are_cropped_to_the_model_window_deterministically():
    twenty_seconds = np.random.default_rng(0).normal(size=20 * SR).astype(np.float32)
    first = prepare_waveform(twenty_seconds, SR)
    second = prepare_waveform(twenty_seconds, SR)
    assert first.shape == (MAX_SECONDS * SR,)
    assert np.array_equal(first, second)
    assert np.array_equal(first, twenty_seconds[: MAX_SECONDS * SR])


def test_short_clips_are_left_alone():
    two_seconds = np.zeros(2 * SR, dtype=np.float32)
    assert prepare_waveform(two_seconds, SR).shape == (2 * SR,)


def test_adapter_writes_mono_window_for_the_model():
    adapter = adapter_with_probe()
    stereo = np.zeros((20 * SR, 2), dtype=np.float32)
    vector = adapter.encode_audio(stereo, SR)
    (shape, sr), = adapter._model.seen
    assert shape == (MAX_SECONDS * SR, 1)
    assert sr == SR
    assert pytest.approx(float(np.linalg.norm(vector))) == 1.0
