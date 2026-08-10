"""LAION-CLAP music adapter (frozen challenger).

Music-specific checkpoint from the LAION-CLAP release. Code repository is
CC0; the training audio provenance is complex (DATA_CREDITS.md), so this
backbone is a research challenger, not a deployment default. Weights download
once to a local cache; revision is pinned to the checkpoint file hash.
"""

import hashlib
import pathlib

import numpy as np

from ranking.adapters.base import RepresentationModelCard

CHECKPOINT_URL = (
    "https://huggingface.co/lukewys/laion_clap/resolve/main/"
    "music_audioset_epoch_15_esc_90.14.pt"
)
CACHE_DIR = pathlib.Path.home() / ".cache" / "pocket-producer"
TARGET_SR = 48000


class LaionClapMusicAdapter:
    def __init__(self):
        self._model = None
        self.model_card = RepresentationModelCard(
            model_id="laion-clap-music",
            revision="unresolved-until-first-load",
            modality="audio_semantic",
            dims=512,
            license="CC0 code; training-data provenance complex — research challenger only",
            expected_sample_rate=TARGET_SR,
        )

    def _checkpoint_path(self) -> pathlib.Path:
        path = CACHE_DIR / "music_audioset_epoch_15_esc_90.14.pt"
        if not path.exists():
            import requests

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with requests.get(CHECKPOINT_URL, stream=True, timeout=600) as response:
                response.raise_for_status()
                partial = path.with_suffix(".partial")
                with partial.open("wb") as sink:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        sink.write(chunk)
                partial.rename(path)
        return path

    def _load(self):
        if self._model is None:
            import laion_clap

            checkpoint = self._checkpoint_path()
            model = laion_clap.CLAP_Module(
                enable_fusion=False, amodel="HTSAT-base"
            )
            model.load_ckpt(str(checkpoint))
            self._model = model
            digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            self.model_card = RepresentationModelCard(
                model_id=self.model_card.model_id,
                revision=f"sha256:{digest}",
                modality=self.model_card.modality,
                dims=self.model_card.dims,
                license=self.model_card.license,
                expected_sample_rate=TARGET_SR,
            )
        return self._model

    def encode_audio(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        import librosa

        model = self._load()
        mono = np.asarray(waveform, dtype=np.float32).reshape(-1)
        if sample_rate != TARGET_SR:
            mono = librosa.resample(
                mono, orig_sr=sample_rate, target_sr=TARGET_SR
            )
        embedding = model.get_audio_embedding_from_data(
            x=mono[np.newaxis, :], use_tensor=False
        )
        vector = np.asarray(embedding).reshape(-1)
        return vector / np.linalg.norm(vector)

    def encode_text(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        embeddings = np.asarray(model.get_text_embedding(texts, use_tensor=False))
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / norms
