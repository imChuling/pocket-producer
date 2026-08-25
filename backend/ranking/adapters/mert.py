"""MERT-v1-95M adapter (frozen).

Third representation for the sensitivity extension
(research/protocol-mert-sensitivity-v1.md): audio-only self-supervised
transformer, no text tower. Pooling is fixed by the protocol: unweighted
mean over all transformer hidden layers, then mean over time. Weights are
downloaded once on first use; loading is lazy so importing this module
never triggers a download. The HF repo requires trust_remote_code; the
revision is pinned after load via the resolved commit hash.
"""

import numpy as np

from ranking.adapters.base import RepresentationModelCard

_MERT_REPO = "m-a-p/MERT-v1-95M"
_MERT_SR = 24000


class MertAdapter:
    def __init__(self):
        self._model = None
        self._processor = None
        self.model_card = RepresentationModelCard(
            model_id="mert-v1-95m",
            revision="unresolved-until-first-load",
            modality="audio_music",
            dims=768,
            license="Apache-2.0 repository; weights/training-data audit tracked in DATA_CREDITS.md",
            expected_sample_rate=_MERT_SR,
        )

    def _load(self):
        if self._model is None:
            import torch  # noqa: F401
            from transformers import AutoModel, Wav2Vec2FeatureExtractor

            self._model = AutoModel.from_pretrained(
                _MERT_REPO, trust_remote_code=True
            )
            self._model.eval()
            self._processor = Wav2Vec2FeatureExtractor.from_pretrained(
                _MERT_REPO, trust_remote_code=True
            )
            commit = getattr(self._model.config, "_commit_hash", None)
            self.model_card = RepresentationModelCard(
                model_id=self.model_card.model_id,
                revision=f"hf:{commit}" if commit else f"hf-repo-{_MERT_REPO}",
                modality=self.model_card.modality,
                dims=self.model_card.dims,
                license=self.model_card.license,
                expected_sample_rate=_MERT_SR,
            )
        return self._model

    def encode_audio(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        import librosa
        import torch

        model = self._load()
        mono = np.asarray(waveform, dtype=np.float32)
        if mono.ndim > 1:
            mono = mono.mean(axis=-1)
        mono = mono.reshape(-1)
        if sample_rate != _MERT_SR:
            mono = librosa.resample(mono, orig_sr=sample_rate, target_sr=_MERT_SR)
        inputs = self._processor(
            mono, sampling_rate=_MERT_SR, return_tensors="pt"
        )
        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)
        # [n_layers, batch=1, time, 768] -> protocol pooling: layer mean, time mean
        hidden = torch.stack(outputs.hidden_states)
        vector = hidden.mean(dim=0).mean(dim=1).squeeze(0).numpy()
        return vector / np.linalg.norm(vector)

    def encode_text(self, texts: list[str]) -> None:
        return None  # audio-only model, no text tower
