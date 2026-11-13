"""Beat grid and beat-synchronous features on a synthetic progression with known beats."""

import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import beatgrid  # noqa: E402

SR = 44100
BPM = 120.0
PERIOD = 60.0 / BPM
OFFSET = 0.1
BEATS = 16
SECONDS = OFFSET + BEATS * PERIOD + 0.4

# C, F, G, C major, four beats each.
CHORDS = [
    ((261.63, 329.63, 392.00), {0, 4, 7}, 0),
    ((349.23, 440.00, 523.25), {5, 9, 0}, 5),
    ((392.00, 493.88, 587.33), {7, 11, 2}, 7),
    ((261.63, 329.63, 392.00), {0, 4, 7}, 0),
]


def _progression(gain: float = 1.0, chords=CHORDS) -> np.ndarray:
    n = int(SECONDS * SR)
    t = np.arange(n) / SR
    y = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(7)
    burst = int(0.02 * SR)
    decay = np.exp(-np.arange(burst) / (0.004 * SR))
    for k in range(BEATS):
        start = int(round((OFFSET + k * PERIOD) * SR))
        end = int(round((OFFSET + (k + 1) * PERIOD) * SR))
        freqs = chords[k // 4][0]
        y[start:end] += sum(0.12 * np.sin(2 * np.pi * f * t[start:end]) for f in freqs)
        y[start : start + burst] += 0.6 * rng.standard_normal(burst) * decay
    return (gain * y).astype(np.float32)


def _true_beat(index_time: float) -> int:
    return int(np.floor((index_time - OFFSET) / PERIOD + 1e-9))


@pytest.fixture(scope="module")
def audio():
    return _progression()


@pytest.fixture(scope="module")
def grid(audio):
    found = beatgrid.estimate_grid(audio, SR)
    assert found is not None
    return found


def _inside_beats(grid):
    """Grid beats whose span lies inside the synthesized beats."""
    last = OFFSET + BEATS * PERIOD
    return [
        i
        for i in range(grid.beat_times.shape[0] - 1)
        if grid.beat_times[i] >= OFFSET - 0.05 and grid.beat_times[i + 1] <= last + 0.05
    ]


def test_tempo_and_spacing(grid):
    assert abs(grid.bpm - BPM) / BPM < 0.03
    gaps = np.diff(grid.beat_times)
    assert np.all(np.abs(gaps - PERIOD) / PERIOD < 0.03)
    assert np.all(np.diff(grid.beat_times) > 0)
    assert grid.beat_times[0] >= 0
    assert grid.beat_times[-1] < SECONDS


def test_phase_lands_on_the_true_beats(grid):
    true = OFFSET + PERIOD * np.arange(BEATS)
    inside = grid.beat_times[(grid.beat_times >= OFFSET - 0.1) & (grid.beat_times < true[-1] + 0.1)]
    distance = np.abs(inside[:, None] - true[None, :]).min(axis=1)
    assert inside.shape[0] >= BEATS - 1
    assert np.all(distance <= 0.040)


def test_estimate_is_deterministic(audio, grid):
    again = beatgrid.estimate_grid(audio, SR)
    assert again.bpm == grid.bpm
    assert np.array_equal(again.beat_times, grid.beat_times)


def test_beat_chroma_top_three_pitch_classes(audio, grid):
    chroma = beatgrid.beat_sync_chroma(audio, SR, grid)
    assert chroma.shape == (grid.beat_times.shape[0] - 1, 12)
    rows = _inside_beats(grid)
    hits = 0
    for i in rows:
        k = _true_beat((grid.beat_times[i] + grid.beat_times[i + 1]) / 2)
        top3 = set(np.argsort(chroma[i])[-3:].tolist())
        hits += top3 == CHORDS[k // 4][1]
    assert hits / len(rows) >= 0.8


def test_chord_posteriors_pick_the_chord(audio, grid):
    posteriors = beatgrid.chord_posteriors(beatgrid.beat_sync_chroma(audio, SR, grid))
    assert posteriors.shape[1] == 24
    rows = _inside_beats(grid)
    hits = 0
    for i in rows:
        k = _true_beat((grid.beat_times[i] + grid.beat_times[i + 1]) / 2)
        hits += int(np.argmax(posteriors[i])) == CHORDS[k // 4][2]
        assert np.isclose(posteriors[i].sum(), 1.0)
    assert hits / len(rows) >= 0.8


def test_onsets_peak_at_the_start_of_each_beat(audio, grid):
    subdivisions = 4
    onsets = beatgrid.beat_sync_onsets(audio, SR, grid, subdivisions=subdivisions)
    assert onsets.shape == ((grid.beat_times.shape[0] - 1) * subdivisions,)
    assert onsets.min() >= 0 and onsets.max() == pytest.approx(1.0)
    per_beat = onsets.reshape(-1, subdivisions)
    rows = _inside_beats(grid)
    first_slot = sum(int(np.argmax(per_beat[i])) == 0 for i in rows)
    assert first_slot / len(rows) >= 0.8


def test_silence(grid):
    silent = np.zeros(int(SECONDS * SR), dtype=np.float32)
    assert beatgrid.estimate_grid(silent, SR) is None
    assert not beatgrid.beat_sync_chroma(silent, SR, grid).any()
    assert not beatgrid.beat_sync_onsets(silent, SR, grid).any()
    assert not beatgrid.chord_posteriors(np.zeros((3, 12))).any()


def test_a_grid_can_cut_other_audio(audio, grid):
    quiet = _progression(gain=0.1)
    other = _progression(chords=list(reversed(CHORDS)))
    for clip in (quiet, other, other[: int(4.0 * SR)]):
        assert beatgrid.beat_sync_chroma(clip, SR, grid).shape == (
            grid.beat_times.shape[0] - 1,
            12,
        )
        assert beatgrid.beat_sync_onsets(clip, SR, grid).shape == (
            (grid.beat_times.shape[0] - 1) * 4,
        )
    short_chroma = beatgrid.beat_sync_chroma(other[: int(4.0 * SR)], SR, grid)
    assert not short_chroma[-3:].any()


def test_other_sample_rates_give_the_same_grid(audio, grid):
    import librosa

    at_16k = librosa.resample(audio, orig_sr=SR, target_sr=16000)
    found = beatgrid.estimate_grid(at_16k, 16000)
    assert abs(found.bpm - grid.bpm) / grid.bpm < 0.01
