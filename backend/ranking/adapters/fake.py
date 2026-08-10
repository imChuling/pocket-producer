"""Deterministic fake adapter for tests and offline development.

Embeddings are seeded from a content hash, so identical inputs always map to
identical vectors and different inputs (almost surely) differ — without any
model download.
"""

import hashlib

import numpy as np

from ranking.adapters.base import RepresentationModelCard


class FakeAdapter:
    def __init__(
        self,
        dims: int = 16,
        revision: str = "sha256:fake",
        poison_with_nan: bool = False,
    ):
        self.model_card = RepresentationModelCard(
            model_id="fake-adapter",
            revision=revision,
            modality="audio_semantic",
            dims=dims,
            license="internal-test",
        )
        self._dims = dims
        self._poison_with_nan = poison_with_nan
        self.encode_calls = 0

    def _seeded_vector(self, payload: bytes) -> np.ndarray:
        seed = int.from_bytes(
            hashlib.sha256(payload).digest()[:8], "big", signed=False
        )
        rng = np.random.default_rng(seed)
        vector = rng.normal(size=self._dims)
        return vector / np.linalg.norm(vector)

    def encode_audio(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        self.encode_calls += 1
        payload = (
            str(sample_rate).encode()
            + np.ascontiguousarray(waveform, dtype=np.float32).tobytes()
        )
        vector = self._seeded_vector(payload)
        if self._poison_with_nan:
            vector = vector.copy()
            vector[0] = np.nan
        return vector

    def encode_text(self, texts: list[str]) -> np.ndarray:
        return np.stack(
            [self._seeded_vector(text.encode("utf-8")) for text in texts]
        )
