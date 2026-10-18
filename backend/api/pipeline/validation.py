"""Audio upload inspection and validation."""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException

from ..deps import ALLOWED_AUDIO_CONTENT_TYPES, MAX_AUDIO_BYTES, MAX_AUDIO_DURATION_SEC

logger = logging.getLogger(__name__)


def inspect_upload_sync(file_obj, filename: str | None, content_type: str | None) -> dict:
    base_type = content_type.split(";")[0].strip() if content_type else None
    if base_type and base_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {content_type}")

    suffix = Path(filename or "upload.webm").suffix or ".webm"
    total = 0
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_AUDIO_BYTES:
                    raise HTTPException(status_code=413, detail="Audio file must be 10 MB or smaller")
                tmp.write(chunk)

        if total == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")

        import librosa

        y, sr = librosa.load(
            tmp_path, sr=8000, mono=True,
            duration=MAX_AUDIO_DURATION_SEC + 1,
        )
        duration = float(librosa.get_duration(y=y, sr=sr))
        if duration > MAX_AUDIO_DURATION_SEC:
            raise HTTPException(status_code=413, detail="Audio must be 5 minutes or shorter")

        return {"size_bytes": total, "duration_sec": round(duration, 2)}
    finally:
        try:
            file_obj.seek(0)
        except Exception:
            pass
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


async def validate_audio_upload(file) -> dict:
    return await asyncio.to_thread(
        inspect_upload_sync, file.file, file.filename, file.content_type,
    )
