"""MERT adapter smoke tests.

The real model needs a one-time weight download, so these tests only run when
POCKET_RESEARCH_MODELS=1 is set. Protocol-level behavior is covered by the
fake-adapter tests; the always-on tests below need no weights.
"""

import os

import numpy as np
import pytest

from ranking.adapters.base import AudioRepresentationAdapter
from ranking.adapters.mert import MertAdapter


def test_import_does_not_load_weights():
    adapter = MertAdapter()
    assert adapter._model is None
    assert adapter.model_card.revision == "unresolved-until-first-load"
    assert adapter.model_card.dims == 768
    assert adapter.model_card.modality == "audio_music"
    assert isinstance(adapter, AudioRepresentationAdapter)


def test_text_tower_absent():
    assert MertAdapter().encode_text(["a prompt"]) is None


pytest.importorskip("transformers")

if os.environ.get("POCKET_RESEARCH_MODELS") != "1":
    pytest.skip(
        "set POCKET_RESEARCH_MODELS=1 to run real-model smoke tests",
        allow_module_level=True,
    )

from ranking.adapters.base import encode_with_lineage  # noqa: E402


@pytest.fixture(scope="module")
def adapter() -> MertAdapter:
    return MertAdapter()


def tone(freq: float, seconds: float = 2.0, sr: int = 44100) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (0.4 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_audio_embedding_is_finite_unit_norm_768d(adapter):
    record = encode_with_lineage(adapter, tone(220), 44100)
    assert record.dims == 768
    assert record.revision.startswith("hf")
    vector = np.asarray(record.vector)
    assert np.all(np.isfinite(vector))
    assert np.isclose(np.linalg.norm(vector), 1.0, atol=1e-5)


def test_different_audio_gives_different_embeddings(adapter):
    a = adapter.encode_audio(tone(220), 44100)
    b = adapter.encode_audio(tone(880), 44100)
    assert float(np.dot(a, b)) < 0.999
