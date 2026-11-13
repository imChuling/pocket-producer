"""MUSDB18-HQ reader: (context, target) pairs streamed from the release zip.

Each track is read straight out of the archive, one track at a time, so the
dataset never has to be unpacked. Every one of the four stems is the target
once, with the other three as its context.
"""

import io
import pathlib
import zipfile
from collections.abc import Iterator

import numpy as np

from .datasets import Pair, build_pair, in_shard

STEMS = ("drums", "bass", "other", "vocals")
SPLITS = ("train", "test")


def _index(archive: zipfile.ZipFile) -> dict[tuple[str, str], dict[str, str]]:
    """Map (split, track) to {stem: member name}, ignoring any leading folder."""
    tracks: dict[tuple[str, str], dict[str, str]] = {}
    for name in archive.namelist():
        parts = pathlib.PurePosixPath(name).parts
        if len(parts) < 3 or not parts[-1].endswith(".wav"):
            continue
        split, track, stem = parts[-3], parts[-2], parts[-1][: -len(".wav")]
        if split in SPLITS and stem in STEMS:
            tracks.setdefault((split, track), {})[stem] = name
    return tracks


def _read_mono(archive: zipfile.ZipFile, member: str) -> tuple[np.ndarray, int]:
    import soundfile

    audio, sample_rate = soundfile.read(io.BytesIO(archive.read(member)), dtype="float32")
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio, sample_rate


def musdb_pairs(
    zip_path: str | pathlib.Path,
    split: str | None = None,
    shard: tuple[int, int] | None = None,
) -> Iterator[Pair]:
    """Pairs for every track in `split` ("train", "test", or both when None).

    `shard` (i, n) keeps every n-th track, counted over the whole archive.
    """
    if split is not None and split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS} or None, got {split!r}")
    with zipfile.ZipFile(zip_path) as archive:
        tracks = _index(archive)
        for index, ((track_split, track), members) in enumerate(sorted(tracks.items())):
            if not in_shard(index, shard):
                continue
            if split is not None and track_split != split:
                continue
            if set(members) != set(STEMS):
                continue
            stems: dict[str, np.ndarray] = {}
            sample_rate = 0
            for stem in STEMS:
                stems[stem], sample_rate = _read_mono(archive, members[stem])
            length = min(audio.shape[0] for audio in stems.values())
            stems = {k: audio[:length] for k, audio in stems.items()}
            for stem in STEMS:
                others = [stems[k] for k in STEMS if k != stem]
                pair = build_pair(
                    f"{track_split}/{track}:{stem}",
                    track,
                    stem,
                    stem != "drums",
                    stems[stem],
                    others,
                    sample_rate,
                )
                if pair is not None:
                    yield pair
