import os
import tempfile
from typing import Any

import requests
from google.cloud import storage


def extract_audio_features(audio_url: str) -> dict[str, Any]:
    """Extract objective audio features (BPM, key, duration, pitch range) using librosa."""
    audio_service_url = os.environ.get("AUDIO_SERVICE_URL")
    if audio_service_url:
        response = requests.post(
            f"{audio_service_url}/extract",
            json={"audio_url": audio_url},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    import librosa
    import numpy as np

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        if audio_url.startswith("gs://"):
            parts = audio_url.replace("gs://", "").split("/", 1)
            bucket_name, blob_name = parts[0], parts[1]
            client = storage.Client()
            client.bucket(bucket_name).blob(blob_name).download_to_filename(tmp.name)
        else:
            r = requests.get(audio_url, timeout=30)
            r.raise_for_status()
            tmp.write(r.content)
        tmp.flush()
        tmp_path = tmp.name

    y, sr = librosa.load(tmp_path, sr=22050, mono=True)
    os.unlink(tmp_path)

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key_index = int(chroma.mean(axis=1).argmax())
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    duration = float(librosa.get_duration(y=y, sr=sr))
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    active = pitches[magnitudes > np.max(magnitudes) * 0.1]
    pitch_range = (
        [float(np.min(active)), float(np.max(active))] if len(active) > 0 else [0.0, 0.0]
    )

    return {
        "bpm": round(float(tempo), 1),
        "estimated_key": keys[key_index],
        "duration_sec": round(duration, 2),
        "pitch_range": pitch_range,
    }
