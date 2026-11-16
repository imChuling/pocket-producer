"""Readers that turn a multitrack dataset into (context, target) pairs.

A pair is one stem (the target) and everything else that plays with it in
the same window of the same recording. That is the only supervision the
behavioural tests need: the original target is known to fit its context.
"""

import pathlib
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from . import perturb

ACTIVE_RMS = 10 ** (-50 / 20)
MIN_ACTIVE_FRACTION = 0.8
MAX_REGIONS = 4


@dataclass
class Pair:
    pair_id: str
    track: str
    role: str
    pitched: bool
    sample_rate: int
    target_padded: np.ndarray
    context_mix: np.ndarray
    regions: list[np.ndarray]


def _second_rms(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    seconds = audio.shape[0] // sample_rate
    if seconds == 0:
        return np.zeros(0)
    frames = audio[: seconds * sample_rate].reshape(seconds, sample_rate)
    return np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))


def choose_window(target: np.ndarray, others: list[np.ndarray], sample_rate: int) -> int | None:
    """Start second of the window where target and context are both busiest.

    Returns None when no window has the target sounding for most of it with
    at least two other stems playing.
    """
    window = int(perturb.WINDOW_SECONDS)
    target_active = _second_rms(target, sample_rate) > ACTIVE_RMS
    other_active = np.stack([_second_rms(o, sample_rate) > ACTIVE_RMS for o in others])
    first = int(np.ceil(perturb.MARGIN_BEFORE))
    last = target_active.shape[0] - window - int(np.ceil(perturb.MARGIN_AFTER))
    best, best_score = None, 0.0
    for start in range(first, last + 1):
        span = slice(start, start + window)
        target_fraction = float(target_active[span].mean())
        stems_playing = int((other_active[:, span].mean(axis=1) >= MIN_ACTIVE_FRACTION).sum())
        if target_fraction < MIN_ACTIVE_FRACTION or stems_playing < 2:
            continue
        score = target_fraction + stems_playing / len(others)
        if score > best_score:
            best, best_score = start, score
    return best


def build_pair(
    pair_id: str,
    track: str,
    role: str,
    pitched: bool,
    target: np.ndarray,
    others: list[np.ndarray],
    sample_rate: int,
) -> Pair | None:
    start = choose_window(target, others, sample_rate)
    if start is None:
        return None
    lo = int(round((start - perturb.MARGIN_BEFORE) * sample_rate))
    padded = target[lo : lo + perturb.padded_length(sample_rate)].astype(np.float32)
    begin = start * sample_rate
    span = slice(begin, begin + perturb.window_length(sample_rate))
    windows = [o[span].astype(np.float32) for o in others]
    loudest = sorted(windows, key=lambda w: -float(np.sqrt((w**2).mean())))[:MAX_REGIONS]
    regions = [w for w in loudest if float(np.sqrt((w**2).mean())) > ACTIVE_RMS]
    context_mix = np.sum(windows, axis=0).astype(np.float32)
    return Pair(pair_id, track, role, pitched, sample_rate, padded, context_mix, regions)


def in_shard(index: int, shard: tuple[int, int] | None) -> bool:
    """Whether the track at `index` belongs to shard (i, n): every n-th track from i."""
    return shard is None or index % shard[1] == shard[0]


def babyslakh_pairs(
    root: pathlib.Path, per_track: int = 3, shard: tuple[int, int] | None = None
) -> Iterator[Pair]:
    """Up to `per_track` targets per track: drums, bass, then the loudest pitched stem."""
    import soundfile
    import yaml

    for index, track_dir in enumerate(sorted(p for p in root.iterdir() if p.is_dir())):
        if not in_shard(index, shard):
            continue
        meta = yaml.safe_load((track_dir / "metadata.yaml").read_text())
        stems: dict[str, tuple[dict, np.ndarray]] = {}
        sample_rate = 0
        for stem_id, info in meta["stems"].items():
            path = track_dir / "stems" / f"{stem_id}.wav"
            # BabySlakh marks stems as not rendered even when the file exists.
            if not path.exists():
                continue
            audio, sample_rate = soundfile.read(str(path), dtype="float32")
            if audio.ndim == 2:
                audio = audio.mean(axis=1)
            stems[stem_id] = (info, audio)
        if len(stems) < 3:
            continue
        length = min(audio.shape[0] for _, audio in stems.values())
        stems = {k: (info, audio[:length]) for k, (info, audio) in stems.items()}

        by_loudness = sorted(stems, key=lambda k: -float(np.sqrt((stems[k][1] ** 2).mean())))
        drums = [k for k in by_loudness if stems[k][0].get("is_drum")]
        bass = [k for k in by_loudness if stems[k][0].get("inst_class") == "Bass"]
        rest = [k for k in by_loudness if k not in drums and k not in bass]
        chosen = (drums[:1] + bass[:1] + rest)[:per_track]

        for stem_id in chosen:
            info, target = stems[stem_id]
            others = [audio for k, (_, audio) in stems.items() if k != stem_id]
            pair = build_pair(
                f"{track_dir.name}:{stem_id}",
                track_dir.name,
                "Drums" if info.get("is_drum") else str(info.get("inst_class")),
                not info.get("is_drum"),
                target,
                others,
                sample_rate,
            )
            if pair is not None:
                yield pair
