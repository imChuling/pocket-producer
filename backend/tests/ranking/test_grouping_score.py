"""Pairwise fusion score used to decide project membership."""

import pytest

from ranking.grouping import pair_fusion_score, pair_signals

W = [6.8, 8.3, 2.0, 0.4, 1.5]


def score(**kw):
    base = dict(vec_a=[1.0, 0.0], vec_b=[1.0, 0.0], bpm_a=120.0, bpm_b=120.0,
                key_a="Am", key_b="a minor", tags_a=["Bass"], tags_b=["bass"])
    base.update(kw)
    return pair_fusion_score(W, **base)


def test_identical_pair_takes_every_term():
    assert score() == pytest.approx(sum(W))


def test_cosine_fills_both_audio_terms():
    signals = pair_signals([1.0, 0.0], [0.0, 1.0], None, None, None, None, [], [])
    assert signals == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_score_is_symmetric():
    a = score(bpm_a=100.0, bpm_b=120.0, vec_b=[0.6, 0.8], tags_b=["bass", "dark"])
    b = pair_fusion_score(W, [0.6, 0.8], [1.0, 0.0], 120.0, 100.0, "a minor", "Am",
                          ["bass", "dark"], ["Bass"])
    assert a == pytest.approx(b)


def test_compact_and_spoken_keys_match():
    with_key = score()
    without = score(key_b="C")
    assert with_key - without == pytest.approx(W[3])


@pytest.mark.parametrize("vec_b", [[0.0, 0.0], [1.0], [float("nan"), 1.0]])
def test_unusable_vectors_raise(vec_b):
    with pytest.raises(ValueError):
        score(vec_b=vec_b)
