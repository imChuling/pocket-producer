"""Adapter protocol for frozen audio representation models.

Adapters wrap external models (MS-CLAP, LAION-CLAP, MusicFM, ...) behind one
interface so the bake-off, the cache and the ranking pipeline never depend on
a specific vendor. Adapters are frozen: they only encode, never train.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import numpy as np

from ranking.representations import Modality, RepresentationRecord


@dataclass(frozen=True)
class RepresentationModelCard:
    model_id: str
    revision: str
    modality: Modality
    dims: int
    license: str
    expected_sample_rate: int | None = None


@runtime_checkable
class AudioRepresentationAdapter(Protocol):
    model_card: RepresentationModelCard

    def encode_audio(
        self, waveform: np.ndarray, sample_rate: int
    ) -> np.ndarray: ...

    def encode_text(self, texts: list[str]) -> np.ndarray | None: ...


def audio_sha256(waveform: np.ndarray, sample_rate: int) -> str:
    digest = hashlib.sha256()
    digest.update(str(sample_rate).encode())
    digest.update(np.ascontiguousarray(waveform, dtype=np.float32).tobytes())
    return digest.hexdigest()


def pool_windows_mean_l2(windows: np.ndarray) -> np.ndarray:
    """Deterministic pooling: mean over windows, then L2 normalization."""
    pooled = np.asarray(windows, dtype=np.float64).mean(axis=0)
    norm = float(np.linalg.norm(pooled))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("cannot L2-normalize a zero or non-finite vector")
    return pooled / norm


def encode_with_lineage(
    adapter: AudioRepresentationAdapter,
    waveform: np.ndarray,
    sample_rate: int,
) -> RepresentationRecord:
    vector = np.asarray(adapter.encode_audio(waveform, sample_rate)).reshape(-1)
    if not np.all(np.isfinite(vector)):
        raise ValueError(
            f"{adapter.model_card.model_id} produced non-finite embedding values"
        )
    card = adapter.model_card
    return RepresentationRecord(
        modality=card.modality,
        model_id=card.model_id,
        revision=card.revision,
        dims=int(vector.shape[0]),
        vector=[float(v) for v in vector],
        input_sha256=audio_sha256(waveform, sample_rate),
        sample_rate=sample_rate,
        created_at=datetime.now(UTC).isoformat(),
        license=card.license,
    )


class EmbeddingCache:
    """Cache keyed by (model_id, revision, input hash) — a new model revision
    is always a miss, so upgrades can never silently reuse stale vectors."""

    def __init__(self):
        self._store: dict[tuple[str, str, str], RepresentationRecord] = {}

    def get_or_encode(
        self,
        adapter: AudioRepresentationAdapter,
        waveform: np.ndarray,
        sample_rate: int,
    ) -> RepresentationRecord:
        card = adapter.model_card
        key = (card.model_id, card.revision, audio_sha256(waveform, sample_rate))
        cached = self._store.get(key)
        if cached is not None:
            return cached
        record = encode_with_lineage(adapter, waveform, sample_rate)
        self._store[key] = record
        return record
