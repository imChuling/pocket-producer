"""COCOLA coherence as a scorer for the behavioural tests.

Loads the COCOLA_HP_v1 checkpoint from a sibling checkout of the COCOLA
repository and exposes it as embed + score, following
research/cocola_heldout_eval.py: 16 kHz mono input, the first five seconds
of the clip (zero-padded if shorter), harmonic/percussive mel features,
encoder + layer norm + tanh, and the model's bilinear pairwise similarity.
"""

import pathlib
import sys

import numpy as np

COCOLA_ROOT = pathlib.Path(__file__).resolve().parents[4] / "cocola"
CHECKPOINT = COCOLA_ROOT / "COCOLA_HP_v1.ckpt"
SAMPLE_RATE = 16000
CLIP_SECONDS = 5
CLIP_SAMPLES = SAMPLE_RATE * CLIP_SECONDS
MODES = ("both", "harmonic", "percussive")


def available(root: pathlib.Path = COCOLA_ROOT) -> bool:
    return (root / "contrastive_model").is_dir() and (root / "COCOLA_HP_v1.ckpt").is_file()


class CocolaScorer:
    """Lazily loaded COCOLA model; `mode` masks the other HPSS channel."""

    def __init__(self, mode: str = "both", root: pathlib.Path = COCOLA_ROOT):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        self.mode = mode
        self.root = pathlib.Path(root)
        self._model = None
        self._extractor = None

    def _load(self):
        if self._model is not None:
            return
        import torch

        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from contrastive_model import constants
        from contrastive_model.contrastive_model import CoCola
        from feature_extraction.feature_extraction import CoColaFeatureExtractor

        torch.serialization.add_safe_globals([
            constants.EmbeddingMode,
            constants.ModelInputType,
            constants.Dataset,
            constants.ModelFeatureExtractorType,
            constants.FeatureExtractionTime,
        ])
        model = CoCola.load_from_checkpoint(
            str(self.root / "COCOLA_HP_v1.ckpt"), map_location="cpu"
        )
        model.eval()
        model.set_embedding_mode({
            "both": constants.EmbeddingMode.BOTH,
            "harmonic": constants.EmbeddingMode.HARMONIC,
            "percussive": constants.EmbeddingMode.PERCUSSIVE,
        }[self.mode])
        self._model = model
        self._extractor = CoColaFeatureExtractor()

    def embed(self, audio: np.ndarray, sample_rate: int):
        """Embedding of the first five seconds of `audio`, resampled to 16 kHz.

        Clips shorter than five seconds are zero-padded at the end. For a
        ten-second analysis window this means only its first half is heard.
        """
        import librosa
        import torch

        self._load()
        mono = np.asarray(audio, dtype=np.float32).reshape(-1)
        if sample_rate != SAMPLE_RATE:
            mono = librosa.resample(mono, orig_sr=sample_rate, target_sr=SAMPLE_RATE)
        clip = np.zeros(CLIP_SAMPLES, dtype=np.float32)
        clip[: min(CLIP_SAMPLES, mono.shape[0])] = mono[:CLIP_SAMPLES]
        features = self._extractor(torch.from_numpy(clip).unsqueeze(0))
        with torch.no_grad():
            embedding = self._model.encoder(features.unsqueeze(0).float())
            embedding = self._model.tanh(self._model.layer_norm(embedding))
        return embedding.squeeze(0)

    def score(self, context_embedding, candidate_embedding) -> float:
        """COCOLA pairwise score of a candidate against a context (higher fits better)."""
        import torch

        self._load()
        with torch.no_grad():
            value = self._model.similarity.pairwise(
                candidate_embedding.unsqueeze(0), context_embedding.unsqueeze(0)
            )
        return float(value.squeeze())
