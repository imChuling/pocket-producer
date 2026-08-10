"""MS-CLAP adapter smoke tests.

The real model needs a one-time weight download, so these tests only run when
POCKET_RESEARCH_MODELS=1 is set. Everything protocol-level is already covered
by the fake-adapter tests.
"""

import os

import numpy as np
import pytest

pytest.importorskip("msclap")

if os.environ.get("POCKET_RESEARCH_MODELS") != "1":
    pytest.skip(
        "set POCKET_RESEARCH_MODELS=1 to run real-model smoke tests",
        allow_module_level=True,
    )

from ranking.adapters.base import encode_with_lineage
from ranking.adapters.msclap import MsClapAdapter
from ranking.zero_shot import style_scores


@pytest.fixture(scope="module")
def adapter() -> MsClapAdapter:
    return MsClapAdapter()


def tone(freq: float, seconds: float = 2.0, sr: int = 44100) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (0.4 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_audio_embedding_is_finite_unit_norm_1024d(adapter):
    record = encode_with_lineage(adapter, tone(220), 44100)
    assert record.dims == 1024
    assert record.revision.startswith("sha256:")
    vector = np.asarray(record.vector)
    assert np.all(np.isfinite(vector))
    assert pytest.approx(float(np.linalg.norm(vector)), abs=1e-3) == 1.0


def test_text_and_audio_live_in_comparable_space(adapter):
    texts = adapter.encode_text(["a low bass tone", "loud applause"])
    audio = adapter.encode_audio(tone(80, seconds=2.0), 44100)
    similarities = texts @ audio
    assert np.all(np.isfinite(similarities))


def test_style_scores_run_on_real_model(adapter):
    scores = style_scores(adapter, tone(440), 44100)
    assert len(scores) > 0
    assert all(np.isfinite(v) for v in scores.values())
