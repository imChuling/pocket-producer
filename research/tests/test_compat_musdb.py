"""The MUSDB18-HQ reader on a small synthetic archive with the release layout."""

import io
import pathlib
import sys
import zipfile

import numpy as np
import pytest
import soundfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import musdb, perturb  # noqa: E402

SR = 44100
SECONDS = 22


def _stem(frequency: float, seconds: int = SECONDS, silent: bool = False) -> np.ndarray:
    t = np.arange(seconds * SR) / SR
    mono = np.zeros_like(t) if silent else 0.3 * np.sin(2 * np.pi * frequency * t)
    # Stereo with a small channel difference, as in the real stems.
    return np.stack([mono, 0.9 * mono], axis=1).astype(np.float32)


def _wav_bytes(audio: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, audio, SR, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def _archive(
    path: pathlib.Path, tracks: dict[str, dict[str, np.ndarray]], prefix: str = ""
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for track_path, stems in tracks.items():
            for stem, audio in stems.items():
                archive.writestr(f"{prefix}{track_path}/{stem}.wav", _wav_bytes(audio))
            shortest = min(a.shape[0] for a in stems.values())
            mixture = sum(a[:shortest] for a in stems.values())
            archive.writestr(f"{prefix}{track_path}/mixture.wav", _wav_bytes(mixture))


def _full_track(offset: float = 0.0) -> dict[str, np.ndarray]:
    return {
        "drums": _stem(80 + offset),
        "bass": _stem(55 + offset),
        "other": _stem(330 + offset),
        "vocals": _stem(440 + offset),
    }


def test_every_stem_is_a_target_once(tmp_path):
    zip_path = tmp_path / "musdb18hq.zip"
    _archive(zip_path, {"train/Artist - Song": _full_track()})

    pairs = list(musdb.musdb_pairs(zip_path))

    assert [p.role for p in pairs] == list(musdb.STEMS)
    assert [p.pair_id for p in pairs] == [f"train/Artist - Song:{s}" for s in musdb.STEMS]
    assert {p.track for p in pairs} == {"Artist - Song"}
    assert [p.pitched for p in pairs] == [False, True, True, True]


def test_pairs_are_mono_at_the_source_rate_with_three_stem_context(tmp_path):
    zip_path = tmp_path / "musdb18hq.zip"
    _archive(zip_path, {"test/Artist - Song": _full_track()})

    pair = next(musdb.musdb_pairs(zip_path))

    assert pair.sample_rate == SR
    assert pair.target_padded.ndim == 1
    assert pair.target_padded.shape[0] == perturb.padded_length(SR)
    assert pair.context_mix.shape == (perturb.window_length(SR),)
    assert len(pair.regions) == 3
    assert all(r.shape == (perturb.window_length(SR),) for r in pair.regions)


def test_split_filter_and_leading_folder(tmp_path):
    zip_path = tmp_path / "musdb18hq.zip"
    _archive(
        zip_path,
        {"train/A - One": _full_track(), "test/B - Two": _full_track(offset=3.0)},
        prefix="musdb18hq/",
    )

    train = {p.track for p in musdb.musdb_pairs(zip_path, split="train")}
    test = {p.track for p in musdb.musdb_pairs(zip_path, split="test")}
    both = {p.track for p in musdb.musdb_pairs(zip_path)}

    assert train == {"A - One"}
    assert test == {"B - Two"}
    assert both == {"A - One", "B - Two"}


def test_stems_of_unequal_length_are_trimmed_to_the_shortest(tmp_path):
    zip_path = tmp_path / "musdb18hq.zip"
    track = _full_track()
    track["vocals"] = _stem(440, seconds=SECONDS - 2)
    _archive(zip_path, {"train/Artist - Song": track})

    pairs = list(musdb.musdb_pairs(zip_path))

    assert len(pairs) == 4


def test_silent_target_and_incomplete_tracks_are_skipped(tmp_path):
    zip_path = tmp_path / "musdb18hq.zip"
    silent_bass = _full_track()
    silent_bass["bass"] = _stem(55, silent=True)
    missing_vocals = _full_track()
    del missing_vocals["vocals"]
    _archive(zip_path, {"train/Silent Bass": silent_bass, "train/No Vocals": missing_vocals})

    pairs = list(musdb.musdb_pairs(zip_path))

    assert {p.track for p in pairs} == {"Silent Bass"}
    assert "bass" not in {p.role for p in pairs}


def test_unknown_split_is_rejected(tmp_path):
    zip_path = tmp_path / "musdb18hq.zip"
    _archive(zip_path, {"train/Artist - Song": _full_track()})

    with pytest.raises(ValueError):
        list(musdb.musdb_pairs(zip_path, split="valid"))
