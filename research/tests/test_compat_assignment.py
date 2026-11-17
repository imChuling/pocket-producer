"""Assignment over a small synthetic store with a known answer."""

import pathlib
import pickle
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import beatgrid, run_assignment, signals  # noqa: E402

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


def _features(rng, beat_chroma=None, onsets=None, vector=None) -> signals.ClipFeatures:
    return signals.ClipFeatures(
        embeddings={"msclap": rng.normal(size=16).astype(np.float32) if vector is None else vector},
        bpm=120.0,
        key="C major",
        chroma=list(np.ones(12) / np.sqrt(12)),
        beat_chroma=beat_chroma,
        onsets=onsets,
    )


def _store(role_vectors: bool = False) -> dict:
    """Stems of one track share a chord progression; stems of one type can share timbre.

    With role_vectors, every stem of a type has nearly the same MS-CLAP
    vector, as if the embedding heard only the instrument.
    """
    rng = np.random.default_rng(0)
    timbre = {role: rng.normal(size=16).astype(np.float32) for role in ROLES}
    cache = {}
    for track in range(N_TRACKS):
        period = 0.5
        grid = beatgrid.BeatGrid(bpm=120.0, beat_times=np.arange(BEATS + 1) * period)
        progression = _progression(track)
        onsets = np.zeros(BEATS * signals.ONSET_SUBDIVISIONS)
        onsets[:: signals.ONSET_SUBDIVISIONS] = 1.0
        for role in ROLES:
            vector = (
                timbre[role] + 0.01 * rng.normal(size=16).astype(np.float32)
                if role_vectors
                else None
            )
            cache[f"t{track:02d}:{role}"] = {
                "pair_id": f"t{track:02d}:{role}",
                "track": f"t{track:02d}",
                "role": role,
                "pitched": True,
                "grid": grid,
                "context_mix": _features(rng, progression, onsets),
                "regions": [_features(rng), _features(rng)],
                "original": _features(rng, progression, onsets, vector),
                "original_frames": _frames(progression, period),
                "perturbed": {},
            }
    return cache


def test_missing_or_empty_store_stops_with_a_message(tmp_path):
    with pytest.raises(SystemExit, match="Store not found"):
        run_assignment.check_store(tmp_path / "absent")
    (tmp_path / "._ghost.pkl").write_bytes(b"not a pickle")
    with pytest.raises(SystemExit, match="No stored pairs"):
        run_assignment.check_store(tmp_path)


def test_a_store_with_pairs_passes_the_check(tmp_path):
    (tmp_path / "t00_bass.pkl").write_bytes(pickle.dumps({"pair_id": "t00:bass"}))
    run_assignment.check_store(tmp_path)


def test_the_stem_is_heard_on_each_candidate_contexts_grid():
    cache = _store()
    cache["t05:bass"]["grid"] = beatgrid.BeatGrid(bpm=60.0, beat_times=np.arange(9) * 1.0)
    weights = signals.load_fusion_weights()
    table = run_assignment.score_contexts(
        cache, "t00:bass", ["t00:bass", "t05:bass"], weights, None
    )
    assert set(run_assignment.COMBINATIONS) <= set(table)
    assert all(len(scores) == 2 for scores in table.values())
    moved = run_assignment.on_query_grid(cache, "t05:bass", "t00:bass")
    assert moved.beat_chroma.shape == (8, 12)


def test_fit_finds_the_stems_own_project_where_random_embeddings_cannot():
    report = run_assignment.analyse(_store())
    assert report["n_queries"] == N_TRACKS * len(ROLES)
    assert report["cocola"] == "no stored COCOLA embeddings in this store"
    for pool in run_assignment.POOLS:
        scorers = report["pools"][pool]
        assert scorers["classic_onset"]["recall@1"]["value"] == 1.0
        assert scorers["clap_cos_mean"]["recall@1"]["value"] < 0.5
        for baseline in run_assignment.BASELINES:
            gap = report["differences"][pool][f"classic_onset - {baseline}"]["recall@1"]
            assert gap["value"] > 0.5 and gap["ci95"][0] > 0
        assert not any(name.startswith("cocola") for name in report["differences"][pool])
    assert set(report["by_role"]["same_role"]) == set(ROLES)


def test_nearest_neighbours_split_by_instrument_and_by_song():
    cache = _store(role_vectors=True)
    shares = run_assignment.nearest_neighbours(cache, sorted(cache))
    by_clap = shares["msclap_cosine"]
    by_fit = shares["classic_onset_stem_to_stem"]
    assert by_clap["n"] == by_fit["n"] == N_TRACKS * len(ROLES)
    assert by_clap["same_type_other_song"] == 1.0
    assert by_fit["other_type_same_song"] == 1.0


def test_relation_labels():
    cache = _store()
    assert run_assignment.relation(cache, "t00:bass", "t00:other") == "other_type_same_song"
    assert run_assignment.relation(cache, "t00:bass", "t03:bass") == "same_type_other_song"
    assert run_assignment.relation(cache, "t00:bass", "t03:other") == "other_type_other_song"
