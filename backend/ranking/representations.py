"""Versioned representation contract.

No vector enters the system without lineage: model id, immutable revision,
input hash, dims and pooling policy. Different models never share a field.
"""

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Modality = Literal["text", "audio_semantic", "audio_music"]


class RepresentationRecord(BaseModel):
    modality: Modality
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    dims: int = Field(gt=0)
    vector: list[float]
    input_sha256: str = Field(min_length=1)
    sample_rate: int | None = None
    window_policy: str = "full"
    pooling: str = "mean_l2"
    created_at: str
    license: str | None = None

    @field_validator("vector")
    @classmethod
    def vector_must_be_finite(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(v) for v in value):
            raise ValueError("vector contains non-finite values")
        return value

    @model_validator(mode="after")
    def dims_must_match_vector(self):
        if len(self.vector) != self.dims:
            raise ValueError(
                f"dims={self.dims} does not match vector length {len(self.vector)}"
            )
        return self


LEGACY_TEXT_MODEL_ID = "voyage-3"


def migrate_legacy_embedding(fragment_doc: dict) -> RepresentationRecord | None:
    """Register the historical `embedding` field as what it actually is:
    a Voyage text embedding — regardless of the fragment's media type."""
    vector = fragment_doc.get("embedding")
    if not vector:
        return None
    return RepresentationRecord(
        modality="text",
        model_id=LEGACY_TEXT_MODEL_ID,
        revision="api-2026-07",
        dims=len(vector),
        vector=list(vector),
        input_sha256="legacy-unrecorded",
        created_at=str(fragment_doc.get("created_at", "unknown")),
    )
