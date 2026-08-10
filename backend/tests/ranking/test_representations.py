"""Lineage contract for versioned representations.

Every vector must carry model id, immutable revision, input hash and dims;
vectors without lineage or with non-finite values are rejected outright.
"""

import math

import pytest
from pydantic import ValidationError

from ranking.representations import (
    RepresentationRecord,
    migrate_legacy_embedding,
)


def valid_record(**overrides) -> RepresentationRecord:
    base = dict(
        modality="audio_semantic",
        model_id="msclap-2023",
        revision="sha256:abc123",
        dims=4,
        vector=[0.1, 0.2, 0.3, 0.4],
        input_sha256="f" * 64,
        sample_rate=44100,
        window_policy="full",
        pooling="mean_l2",
        created_at="2026-07-31T00:00:00Z",
    )
    base.update(overrides)
    return RepresentationRecord(**base)


class TestRepresentationRecord:
    def test_valid_record_roundtrips(self):
        record = valid_record()
        assert record.model_id == "msclap-2023"
        assert record.dims == 4

    def test_missing_revision_rejected(self):
        with pytest.raises(ValidationError):
            valid_record(revision="")

    def test_missing_input_hash_rejected(self):
        with pytest.raises(ValidationError):
            valid_record(input_sha256="")

    def test_dims_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            valid_record(dims=3)

    def test_nan_vector_rejected(self):
        with pytest.raises(ValidationError):
            valid_record(vector=[0.1, math.nan, 0.3, 0.4])

    def test_inf_vector_rejected(self):
        with pytest.raises(ValidationError):
            valid_record(vector=[0.1, math.inf, 0.3, 0.4])

    def test_unknown_modality_rejected(self):
        with pytest.raises(ValidationError):
            valid_record(modality="vibes")


class TestLegacyMigration:
    def test_legacy_embedding_becomes_text_representation(self):
        doc = {
            "_id": "f1",
            "text": "dark bass idea",
            "embedding": [0.1, 0.2],
        }
        record = migrate_legacy_embedding(doc)
        assert record.modality == "text"
        assert record.model_id == "voyage-3"
        assert record.dims == 2
        assert record.vector == [0.1, 0.2]

    def test_fragment_without_embedding_returns_none(self):
        assert migrate_legacy_embedding({"_id": "f2"}) is None

    def test_legacy_embedding_never_labeled_audio(self):
        record = migrate_legacy_embedding(
            {"_id": "f3", "type": "audio", "embedding": [0.5]}
        )
        assert record.modality == "text"
