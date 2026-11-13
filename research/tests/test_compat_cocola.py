"""COCOLA scorer: stable shapes, deterministic output, finite scores."""

import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import cocola_scorer  # noqa: E402

pytestmark = pytest.mark.skipif(
    not cocola_scorer.available(), reason="COCOLA repository or checkpoint not present"
)

pytest.importorskip("lightning")
pytest.importorskip("efficientnet_pytorch")


@pytest.fixture(scope="module")
def scorer():
    return cocola_scorer.CocolaScorer()


def _chord(seconds: float, sample_rate: int, root: float = 220.0) -> np.ndarray:
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    tones = sum(np.sin(2 * np.pi * root * r * t) for r in (1.0, 1.25, 1.5))
    return (0.2 * tones).astype(np.float32)


def test_embedding_shape_is_stable_across_rates_and_lengths(scorer):
    a = scorer.embed(_chord(10.0, 44100), 44100)
    b = scorer.embed(_chord(3.0, 16000), 16000)
    assert a.ndim == 1
    assert a.shape == b.shape


def test_same_input_gives_the_same_embedding(scorer):
    audio = _chord(10.0, 22050)
    first = scorer.embed(audio, 22050)
    second = scorer.embed(audio, 22050)
    assert np.allclose(first.numpy(), second.numpy())


def test_score_is_a_finite_float(scorer):
    context = scorer.embed(_chord(10.0, 16000, root=220.0), 16000)
    candidate = scorer.embed(_chord(10.0, 16000, root=330.0), 16000)
    value = scorer.score(context, candidate)
    assert isinstance(value, float)
    assert np.isfinite(value)


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        cocola_scorer.CocolaScorer(mode="drums")
