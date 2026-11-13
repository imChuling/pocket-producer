"""Retrieval over a small synthetic store with a known answer."""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import beatgrid, run_retrieval, signals  # noqa: E402

BEATS = 16
FRAMES_PER_BEAT = 10
ROLES = ("bass", "other")
N_TRACKS = 12


def _progression(seed: int) -> np.ndarray:
    """One pitch class per bar, different for every track."""
    rng = np.random.default_rng(seed)
    bars = rng.choice(12, size=BEATS // 4, replace=False)
    rows = np.zeros((BEATS, 12))
    for beat in range(BEATS):
        rows[beat, bars[beat // 4]] = 1.0
    return rows


def _frames(beat_chroma: np.ndarray, period: float) -> beatgrid.Frames:
    n = BEATS * FRAMES_PER_BEAT
    times = (np.arange(n) + 0.5) * period / FRAMES_PER_BEAT
    chroma = np.repeat(beat_chroma, FRAMES_PER_BEAT, axis=0).T.astype(np.float32)
    onset = np.zeros(n, dtype=np.float32)
    onset[::FRAMES_PER_BEAT] = 1.0
    return beatgrid.Frames(
        chroma=chroma, onset=onset, rms=np.ones(n, dtype=np.float32), times=times,
        duration=BEATS * period,
    )


def _features(rng, beat_chroma=None, onsets=None) -> signals.ClipFeatures:
    return signals.ClipFeatures(
        embeddings={"msclap": rng.normal(size=16).astype(np.float32)},
        bpm=120.0,
        key="C major",
        chroma=list(np.ones(12) / np.sqrt(12)),
        beat_chroma=beat_chroma,
        onsets=onsets,
    )


def _store() -> dict:
    rng = np.random.default_rng(0)
    cache = {}
    for track in range(N_TRACKS):
        period = 0.5
        grid = beatgrid.BeatGrid(bpm=120.0, beat_times=np.arange(BEATS + 1) * period)
        progression = _progression(track)
        onsets = np.zeros(BEATS * signals.ONSET_SUBDIVISIONS)
        onsets[:: signals.ONSET_SUBDIVISIONS] = 1.0
        for role in ROLES:
            cache[f"t{track:02d}:{role}"] = {
                "pair_id": f"t{track:02d}:{role}",
                "track": f"t{track:02d}",
                "role": role,
                "pitched": True,
                "grid": grid,
                "context_mix": _features(rng, progression, onsets),
                "regions": [_features(rng), _features(rng)],
                "original": _features(rng, progression, onsets),
                "original_frames": _frames(progression, period),
                "perturbed": {},
            }
    return cache


def test_rank_shares_ties_and_counts_better_scores():
    assert run_retrieval.rank_of_first(np.array([3.0, 1.0, 2.0])) == 1.0
    assert run_retrieval.rank_of_first(np.array([1.0, 3.0, 2.0])) == 3.0
    assert run_retrieval.rank_of_first(np.array([1.0, 1.0, 1.0])) == 2.0
    assert run_retrieval.rank_of_first(np.array([1.0, 2.0, 1.0])) == 2.5


def test_standardise_handles_a_constant_column():
    np.testing.assert_allclose(run_retrieval.standardise(np.array([2.0, 2.0, 2.0])), 0.0)
    scaled = run_retrieval.standardise(np.array([1.0, 2.0, 3.0]))
    assert abs(scaled.mean()) < 1e-12 and abs(scaled.std() - 1.0) < 1e-12


def test_pools_start_with_the_target_and_use_other_tracks_only():
    cache = _store()
    pair_ids = sorted(cache)
    for pool in run_retrieval.POOLS:
        candidates = run_retrieval.draw_pool(cache, pair_ids, 3, pool)
        query = cache[pair_ids[3]]
        assert candidates[0] == pair_ids[3]
        assert all(cache[c]["track"] != query["track"] for c in candidates[1:])
        assert len(set(candidates)) == len(candidates)
        assert candidates == run_retrieval.draw_pool(cache, pair_ids, 3, pool)
    same = run_retrieval.draw_pool(cache, pair_ids, 3, "same_role")
    assert all(cache[c]["role"] == cache[pair_ids[3]]["role"] for c in same)


def test_tempo_matched_pool_keeps_only_tracks_at_the_querys_tempo():
    cache = _store()
    pair_ids = sorted(cache)
    assert len(run_retrieval.draw_pool(cache, pair_ids, 0, "tempo_matched")) == 10
    for pid in pair_ids[2:]:
        cache[pid]["grid"] = beatgrid.BeatGrid(bpm=90.0, beat_times=cache[pid]["grid"].beat_times)
    assert run_retrieval.draw_pool(cache, pair_ids, 0, "tempo_matched") == [pair_ids[0]]
    matched = run_retrieval.draw_pool(cache, pair_ids, 5, "tempo_matched")
    assert len(matched) == 10 and pair_ids[0] not in matched and pair_ids[1] not in matched


def test_a_candidate_is_cut_on_the_querys_grid():
    cache = _store()
    cache["t00:bass"]["grid"] = beatgrid.BeatGrid(bpm=60.0, beat_times=np.arange(9) * 1.0)
    moved = run_retrieval.on_query_grid(cache, "t00:bass", "t05:bass")
    assert moved.beat_chroma.shape == (8, 12)
    assert cache["t05:bass"]["original"].beat_chroma.shape == (BEATS, 12)


def test_progression_finds_the_target_where_random_embeddings_cannot():
    report = run_retrieval.analyse(_store())
    assert report["n_queries"] == N_TRACKS * len(ROLES)
    for pool in run_retrieval.POOLS:
        scorers = report["pools"][pool]
        assert scorers["chroma_beat_aligned"]["recall@1"]["value"] == 1.0
        assert scorers["classic_onset"]["recall@1"]["value"] == 1.0
        assert scorers["clap_cos_mix"]["recall@1"]["value"] < 0.5
        gap = report["differences"][pool]["classic_onset - fusion5_online"]["recall@1"]
        assert gap["value"] > 0.5 and gap["ci95"][0] > 0
    assert set(report["by_role"]["same_role"]) == set(ROLES)
