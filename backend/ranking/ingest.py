"""Online MS-CLAP encoding for newly uploaded audio fragments.

Keeps the fragment library rank-ready: /api/ranking/rank reads
representations.audio_semantic.vector via attach_audio_embeddings, so a
fragment without this record can only be ranked through its text embedding.
Mirrors scripts/backfill_audio_representations.py — the backfill script
remains the recovery path for fragments uploaded while CLAP was disabled.
"""

import asyncio
import logging
import pathlib
import tempfile

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 44100

_adapter = None


def _get_adapter():
    global _adapter
    if _adapter is None:
        from ranking.adapters.msclap import MsClapAdapter

        _adapter = MsClapAdapter()
    return _adapter


def _encode_sync(db, user_id: str, fragment_id: str, gcs_uri: str) -> str:
    import librosa
    import numpy as np
    from bson import ObjectId
    from google.cloud import storage

    from ranking.adapters.base import audio_sha256, encode_with_lineage
    from ranking.zero_shot import style_scores

    bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
    suffix = pathlib.Path(blob_name).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
        storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(handle.name)
        waveform, sample_rate = librosa.load(handle.name, sr=TARGET_SAMPLE_RATE, mono=True)
    waveform = waveform.astype(np.float32)

    oid = ObjectId(fragment_id)
    doc = db["fragments"].find_one(
        {"_id": oid, "user_id": user_id},
        {"representations.audio_semantic.input_sha256": 1,
         "representations.audio_semantic.revision": 1},
    )
    if doc is None:
        return "missing"

    adapter = _get_adapter()
    input_hash = audio_sha256(waveform, sample_rate)
    existing = (doc.get("representations") or {}).get("audio_semantic") or {}
    if (
        existing.get("input_sha256") == input_hash
        and existing.get("revision") == adapter.model_card.revision
    ):
        return "skipped"

    record = encode_with_lineage(adapter, waveform, sample_rate)
    styles = style_scores(adapter, waveform, sample_rate)
    top_styles = sorted(styles.items(), key=lambda kv: -kv[1])[:5]
    db["fragments"].update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {
            "representations.audio_semantic": record.model_dump(),
            "style_scores": {
                "model_id": record.model_id,
                "revision": record.revision,
                "top": [
                    {"style": style, "score": round(score, 4)}
                    for style, score in top_styles
                ],
            },
        }},
    )
    return "encoded"


async def encode_audio_representation(
    db, user_id: str, fragment_id: str, gcs_uri: str
) -> str:
    """Encode one fragment's audio into representations.audio_semantic.

    Returns "encoded", "skipped" (already current), or "missing".
    """
    return await asyncio.to_thread(_encode_sync, db, user_id, fragment_id, gcs_uri)
