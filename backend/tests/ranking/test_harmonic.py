"""Tests for chroma-based harmonic compatibility probe and ranker."""

import numpy as np
import pytest

from ranking.harmonic_probe import (
    CHROMA_BINS,
    chroma_from_audio,
    session_chroma,
    shift_label,
    transpose_invariant_score,
)
from ranking.harmonic_ranker import HarmonicFitRanker
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint


def _c_major_chroma() -> list[float]:
    """C-E-G triad chroma profile (normalized)."""
    c = np.zeros(CHROMA_BINS)
    c[0] = 1.0  # C
    c[4] = 1.0  # E
    c[7] = 1.0  # G
    return list(c / np.linalg.norm(c))


def _f_major_chroma() -> list[float]:
    """F-A-C triad — shift C major up by 5 semitones."""
    return list(np.roll(np.array(_c_major_chroma()), 5))


def _c_minor_chroma() -> list[float]:
    """C-Eb-G triad chroma profile."""
    c = np.zeros(CHROMA_BINS)
    c[0] = 1.0  # C
    c[3] = 1.0  # Eb
    c[7] = 1.0  # G
    return list(c / np.linalg.norm(c))


class TestTransposeInvariantScore:
    def test_identical_chromas_score_1(self):
        chroma = _c_major_chroma()
        score, shift = transpose_invariant_score(chroma, chroma)
        assert score == pytest.approx(1.0, abs=1e-5)
        assert shift == 0

    def test_transposed_chromas_detected(self):
        c_maj = _c_major_chroma()
        f_maj = _f_major_chroma()
        score, shift = transpose_invariant_score(c_maj, f_maj)
        assert score == pytest.approx(1.0, abs=1e-5)
        assert shift == 7  # roll F up 7 semitones = C

    def test_different_quality_scores_lower(self):
        c_maj = _c_major_chroma()
        c_min = _c_minor_chroma()
        score, _ = transpose_invariant_score(c_maj, c_min)
        assert 0.0 < score < 1.0

    def test_zero_chroma_scores_zero(self):
        c_maj = _c_major_chroma()
        zero = [0.0] * CHROMA_BINS
        score, shift = transpose_invariant_score(c_maj, zero)
        assert score == 0.0
        assert shift == 0

    def test_both_zero_scores_zero(self):
        zero = [0.0] * CHROMA_BINS
        score, _ = transpose_invariant_score(zero, zero)
        assert score == 0.0

    def test_score_in_valid_range(self):
        rng = np.random.default_rng(42)
        for _ in range(20):
            a = list(rng.random(CHROMA_BINS))
            b = list(rng.random(CHROMA_BINS))
            score, shift = transpose_invariant_score(a, b)
            assert 0.0 <= score <= 1.0
            assert 0 <= shift < CHROMA_BINS


class TestSessionChroma:
    def test_single_region(self):
        c_maj = _c_major_chroma()
        result = session_chroma([c_maj])
        assert len(result) == CHROMA_BINS
        np.testing.assert_allclose(result, c_maj, atol=1e-6)

    def test_empty_regions(self):
        result = session_chroma([])
        assert result == [0.0] * CHROMA_BINS

    def test_multiple_regions_averaged(self):
        c_maj = _c_major_chroma()
        f_maj = _f_major_chroma()
        result = session_chroma([c_maj, f_maj])
        assert len(result) == CHROMA_BINS
        assert sum(abs(x) for x in result) > 0


class TestShiftLabel:
    def test_zero_shift(self):
        assert shift_label(0) == "in original key"

    def test_nonzero_shift(self):
        label = shift_label(5)
        assert "+5" in label
        assert "F" in label

    def test_sharp_note(self):
        label = shift_label(1)
        assert "C♯" in label


class TestChromaFromAudio:
    def test_sine_wave_peaks_at_correct_bin(self):
        sr = 22050
        duration = 1.0
        freq = 440.0  # A4
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        waveform = np.sin(2 * np.pi * freq * t).astype(np.float32)
        chroma = chroma_from_audio(waveform, sr)
        assert len(chroma) == CHROMA_BINS
        assert chroma[9] == max(chroma)  # A is bin 9

    def test_empty_waveform(self):
        chroma = chroma_from_audio(np.array([], dtype=np.float32))
        assert chroma == [0.0] * CHROMA_BINS

    def test_silence_returns_zero(self):
        chroma = chroma_from_audio(np.zeros(22050, dtype=np.float32))
        assert all(abs(x) < 1e-6 for x in chroma)


class TestHarmonicFitRanker:
    def _make_request(self, session_chromas, candidate_chromas):
        candidates = [
            FragmentCandidate(
                fragment_id=f"f{i}",
                duration_seconds=4.0,
                created_at_iso="2026-07-01T00:00:00Z",
                audio_url=f"/api/fragments/f{i}/audio",
                chroma_vector=cv,
            )
            for i, cv in enumerate(candidate_chromas)
        ]
        return RankRequest(
            session=SessionFingerprint(
                project_id="p1",
                playhead_seconds=0,
                track_count=len(session_chromas),
                active_track_types=[],
                region_chroma_vectors=session_chromas,
            ),
            candidates=candidates,
            model_id="harmonic-fit-v1",
            limit=10,
        )

    def test_same_key_scores_highest(self):
        ranker = HarmonicFitRanker()
        c_maj = _c_major_chroma()
        c_min = _c_minor_chroma()
        request = self._make_request([c_maj], [c_maj, c_min])
        response = ranker.rank(request)
        assert response.model_id == "harmonic-fit-v1"
        assert response.candidates[0].fragment_id == "f0"
        assert response.candidates[0].score > response.candidates[1].score
        assert response.candidates[0].evidence[0].code == "harmonic_fit"

    def test_transposition_detected_in_evidence(self):
        ranker = HarmonicFitRanker()
        c_maj = _c_major_chroma()
        f_maj = _f_major_chroma()
        request = self._make_request([c_maj], [f_maj])
        response = ranker.rank(request)
        label = response.candidates[0].evidence[0].label
        assert "transpose" in label

    def test_missing_chroma_scores_zero(self):
        ranker = HarmonicFitRanker()
        c_maj = _c_major_chroma()
        request = RankRequest(
            session=SessionFingerprint(
                project_id="p1",
                playhead_seconds=0,
                track_count=1,
                active_track_types=[],
                region_chroma_vectors=[c_maj],
            ),
            candidates=[
                FragmentCandidate(
                    fragment_id="f0",
                    duration_seconds=4.0,
                    created_at_iso="2026-07-01T00:00:00Z",
                    audio_url="/api/fragments/f0/audio",
                    chroma_vector=None,
                )
            ],
            model_id="harmonic-fit-v1",
        )
        response = ranker.rank(request)
        assert response.candidates[0].score == 0.0
        assert response.candidates[0].evidence == []

    def test_no_regions_raises(self):
        ranker = HarmonicFitRanker()
        request = RankRequest(
            session=SessionFingerprint(
                project_id="p1",
                playhead_seconds=0,
                track_count=0,
                active_track_types=[],
            ),
            candidates=[
                FragmentCandidate(
                    fragment_id="f0",
                    duration_seconds=4.0,
                    created_at_iso="2026-07-01T00:00:00Z",
                    audio_url="/api/fragments/f0/audio",
                )
            ],
            model_id="harmonic-fit-v1",
        )
        with pytest.raises(Exception):
            ranker.rank(request)
