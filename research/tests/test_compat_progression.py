"""The progression scorers see chord order, which a mean chroma vector cannot."""

import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import progression  # noqa: E402

C, F, G, A_MINOR = (0, 4, 7), (5, 9, 0), (7, 11, 2), (9, 0, 4)


def _beats(chords, beats_per_chord=4) -> np.ndarray:
    rows = []
    for chord in chords:
        row = np.zeros(12)
        row[list(chord)] = 1.0
        rows.extend([row / np.linalg.norm(row)] * beats_per_chord)
    return np.array(rows)


def test_same_chords_in_a_different_order_share_a_mean_chroma_but_not_a_fit():
    session = _beats([C, G, A_MINOR, F])
    reordered = _beats([C, A_MINOR, F, G])
    np.testing.assert_allclose(session.mean(axis=0), reordered.mean(axis=0))
    assert progression.aligned_fit(session, session) == pytest.approx(1.0)
    assert progression.aligned_fit(session, reordered) < 0.6


def test_one_bar_late_is_found_and_reported():
    session = _beats([C, G, A_MINOR, F, C, G])
    late = np.vstack([session[4:], _beats([A_MINOR])])
    assert progression.aligned_fit(session, late) < 0.7
    score, transposition, delay = progression.best_alignment(session, late)
    assert (transposition, delay) == (0, 4)
    assert score == pytest.approx(1.0)


def test_transposed_copy_is_found_and_reported():
    session = _beats([C, G, A_MINOR, F])
    down_two = np.roll(session, -2, axis=1)
    score, transposition, delay = progression.best_alignment(session, down_two)
    assert (transposition, delay) == (2, 0)
    assert score == pytest.approx(1.0)


def test_an_aligned_candidate_needs_no_change():
    session = _beats([C, C, C, C])
    assert progression.best_alignment(session, session)[1:] == (0, 0)


def test_silent_beats_are_not_evidence():
    session = _beats([C, G, A_MINOR, F])
    sparse = session.copy()
    sparse[::2] = 0.0
    assert progression.aligned_fit(session, sparse) == pytest.approx(1.0)
    assert progression.aligned_fit(session, np.zeros_like(session)) == 0.0


def test_on_grid_ratio_separates_gridded_from_drifting_onsets():
    subdivisions = 8
    on_grid = np.zeros(4 * subdivisions)
    on_grid[::2] = 1.0
    between = np.zeros(4 * subdivisions)
    between[1::2] = 1.0
    assert progression.on_grid_ratio(on_grid, subdivisions) == 1.0
    assert progression.on_grid_ratio(between, subdivisions) == 0.0
    assert progression.on_grid_ratio(np.ones(4 * subdivisions), subdivisions) == 0.5
    assert progression.on_grid_ratio(np.zeros(4 * subdivisions), subdivisions) == 0.0
    with pytest.raises(ValueError):
        progression.on_grid_ratio(on_grid, 4)
