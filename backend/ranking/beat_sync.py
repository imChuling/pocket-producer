"""Beat-synchronous harmony and rhythm on the session's grid.

Two signals from the behavioural tests (research/results-behavioral-v1.md):

- chroma_beat_aligned: per-beat chroma agreement between the session and a
  candidate, so the order of the chords counts, not only which notes occur;
- onset_pattern: correlation of where the onsets fall inside each beat.

A clip is analysed once into frames (chroma, onset strength, RMS at 22050 Hz,
hop 512) and pooled on whatever grid it is heard against. The session grid is
not estimated: the project tempo is known, beats start at timeline zero and
each region is placed at its own position. Candidates are inserted at the
start of the timeline, so their first 10 s are pooled from beat 0.

Frame analysis, pooling and the full-grid signal mirror research/compat_tests
(beatgrid, progression, signals). Beat Fit restricts onset correlation to
shared sounding beats. Fusion's historical log uses the full-grid definition.
"""

import base64
import logging
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 22050
HOP_LENGTH = 512
SILENT_RMS = 10 ** (-50 / 20)
ONSET_SUBDIVISIONS = 8
MIN_SHARED_BEATS = 4
WINDOW_SECONDS = 10.0
MIN_BPM = 20.0
MAX_BPM = 360.0
MAX_BEATS = int(WINDOW_SECONDS * MAX_BPM / 60)
MAX_FRAMES = int(WINDOW_SECONDS * SAMPLE_RATE / HOP_LENGTH) + 1
BEAT_FRAMES_REVISION = "beat-frames-v1"
BEAT_FIT_SIGNAL_NAMES = ("chroma_beat_aligned", "onset_pattern_shared_beats")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Frames:
    chroma: np.ndarray  # (12, n)
    onset: np.ndarray  # (n,)
    rms: np.ndarray  # (n,)
    times: np.ndarray  # (n,) seconds from the clip's start
    duration: float


def frames(audio, sample_rate: int, max_seconds: float | None = WINDOW_SECONDS) -> Frames | None:
    """Frame analysis of the first `max_seconds` of a clip; None for silence."""
    import librosa

    y = np.asarray(audio, dtype=np.float32).reshape(-1)
    if sample_rate != SAMPLE_RATE:
        y = librosa.resample(y, orig_sr=sample_rate, target_sr=SAMPLE_RATE)
    if max_seconds is not None:
        y = y[: int(round(max_seconds * SAMPLE_RATE))]
    if y.size == 0 or float(np.sqrt(np.mean(y.astype(np.float64) ** 2))) < SILENT_RMS:
        return None
    chroma = librosa.feature.chroma_cqt(y=y, sr=SAMPLE_RATE, hop_length=HOP_LENGTH)
    onset = librosa.onset.onset_strength(y=y, sr=SAMPLE_RATE, hop_length=HOP_LENGTH)
    rms = librosa.feature.rms(y=y, hop_length=HOP_LENGTH)[0]
    n = min(chroma.shape[1], onset.shape[0], rms.shape[0])
    times = librosa.frames_to_time(np.arange(n), sr=SAMPLE_RATE, hop_length=HOP_LENGTH)
    return Frames(
        chroma=chroma[:, :n].astype(np.float32),
        onset=onset[:n].astype(np.float32),
        rms=rms[:n].astype(np.float32),
        times=times,
        duration=y.shape[0] / SAMPLE_RATE,
    )


def beat_times_for(bpm: float, seconds: float = WINDOW_SECONDS) -> np.ndarray:
    """Beat boundaries from timeline zero covering whole beats within `seconds`."""
    if not np.isfinite(bpm) or not MIN_BPM <= bpm <= MAX_BPM:
        raise ValueError(f"beat grid requires a finite tempo in [{MIN_BPM}, {MAX_BPM}] BPM")
    if not np.isfinite(seconds) or not 0 < seconds <= WINDOW_SECONDS:
        raise ValueError(f"beat grid window must be in (0, {WINDOW_SECONDS}] seconds")
    period = 60.0 / bpm
    count = int(np.floor(seconds / period + 1e-9))
    return np.arange(count + 1) * period


def _beat_chroma_parts(clip, beat_times, offset=0.0, until=None):
    """Per beat: mean chroma (unnormalised) and RMS of the sounding frames."""
    n_beats = max(beat_times.shape[0] - 1, 0)
    rows = np.zeros((n_beats, 12), dtype=np.float64)
    level = np.zeros(n_beats, dtype=np.float64)
    if clip is None:
        return rows, level
    times = clip.times + offset
    valid = times < until if until is not None else np.ones_like(times, dtype=bool)
    for i in range(n_beats):
        inside = valid & (times >= beat_times[i]) & (times < beat_times[i + 1])
        if not inside.any():
            continue
        rms = float(np.sqrt(np.mean(clip.rms[inside].astype(np.float64) ** 2)))
        if rms < SILENT_RMS:
            continue
        rows[i] = clip.chroma[:, inside].mean(axis=1).astype(np.float64)
        level[i] = rms
    return rows, level


