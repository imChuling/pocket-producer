"""Beat-synchronous signals: agreement with the research implementation and
the session-side placement rules."""

import pathlib
import sys

import numpy as np
import pytest

from ranking import beat_sync

REPO = pathlib.Path(__file__).resolve().parents[3]
SR = 22050


def _research():
    sys.path.insert(0, str(REPO))
    from research.compat_tests import beatgrid, progression, signals

    return beatgrid, progression, signals


def _progression_audio(seconds=10.0, bpm=120.0, sr=SR):
    """Clicks on every beat over a I-IV-V-I progression, four beats per chord."""
    period = 60.0 / bpm
    t = np.arange(int(seconds * sr)) / sr
    y = np.zeros_like(t)
    chords = [(261.63, 329.63, 392.0), (349.23, 440.0, 523.25), (392.0, 493.88, 587.33)]
    rng = np.random.default_rng(1)
    for k in range(int(seconds / period)):
        a, b = int(k * period * sr), int((k + 1) * period * sr)
        y[a:b] += sum(0.1 * np.sin(2 * np.pi * f * t[a:b]) for f in chords[(k // 4) % 3])
        y[a : a + 400] += 0.5 * rng.standard_normal(400) * np.exp(-np.arange(400) / 80)
    return y.astype(np.float32)


@pytest.fixture(scope="module")
def clip():
    return beat_sync.frames(_progression_audio(), SR)


def test_frames_match_research(clip):
    beatgrid, _, _ = _research()
    theirs = beatgrid.frames(_progression_audio(), SR)
    assert np.allclose(clip.chroma, theirs.chroma)
    assert np.allclose(clip.onset, theirs.onset)
    assert np.allclose(clip.rms, theirs.rms)
    assert np.allclose(clip.times, theirs.times)


def test_pooling_matches_research(clip):
    beatgrid, _, signals = _research()
    grid = beatgrid.BeatGrid(bpm=120.0, beat_times=beat_sync.beat_times_for(120.0))
    theirs = beatgrid.frames(_progression_audio(), SR)
    assert np.allclose(
        beat_sync.pool_chroma(clip, grid.beat_times), beatgrid.pool_chroma(theirs, grid)
    )
    assert np.allclose(
        beat_sync.pool_onsets(clip, grid.beat_times),
        beatgrid.pool_onsets(theirs, grid, signals.ONSET_SUBDIVISIONS),
    )


def test_signals_match_research():
    _, progression, signals = _research()
    rng = np.random.default_rng(4)
    for _ in range(20):
        a = np.abs(rng.standard_normal((20, 12)))
        b = np.abs(rng.standard_normal((20, 12)))
        a[rng.random(20) < 0.2] = 0.0
        assert beat_sync.aligned_fit(a, b) == pytest.approx(progression.aligned_fit(a, b))
        x, y = rng.random(160), rng.random(150)
        assert beat_sync.onset_pattern(x, y) == pytest.approx(signals._onset_pattern(x, y))
    assert beat_sync.ONSET_SUBDIVISIONS == signals.ONSET_SUBDIVISIONS
    assert beat_sync.MIN_SHARED_BEATS == progression.MIN_SHARED_BEATS


def test_grid_starts_at_zero_and_covers_whole_beats_in_ten_seconds():
    times = beat_sync.beat_times_for(120.0)
    assert times[0] == 0.0 and times[-1] == pytest.approx(10.0)
    assert len(times) == 21
    assert beat_sync.beat_times_for(70.0)[-1] <= 10.0


def test_a_region_at_zero_is_the_clip_itself(clip):
    beats = beat_sync.session_beats([beat_sync.Placement(clip, 0.0)], 120.0)
    grid = np.asarray(beats["beat_times"])
    assert np.allclose(beats["beat_chroma"], beat_sync.pool_chroma(clip, grid), atol=1e-5)
    assert np.allclose(beats["onsets"], beat_sync.pool_onsets(clip, grid), atol=1e-5)


def test_regions_land_at_their_positions_and_stop_at_their_end(clip):
    late = beat_sync.session_beats([beat_sync.Placement(clip, 4.0, 2.0)], 120.0)
    chroma = np.asarray(late["beat_chroma"])
    sounding = np.linalg.norm(chroma, axis=1) > 0
    assert not sounding[:8].any()
    assert sounding[8:12].all()
    assert not sounding[12:].any()


def test_overlapping_regions_combine(clip):
    quiet = beat_sync.Frames(clip.chroma, clip.onset * 0.5, clip.rms, clip.times, clip.duration)
    both = beat_sync.session_beats(
        [beat_sync.Placement(clip, 0.0), beat_sync.Placement(quiet, 0.0)], 120.0
    )
    alone = beat_sync.session_beats([beat_sync.Placement(clip, 0.0)], 120.0)
    assert np.allclose(both["beat_chroma"], alone["beat_chroma"], atol=1e-5)
    assert np.allclose(both["onsets"], alone["onsets"], atol=1e-5)


def test_no_tempo_means_no_grid(clip):
    assert beat_sync.session_beats([beat_sync.Placement(clip, 0.0)], None) is None
    assert beat_sync.session_beats([beat_sync.Placement(clip, 0.0)], 0.0) is None


def test_stored_frames_round_trip_and_score_the_session(clip):
    record = beat_sync.encode_frames(clip)
    restored = beat_sync.decode_frames(record)
    assert restored.chroma.shape == clip.chroma.shape
    assert np.allclose(restored.chroma, clip.chroma, atol=2e-3)
    beats = beat_sync.session_beats([beat_sync.Placement(clip, 0.0)], 120.0)
    harmony, rhythm = beat_sync.candidate_signals(beats, record)
    assert harmony > 0.95 and rhythm > 0.95


def test_a_candidate_out_of_step_scores_lower(clip):
    beats = beat_sync.session_beats([beat_sync.Placement(clip, 0.0)], 120.0)
    shifted = beat_sync.frames(np.roll(_progression_audio(), int(0.37 * 0.5 * SR)), SR)
    same = beat_sync.candidate_signals(beats, beat_sync.encode_frames(clip))
    late = beat_sync.candidate_signals(beats, beat_sync.encode_frames(shifted))
    assert late[1] < same[1]


def test_silence_and_missing_records_are_not_scorable():
    assert beat_sync.frames(np.zeros(SR * 3, dtype=np.float32), SR) is None
    assert beat_sync.decode_frames(beat_sync.encode_frames(None)) is None
    assert beat_sync.candidate_signals(None, {}) is None
    assert beat_sync.candidate_signals({"beat_times": [0, 0.5]}, None) is None
