"""MS-CLAP 2023 adapter (frozen).

First deployment candidate from the bake-off shortlist: MIT-licensed repo,
native audio+text towers, small enough for CPU inference. Weights are
downloaded once on first use; loading is lazy so importing this module never
triggers a download.
"""

import hashlib
import tempfile
from pathlib import Path

import numpy as np

from ranking.adapters.base import RepresentationModelCard

_MSCLAP_VERSION = "2023"


def _weights_revision(model) -> str:
    """Pin the revision to the checkpoint file hash when it is discoverable."""
    for attribute in ("model_fp", "weights_path", "ckpt_path"):
        path = getattr(model, attribute, None)
        if path and Path(str(path)).exists():
            digest = hashlib.sha256(Path(str(path)).read_bytes()).hexdigest()
            return f"sha256:{digest}"
    return f"msclap-package-{_MSCLAP_VERSION}"


class MsClapAdapter:
    def __init__(self):
        self._model = None
        self.model_card = RepresentationModelCard(
            model_id=f"msclap-{_MSCLAP_VERSION}",
            revision="unresolved-until-first-load",
            modality="audio_semantic",
            dims=1024,
            license="MIT repository; weights/training-data audit tracked in DATA_CREDITS.md",
        )

    def _load(self):
        if self._model is None:
            from msclap import CLAP

            self._model = CLAP(version=_MSCLAP_VERSION, use_cuda=False)
            self.model_card = RepresentationModelCard(
                model_id=self.model_card.model_id,
                revision=_weights_revision(self._model),
                modality=self.model_card.modality,
                dims=self.model_card.dims,
                license=self.model_card.license,
            )
        return self._model

    def encode_audio(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        import soundfile

        model = self._load()
        mono = np.asarray(waveform, dtype=np.float32).reshape(-1)
        with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
            soundfile.write(handle.name, mono, sample_rate)
            embeddings = model.get_audio_embeddings([handle.name])
        vector = np.asarray(embeddings).reshape(-1)
        return vector / np.linalg.norm(vector)

    def encode_text(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        embeddings = np.asarray(model.get_text_embeddings(texts))
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / norms
