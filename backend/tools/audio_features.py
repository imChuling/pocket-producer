import asyncio
import os
import tempfile
from typing import Any
from urllib.parse import urlparse

import requests
from google.cloud import storage

_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024

_ALLOWED_AUDIO_HOSTS = frozenset({
    "cdn.audiotool.com",
    "api.audiotool.com",
    "storage.googleapis.com",
})


def _validate_audio_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Only HTTPS audio URLs are accepted, got {parsed.scheme!r}")
    if parsed.hostname not in _ALLOWED_AUDIO_HOSTS:
        raise ValueError(f"Audio host {parsed.hostname!r} is not in the allowlist")


def _extract_sync(audio_url: str) -> dict[str, Any]:
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
            _validate_audio_url(audio_url)
            r = requests.get(audio_url, timeout=30, stream=True)
            r.raise_for_status()
            total = 0
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                total += len(chunk)
                if total > _MAX_DOWNLOAD_BYTES:
                    raise ValueError("Remote audio exceeds 50 MB download cap")
                tmp.write(chunk)
        tmp.flush()
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=22050, mono=True)
    finally:
        os.unlink(tmp_path)

    duration = float(librosa.get_duration(y=y, sr=sr))

    # --- Core features (existing) ---
    tempo_raw, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.mean(tempo_raw))
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key_index = int(chroma.mean(axis=1).argmax())
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    active = pitches[magnitudes > np.max(magnitudes) * 0.1]
    pitch_range = (
        [float(np.min(active)), float(np.max(active))] if len(active) > 0 else [0.0, 0.0]
    )

    # --- Enriched features (new) ---

    # RMS energy — overall loudness curve, segmented into ~4 equal bins
    # Gives Gemini a sense of dynamic arc (e.g. build-up → drop)
    rms = librosa.feature.rms(y=y)[0]
    rms_mean = round(float(np.mean(rms)), 4)
    n_bins = min(4, max(1, int(duration // 5)))  # ~5 sec per bin, min 1
    if n_bins > 1 and len(rms) >= n_bins:
        bin_size = len(rms) // n_bins
        energy_curve = [
            round(float(np.mean(rms[i * bin_size : (i + 1) * bin_size])), 4)
            for i in range(n_bins)
        ]
    else:
        energy_curve = [rms_mean]

    # Spectral centroid — tonal "brightness" (low=warm/dark, high=bright/harsh)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = round(float(np.mean(centroid)), 1)

    # Onset density — how many note attacks per second (sparse vs dense texture)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    onset_density = round(len(onsets) / max(duration, 0.1), 2)

    # Major/minor confidence — helps Gemini verify key quality
    # Compare energy in major vs minor triads across the chroma
    major_profile = np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1])  # Major scale
    minor_profile = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0])  # Natural minor
    chroma_mean = chroma.mean(axis=1)
    major_corr = float(np.corrcoef(np.roll(chroma_mean, -key_index), major_profile)[0, 1])
    minor_corr = float(np.corrcoef(np.roll(chroma_mean, -key_index), minor_profile)[0, 1])
    estimated_mode = "major" if major_corr > minor_corr else "minor"

    # --- Niche-style discriminator features ---

    # Rhythm complexity — std dev of inter-onset intervals (IOI)
    # High = irregular timing (math-rock, jazz), low = steady pulse (four-on-floor, punk)
    # Medium = shuffle/swing patterns (blues, soul)
    if len(onsets) >= 3:
        ioi = np.diff(onsets)
        rhythm_complexity = round(float(np.std(ioi)), 4)
    else:
        rhythm_complexity = 0.0

    # Spectral flatness — how noise-like vs tonal the signal is (0=pure tone, 1=white noise)
    # High (>0.1) = shoegaze wall-of-sound, ambient drones, noise textures
    # Low (<0.02) = clean guitar, piano, vocals in front
    # Use with energy to disambiguate: high flatness + high energy = shoegaze,
    # high flatness + low energy = ambient
    spec_flat = librosa.feature.spectral_flatness(y=y)[0]
    spectral_flatness = round(float(np.mean(spec_flat)), 4)

    # Dynamic range — ratio of 90th to 10th percentile RMS
    # High (>4) = large dynamic swings (post-rock, classical, acoustic-ballad with climax)
    # Low (<2) = compressed/consistent loudness (punk, metal, trap, lo-fi)
    # Medium (2-4) = normal pop/rock dynamics
    if len(rms) >= 10:
        p90 = float(np.percentile(rms, 90))
        p10 = float(np.percentile(rms, 10))
        dynamic_range = round(p90 / max(p10, 1e-6), 2)
    else:
        dynamic_range = 1.0

    return {
        # Core (existing)
        "bpm": round(float(tempo), 1),
        "estimated_key": keys[key_index],
        "estimated_mode": estimated_mode,
        "duration_sec": round(duration, 2),
        "pitch_range": pitch_range,
        # Enriched (wave 1)
        "energy_mean": rms_mean,
        "energy_curve": energy_curve,
        "brightness": centroid_mean,
        "onset_density": onset_density,
        # Niche-style discriminators (wave 2)
        "rhythm_complexity": rhythm_complexity,
        "spectral_flatness": spectral_flatness,
        "dynamic_range": dynamic_range,
    }


async def extract_audio_features(audio_url: str) -> dict[str, Any]:
    """Extract objective audio features (BPM, key, duration, pitch range) using librosa."""
    return await asyncio.to_thread(_extract_sync, audio_url)
