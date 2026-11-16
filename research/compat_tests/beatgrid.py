"""Beat-synchronous features on a constant-tempo grid.

A clip gets one regular grid (tempo and phase). Chroma and onset strength
are then pooled per beat, or per subdivision of a beat, on that grid. The
grid can come from a different clip than the one being pooled, so a
candidate stem can be cut on its context's beats.
"""

from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 22050
HOP_LENGTH = 512
SILENT_RMS = 10 ** (-50 / 20)
PHASE_STEP_SECONDS = 0.002
# The onset envelope peaks about one frame after the onset that causes it.
ONSET_LAG_SECONDS = HOP_LENGTH / SAMPLE_RATE


@dataclass(frozen=True)
class BeatGrid:
    bpm: float
    beat_times: np.ndarray


def _resample(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    import librosa

    mono = np.asarray(audio, dtype=np.float32).reshape(-1)
    if sample_rate != SAMPLE_RATE:
        mono = librosa.resample(mono, orig_sr=sample_rate, target_sr=SAMPLE_RATE)
    return mono


def _rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def _onset_envelope(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    import librosa

    envelope = librosa.onset.onset_strength(y=y, sr=SAMPLE_RATE, hop_length=HOP_LENGTH)
    times = librosa.frames_to_time(
        np.arange(envelope.shape[0]), sr=SAMPLE_RATE, hop_length=HOP_LENGTH
    )
    return envelope, times


@dataclass(frozen=True)
class Frames:
    """Frame-level analysis of one clip at SAMPLE_RATE / HOP_LENGTH.

    Computed once per clip and pooled on as many grids as needed, so a
    candidate can be cut on another context's beats without touching its
    audio again.
    """

    chroma: np.ndarray  # (12, n_frames)
    onset: np.ndarray  # (n_frames,)
    rms: np.ndarray  # (n_frames,)
    times: np.ndarray  # (n_frames,) seconds
    duration: float
    audio: np.ndarray | None = None  # resampled waveform, kept only when asked for

    def without_audio(self) -> "Frames":
        return Frames(self.chroma, self.onset, self.rms, self.times, self.duration)


def frames(audio: np.ndarray, sample_rate: int) -> Frames | None:
    """Chroma, onset strength and RMS per frame, or None for silence."""
    import librosa

    y = _resample(audio, sample_rate)
    if _rms(y) < SILENT_RMS:
        return None
    chroma = librosa.feature.chroma_cqt(y=y, sr=SAMPLE_RATE, hop_length=HOP_LENGTH)
    envelope, times = _onset_envelope(y)
    rms = librosa.feature.rms(y=y, hop_length=HOP_LENGTH)[0]
    n = min(chroma.shape[1], envelope.shape[0], rms.shape[0])
    return Frames(
        chroma=chroma[:, :n].astype(np.float32),
        onset=envelope[:n].astype(np.float32),
        rms=rms[:n].astype(np.float32),
        times=times[:n],
        duration=y.shape[0] / SAMPLE_RATE,
        audio=y,
    )


def grid_from_frames(clip: Frames) -> BeatGrid | None:
    """Constant-tempo grid from a clip's frames (see estimate_grid)."""
    import librosa

    if clip.audio is None:
        raise ValueError("grid estimation needs the clip's audio")
    tempo, beat_frames = librosa.beat.beat_track(
        y=clip.audio, sr=SAMPLE_RATE, hop_length=HOP_LENGTH
    )
    tempo = float(np.atleast_1d(tempo)[0])
    if beat_frames.shape[0] >= 4:
        beat_seconds = librosa.frames_to_time(beat_frames, sr=SAMPLE_RATE, hop_length=HOP_LENGTH)
        period = float(np.polyfit(np.arange(beat_seconds.shape[0]), beat_seconds, 1)[0])
    elif tempo > 0:
        period = 60.0 / tempo
    else:
        return None
    if not np.isfinite(period) or period <= 0:
        return None

    best_phase, best_energy = 0.0, -np.inf
    for phase in np.arange(0.0, period, PHASE_STEP_SECONDS):
        points = np.arange(phase, clip.duration, period) + ONSET_LAG_SECONDS
        energy = float(np.interp(points, clip.times, clip.onset).sum())
        if energy > best_energy:
            best_phase, best_energy = float(phase), energy
    return BeatGrid(bpm=60.0 / period, beat_times=np.arange(best_phase, clip.duration, period))


def pool_chroma(clip: Frames | None, grid: BeatGrid) -> np.ndarray:
    """Mean chroma per beat of `grid`, L2-normalised; quiet beats are zero rows."""
    n_beats = max(grid.beat_times.shape[0] - 1, 0)
    out = np.zeros((n_beats, 12), dtype=np.float64)
    if clip is None:
        return out
    for i in range(n_beats):
        inside = (clip.times >= grid.beat_times[i]) & (clip.times < grid.beat_times[i + 1])
        if not inside.any():
            continue
        if float(np.sqrt(np.mean(clip.rms[inside].astype(np.float64) ** 2))) < SILENT_RMS:
            continue
        row = clip.chroma[:, inside].mean(axis=1).astype(np.float64)
        norm = float(np.linalg.norm(row))
        if norm > 0:
            out[i] = row / norm
    return out


def pool_onsets(clip: Frames | None, grid: BeatGrid, subdivisions: int = 4) -> np.ndarray:
    """Peak onset strength per subdivision of each beat of `grid`, scaled to [0, 1]."""
    n_beats = max(grid.beat_times.shape[0] - 1, 0)
    out = np.zeros(n_beats * subdivisions, dtype=np.float64)
    if clip is None:
        return out
    for i in range(n_beats):
        edges = np.linspace(grid.beat_times[i], grid.beat_times[i + 1], subdivisions + 1)
        for s in range(subdivisions):
            inside = (clip.times >= edges[s]) & (clip.times < edges[s + 1])
            if inside.any():
                out[i * subdivisions + s] = float(clip.onset[inside].max())
    peak = float(out.max())
    return out / peak if peak > 0 else out


def estimate_grid(audio: np.ndarray, sample_rate: int) -> BeatGrid | None:
    """Constant-tempo grid for a clip, or None for silence.

    The tempo comes from the beat tracker. Its own tempo value is quantised
    to whole frames of lag (120 BPM reads as 117.5), so the period is taken
    from a least-squares line through the beats it tracked; with fewer than
    four beats the tempo value is used as is. The phase is the offset within
    one period that puts the most onset strength on the grid points, read
    one frame after each point so that the points mark the onsets
    themselves rather than the envelope's delayed response to them.
    """
    clip = frames(audio, sample_rate)
    return grid_from_frames(clip) if clip is not None else None


def beat_sync_chroma(audio: np.ndarray, sample_rate: int, grid: BeatGrid) -> np.ndarray:
    """Mean chroma per beat, L2-normalised; beats quieter than -50 dBFS are zero."""
    return pool_chroma(frames(audio, sample_rate), grid)


def beat_sync_onsets(
    audio: np.ndarray, sample_rate: int, grid: BeatGrid, subdivisions: int = 4
) -> np.ndarray:
    """Peak onset strength in each subdivision of each beat, scaled to [0, 1].

    Slots use the envelope's own frame times, so an onset on a slot boundary
    shows up in the slot that starts there (the envelope responds a frame later).
    """
    return pool_onsets(frames(audio, sample_rate), grid, subdivisions)


def _chord_templates() -> np.ndarray:
    templates = np.zeros((24, 12), dtype=np.float64)
    for root in range(12):
        templates[root, [root, (root + 4) % 12, (root + 7) % 12]] = 1.0
        templates[12 + root, [root, (root + 3) % 12, (root + 7) % 12]] = 1.0
    return templates / np.linalg.norm(templates, axis=1, keepdims=True)


CHORD_TEMPLATES = _chord_templates()


def chord_posteriors(beat_chroma: np.ndarray) -> np.ndarray:
    """Per-beat weights over 24 triads (0-11 major C..B, 12-23 minor C..B), rows sum to 1."""
    scores = np.clip(np.asarray(beat_chroma, dtype=np.float64) @ CHORD_TEMPLATES.T, 0.0, None)
    totals = scores.sum(axis=1, keepdims=True)
    return np.divide(scores, totals, out=np.zeros_like(scores), where=totals > 0)
