"""Perturbations do what their names say, on signals with a known answer."""

import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import datasets, perturb  # noqa: E402

SR = 16000


def _tone(frequency: float, seconds: float = None) -> np.ndarray:
    n = perturb.padded_length(SR) if seconds is None else int(seconds * SR)
    return (0.5 * np.sin(2 * np.pi * frequency * np.arange(n) / SR)).astype(np.float32)


def _clicks(period_seconds: float) -> np.ndarray:
    audio = np.zeros(perturb.padded_length(SR), dtype=np.float32)
    start = int(perturb.MARGIN_BEFORE * SR)
    audio[start :: int(period_seconds * SR)] = 1.0
    return audio


def _peak_frequency(audio: np.ndarray) -> float:
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.shape[0])))
    return float(np.fft.rfftfreq(audio.shape[0], 1 / SR)[spectrum.argmax()])


def _by_name(name: str) -> perturb.Perturbation:
    return next(p for p in perturb.catalogue() if p.name == name)


def test_every_perturbation_returns_a_full_window():
    padded = _tone(220.0)
    for item in perturb.catalogue():
        clip = perturb.apply(item, padded, SR, beat_seconds=0.5)
        assert clip.shape[0] == perturb.window_length(SR), item.name


@pytest.mark.parametrize("name,ratio", [("pitch+1", 2 ** (1 / 12)), ("pitch-3", 2 ** (-3 / 12)),
                                        ("pitch+12", 2.0)])
def test_pitch_shift_moves_the_fundamental(name, ratio):
    shifted = perturb.apply(_by_name(name), _tone(220.0), SR)
    assert _peak_frequency(shifted) == pytest.approx(220.0 * ratio, rel=0.01)


def test_pitch_roundtrip_returns_to_the_original_pitch():
    back = perturb.apply(_by_name("pitch_roundtrip"), _tone(220.0), SR)
    assert _peak_frequency(back) == pytest.approx(220.0, rel=0.005)


def _burst_at(seconds_into_window: float) -> np.ndarray:
    """Silence with one 100 ms tone burst at a known time inside the window."""
    audio = np.zeros(perturb.padded_length(SR), dtype=np.float32)
    begin = int((perturb.MARGIN_BEFORE + seconds_into_window) * SR)
    audio[begin : begin + SR // 10] = _tone(440.0, 0.1)
    return audio


def _burst_time(audio: np.ndarray) -> float:
    energy = audio.astype(np.float64) ** 2
    return float((energy * np.arange(energy.shape[0])).sum() / energy.sum() / SR)


@pytest.mark.parametrize("name", ["tempo+12%", "tempo+3%", "tempo-6%"])
def test_tempo_change_keeps_pitch_and_moves_events(name):
    item = _by_name(name)
    assert _peak_frequency(perturb.apply(item, _tone(220.0), SR)) == pytest.approx(220.0, rel=0.01)
    # An event 4 s into the window lands at 4 s divided by the rate.
    moved = _burst_time(perturb.apply(item, _burst_at(4.0), SR))
    assert moved == pytest.approx(4.05 / item.value, abs=0.04)


def test_tempo_roundtrip_puts_events_back():
    back = _burst_time(perturb.apply(_by_name("tempo_roundtrip"), _burst_at(4.0), SR))
    assert back == pytest.approx(4.05, abs=0.04)


def test_varispeed_moves_pitch_and_time_together():
    item = _by_name("varispeed+1")
    speed = 2 ** (1 / 12)
    assert _peak_frequency(perturb.apply(item, _tone(220.0), SR)) == pytest.approx(
        220.0 * speed, rel=0.005
    )
    assert _burst_time(perturb.apply(item, _burst_at(4.0), SR)) == pytest.approx(
        4.05 / speed, abs=0.01
    )


def test_beat_shift_delays_by_whole_beats_of_the_context():
    padded = _clicks(1.0)
    delayed = perturb.apply(_by_name("beatshift1"), padded, SR, beat_seconds=0.25)
    assert int(np.flatnonzero(delayed)[0]) == int(0.25 * SR)
    assert int(np.flatnonzero(perturb.original(padded, SR))[0]) == 0


def test_beat_shift_needs_a_grid_and_enough_lead_in():
    one_bar = _by_name("beatshift4")
    assert perturb.applicable(one_bar, True, 0.5)
    assert not perturb.applicable(one_bar, True, None)
    assert not perturb.applicable(one_bar, True, 1.5)
    assert not perturb.applicable(_by_name("pitch+1"), False, 0.5)


def test_gain_and_polarity_leave_the_waveform_shape_alone():
    padded = _tone(220.0)
    base = perturb.original(padded, SR)
    np.testing.assert_allclose(perturb.apply(_by_name("gain-6dB"), padded, SR), 0.5 * base)
    np.testing.assert_allclose(perturb.apply(_by_name("polarity"), padded, SR), -base)


def test_window_is_chosen_where_target_and_context_both_play():
    seconds = 40
    target = np.zeros(seconds * SR, dtype=np.float32)
    target[20 * SR : 32 * SR] = _tone(220.0, 12)
    others = [_tone(110.0, seconds), _tone(330.0, seconds)]
    start = datasets.choose_window(target, others, SR)
    assert start is not None and 20 <= start <= 22


def test_no_window_when_the_target_is_mostly_silent():
    target = np.zeros(40 * SR, dtype=np.float32)
    target[5 * SR : 8 * SR] = _tone(220.0, 3)
    assert datasets.choose_window(target, [_tone(110.0, 40), _tone(330.0, 40)], SR) is None