def _normalise_rows(rows: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    return np.divide(rows, norms, out=np.zeros_like(rows), where=norms > 0)


def pool_chroma(clip, beat_times, offset: float = 0.0, until: float | None = None) -> np.ndarray:
    """Mean chroma per beat, L2-normalised; quiet or empty beats are zero rows."""
    rows, _ = _beat_chroma_parts(clip, beat_times, offset, until)
    return _normalise_rows(rows)


def _onset_slots(clip, beat_times, subdivisions, offset=0.0, until=None) -> np.ndarray:
    n_beats = max(beat_times.shape[0] - 1, 0)
    out = np.zeros(n_beats * subdivisions, dtype=np.float64)
    if clip is None:
        return out
    times = clip.times + offset
    valid = times < until if until is not None else np.ones_like(times, dtype=bool)
    for i in range(n_beats):
        edges = np.linspace(beat_times[i], beat_times[i + 1], subdivisions + 1)
        for s in range(subdivisions):
            inside = valid & (times >= edges[s]) & (times < edges[s + 1])
            if inside.any():
                out[i * subdivisions + s] = float(clip.onset[inside].max())
    return out


def _scale(slots: np.ndarray) -> np.ndarray:
    peak = float(slots.max()) if slots.size else 0.0
    return slots / peak if peak > 0 else slots


def pool_onsets(
    clip, beat_times, subdivisions: int = ONSET_SUBDIVISIONS, offset: float = 0.0,
    until: float | None = None,
) -> np.ndarray:
    """Peak onset strength per subdivision of each beat, scaled to [0, 1]."""
    return _scale(_onset_slots(clip, beat_times, subdivisions, offset, until))


@dataclass(frozen=True)
class Placement:
    clip: Frames | None
    start_seconds: float
    duration_seconds: float | None = None


def session_beats(placements: list[Placement], bpm: float | None) -> dict | None:
    """The session's beat chroma and onset slots over its first 10 s.

    Each region's frames are shifted to its timeline position and cut at its
    end. Chroma from overlapping regions is summed weighted by each region's
    loudness in that beat, then normalised per beat; onset slots take the
    strongest region per slot. Without a tempo there is no grid: None.
    """
    if bpm is None or not np.isfinite(bpm) or not MIN_BPM <= bpm <= MAX_BPM:
        return None
    grid = beat_times_for(bpm)
    if grid.shape[0] < 2:
        return None
    total = np.zeros((grid.shape[0] - 1, 12), dtype=np.float64)
    slots = np.zeros((grid.shape[0] - 1) * ONSET_SUBDIVISIONS, dtype=np.float64)
    for p in placements:
        if p.clip is None or p.start_seconds >= WINDOW_SECONDS:
            continue
        until = p.start_seconds + p.duration_seconds if p.duration_seconds else None
        rows, level = _beat_chroma_parts(p.clip, grid, p.start_seconds, until)
        total += rows * level[:, None]
        slots = np.maximum(
            slots, _onset_slots(p.clip, grid, ONSET_SUBDIVISIONS, p.start_seconds, until)
        )
    return {
        "bpm": float(bpm),
        "beat_times": [round(float(t), 6) for t in grid],
        "beat_chroma": _normalise_rows(total).round(6).tolist(),
        "onsets": _scale(slots).round(6).tolist(),
    }


def aligned_fit(context: np.ndarray, candidate: np.ndarray) -> float:
    """Mean per-beat chroma agreement in [0, 1]; 0 with fewer than 4 shared beats."""
    beats = min(context.shape[0], candidate.shape[0])
    context, candidate = context[:beats], candidate[:beats]
    both = (np.linalg.norm(context, axis=1) > 1e-8) & (np.linalg.norm(candidate, axis=1) > 1e-8)
    if int(both.sum()) < MIN_SHARED_BEATS:
        return 0.0
    left = context[both] / np.linalg.norm(context[both], axis=1, keepdims=True)
    right = candidate[both] / np.linalg.norm(candidate[both], axis=1, keepdims=True)
    return float((left * right).sum(axis=1).mean())


def onset_pattern(context: np.ndarray, candidate: np.ndarray) -> float:
    """Correlation of two onset-slot patterns mapped to [0, 1]; 0 if either is flat."""
    slots = min(context.shape[0], candidate.shape[0])
    context, candidate = context[:slots], candidate[:slots]
    if slots < 2 or context.std() < 1e-9 or candidate.std() < 1e-9:
        return 0.0
    return float((np.corrcoef(context, candidate)[0, 1] + 1.0) / 2.0)


def _b64(array: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(array, dtype=np.float16).tobytes()).decode()


def encode_frames(clip: Frames | None) -> dict:
    """Storage record for representations.beat_frames (float16, base64)."""
    record = {
        "revision": BEAT_FRAMES_REVISION,
        "sample_rate": SAMPLE_RATE,
        "hop_length": HOP_LENGTH,
        "window_seconds": WINDOW_SECONDS,
        "n_frames": 0,
    }
    if clip is not None:
        record.update(
            n_frames=int(clip.times.shape[0]),
            duration=round(float(clip.duration), 4),
            chroma=_b64(clip.chroma),
            onset=_b64(clip.onset),
            rms=_b64(clip.rms),
        )
    return record


def decode_frames(record: dict | None) -> Frames | None:
    """Decode a bounded v1 record; damaged/unsupported records are unavailable.

    Validation happens before allocation. One damaged cache must not turn a
    whole request (including otherwise unaffected five-signal fusion) into
    a fallback. Diagnostics contain no audio or base64 payloads.
    """
    if not record or record.get("revision") != BEAT_FRAMES_REVISION:
        return None
    try:
        n = record["n_frames"]
        if type(n) is not int or not 0 <= n <= MAX_FRAMES:
            raise ValueError("invalid frame count")
        if (record.get("sample_rate") != SAMPLE_RATE
                or record.get("hop_length") != HOP_LENGTH
                or record.get("window_seconds") != WINDOW_SECONDS):
            raise ValueError("unsupported frame codec")
        if n == 0:
            return None
        duration = float(record["duration"])
        # Stored duration is rounded to 4 decimals; tolerate only that rounding.
        if (not np.isfinite(duration) or not 0 < duration <= WINDOW_SECONDS
                or abs(n - 1 - duration * SAMPLE_RATE / HOP_LENGTH) > 1.01):
            raise ValueError("duration inconsistent with frame count")

        def unpack(key, shape):
            encoded = record[key]
            size = int(np.prod(shape)) * 2
            if not isinstance(encoded, str) or len(encoded) != 4 * ((size + 2) // 3):
                raise ValueError(f"invalid {key} length")
            payload = base64.b64decode(encoded, validate=True)
            if len(payload) != size:
                raise ValueError(f"invalid {key} byte count")
            raw = np.frombuffer(payload, dtype=np.float16).astype(np.float32).reshape(shape)
            if not np.isfinite(raw).all() or (raw < 0).any():
                raise ValueError(f"invalid {key} values")
            return raw

        return Frames(
            chroma=unpack("chroma", (12, n)), onset=unpack("onset", (n,)),
            rms=unpack("rms", (n,)), times=np.arange(n) * HOP_LENGTH / SAMPLE_RATE,
            duration=duration,
        )
    except (KeyError, ValueError, TypeError, OverflowError) as error:
        logger.warning("Ignoring invalid beat-frame record (%s)", type(error).__name__)
        return None


@dataclass(frozen=True)
class CandidateMeasurements:
    values: tuple[float, float]
    available: tuple[bool, bool]
    shared_beats: int

    @property
    def onset_correlation(self) -> float | None:
        return 2 * self.values[1] - 1 if self.available[1] else None


def candidate_measurements(
    beats: dict | None, record: dict | None, *, shared_onsets_only: bool = False,
) -> CandidateMeasurements | None:
    """Raw values plus support, independently of their relative ranking.

    The default measures onsets across the full grid for historical fusion
    logs. Beat Fit restricts both the flatness check and the correlation
    to subdivisions on shared sounding beats.
    """
    if not beats:
        return None
    clip = decode_frames(record)
    if clip is None:
        return None
    # Also protect direct callers that do not pass through RankRequest.
    from ranking.schemas import SessionBeats

    try:
        checked = SessionBeats.model_validate(beats)
    except ValueError:
        logger.warning("Ignoring invalid session beat grid")
        return None
    grid = np.asarray(checked.beat_times, dtype=np.float64)
    session_chroma = np.asarray(checked.beat_chroma, dtype=np.float64)
    session_onsets = np.asarray(checked.onsets, dtype=np.float64)
    candidate_chroma = pool_chroma(clip, grid)
    candidate_onsets = pool_onsets(clip, grid)
    shared_mask = ((np.linalg.norm(session_chroma, axis=1) > 1e-8)
                   & (np.linalg.norm(candidate_chroma, axis=1) > 1e-8))
    shared = int(shared_mask.sum())
    harmony_available = shared >= MIN_SHARED_BEATS
    if shared_onsets_only:
        slots = np.repeat(shared_mask, ONSET_SUBDIVISIONS)
        session_onsets = session_onsets[slots]
        candidate_onsets = candidate_onsets[slots]
    rhythm_available = (harmony_available and session_onsets.std() > 1e-8
                        and candidate_onsets.std() > 1e-8)
    return CandidateMeasurements(
        values=(aligned_fit(session_chroma, candidate_chroma) if harmony_available else 0.0,
                onset_pattern(session_onsets, candidate_onsets) if rhythm_available else 0.0),
        available=(harmony_available, bool(rhythm_available)), shared_beats=shared,
    )


def candidate_signals(beats: dict | None, record: dict | None) -> tuple[float, float] | None:
    """(chroma_beat_aligned, onset_pattern) for a stored candidate; None if not scorable."""
    measured = candidate_measurements(beats, record)
    return measured.values if measured is not None and any(measured.available) else None
