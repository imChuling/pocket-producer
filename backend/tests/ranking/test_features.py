"""Unit tests for deterministic, [0, 1]-normalized ranking features."""

from ranking.features import (
    intent_match,
    key_match,
    novelty,
    recency,
    tempo_match,
    track_gap,
)


class TestTempoMatch:
    def test_exact_match_is_one(self):
        assert tempo_match(120, 120) == 1.0

    def test_close_tempo_scores_high(self):
        assert tempo_match(120, 121) > 0.9

    def test_far_tempo_scores_zero(self):
        assert tempo_match(120, 60) == 0.0

    def test_missing_values_score_zero(self):
        assert tempo_match(None, 120) == 0.0
        assert tempo_match(120, None) == 0.0

    def test_bounded(self):
        for frag in (0.1, 60, 90, 120, 180, 500):
            assert 0.0 <= tempo_match(120, frag) <= 1.0

    def test_asymmetric_by_design(self):
        # session_bpm is the anchor; swapping arguments changes the denominator
        assert tempo_match(120, 130) != tempo_match(130, 120)

    def test_half_tempo_is_zero(self):
        assert tempo_match(120, 60) == 0.0

    def test_double_tempo_is_zero(self):
        assert tempo_match(60, 120) == 0.0


class TestKeyMatch:
    def test_same_key_case_insensitive(self):
        assert key_match("A minor", "a minor") == 1.0

    def test_different_key_is_zero(self):
        assert key_match("A minor", "C major") == 0.0

    def test_missing_is_zero(self):
        assert key_match(None, "A minor") == 0.0
        assert key_match("A minor", None) == 0.0


class TestTrackGap:
    def test_candidate_filling_missing_role_scores_one(self):
        assert track_gap(["drums"], ["bass", "dark"]) == 1.0

    def test_candidate_duplicating_role_scores_zero(self):
        assert track_gap(["drums"], ["drums", "punchy"]) == 0.0

    def test_no_role_tags_scores_zero(self):
        assert track_gap(["drums"], ["dark", "moody"]) == 0.0


class TestIntentMatch:
    def test_full_overlap_is_one(self):
        assert intent_match("dark bass", ["dark", "bass"]) == 1.0

    def test_partial_overlap(self):
        assert intent_match("dark bass", ["dark", "vocal"]) == 0.5

    def test_empty_intent_is_zero(self):
        assert intent_match("", ["dark"]) == 0.0


class TestNovelty:
    def test_all_new_tags_score_one(self):
        assert novelty(["glitch", "texture"], ["drums"], "dark bass") == 1.0

    def test_all_known_tags_score_zero(self):
        assert novelty(["drums", "dark"], ["drums"], "dark bass") == 0.0

    def test_no_tags_score_zero(self):
        assert novelty([], ["drums"], "dark bass") == 0.0


class TestRecency:
    def test_newest_is_one(self):
        iso = "2026-07-29T00:00:00Z"
        assert recency(iso, newest_iso=iso) == 1.0

    def test_older_decays_monotonically(self):
        newest = "2026-07-29T00:00:00Z"
        newer = recency("2026-07-20T00:00:00Z", newest_iso=newest)
        older = recency("2026-01-01T00:00:00Z", newest_iso=newest)
        assert 0.0 <= older < newer < 1.0

    def test_invalid_timestamp_scores_zero(self):
        assert recency("not-a-date", newest_iso="2026-07-29T00:00:00Z") == 0.0
