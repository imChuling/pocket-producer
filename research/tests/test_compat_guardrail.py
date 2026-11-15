"""The guardrail on a small synthetic store with a known answer.

Every pair's original sounds like its session (high CLAP cosine) and other
tracks' originals do not, so the baseline passes P1. The 6 dB quieter copy is
identical to the original except for its chroma, which matches the session
better, so a weight on chroma_as_is makes a scorer prefer the quieter copy.
"""

import pathlib
import pickle
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import guardrail, perturb, signals  # noqa: E402

N_TRACKS = 14
DIM = 16


def _features(embedding, chroma, bpm=120.0):
    return signals.ClipFeatures(
        embeddings={"msclap": np.asarray(embedding, dtype=np.float32)},
        bpm=bpm,
        key=None,
        chroma=list(chroma),
    )


def _entry(index: int, rng) -> dict:
    session = rng.standard_normal(DIM)
    context_chroma = np.abs(rng.standard_normal(12)) + 0.1
    off_chroma = np.roll(context_chroma, 5)
    own = session + 0.1 * rng.standard_normal(DIM)
    original = _features(own, off_chroma)
    perturbed = {}
    for item in perturb.catalogue():
        if item.name == guardrail.GAIN_TEST:
            perturbed[item.name] = _features(own, context_chroma)
        elif item.family in ("pitch", "pitch_roundtrip", "varispeed", "beatshift"):
            perturbed[item.name] = _features(own + 0.3 * rng.standard_normal(DIM), off_chroma)
    return {
        "pair_id": f"track{index}:target",
        "track": f"track{index}",
        "role": "bass",
        "pitched": True,
        "grid": None,
        "context_mix": _features(session, context_chroma),
        "regions": [_features(session, context_chroma)],
        "original": original,
        "original_frames": None,
        "perturbed": perturbed,
    }


@pytest.fixture(scope="module")
def entries():
    rng = np.random.default_rng(3)
    return [_entry(i, rng) for i in range(N_TRACKS)]


@pytest.fixture(scope="module")
def baseline():
    return guardrail.WeightSet.from_file(guardrail.BASELINE_WEIGHTS)


def test_the_baseline_passes_p1_and_is_level_on_gain(entries, baseline):
    collected = guardrail.collect(entries, baseline.components())
    result = guardrail.endpoints(collected, baseline)
    assert result["P1"]["ci95"][0] > 0.5
    assert result["gain"]["wins"] == 0.5


def test_the_baseline_accepts_itself(entries, baseline):
    result = guardrail.check(baseline, entries, baseline)
    assert result["verdict"] == "accept"
    assert result["reasons"] == []


def test_weights_that_prefer_the_quieter_copy_are_rejected(entries, baseline):
    louder_is_worse = guardrail.WeightSet.of(
        [*baseline.signals, "chroma_as_is"], [*baseline.weights, 50.0]
    )
    result = guardrail.check(louder_is_worse, entries, baseline)
    assert result["verdict"] == "reject"
    assert any(reason.startswith("gain-6dB") for reason in result["reasons"])
    assert result["candidate"]["endpoints"]["gain"]["wins"] < 0.1


def test_weights_that_lose_a_passing_endpoint_are_rejected(entries, baseline):
    inverted = guardrail.WeightSet.of(
        baseline.signals, [-w if s.startswith("audio_cos") else w
                           for s, w in zip(baseline.signals, baseline.weights)]
    )
    result = guardrail.check(inverted, entries, baseline)
    assert result["verdict"] == "reject"
    assert any(reason.startswith("P1") for reason in result["reasons"])


def test_key_and_tags_are_zero_online(entries, baseline):
    """Weight on the deployed ranker's key and tag terms changes nothing here."""
    heavier = guardrail.WeightSet.of(
        baseline.signals,
        [w + (100.0 if s in ("key", "tag_jaccard") else 0.0)
         for s, w in zip(baseline.signals, baseline.weights)],
    )
    collected = guardrail.collect(entries, baseline.components())
    assert guardrail.endpoints(collected, heavier) == guardrail.endpoints(collected, baseline)


def test_store_is_read_one_file_at_a_time(entries, tmp_path, baseline):
    for entry in entries:
        (tmp_path / f"{entry['pair_id'].replace(':', '_')}.pkl").write_bytes(pickle.dumps(entry))
    (tmp_path / "._junk.pkl").write_bytes(b"not a pickle")
    result = guardrail.check(baseline, guardrail.iter_store(tmp_path), baseline)
    assert result["n_pairs"] == N_TRACKS


def test_unknown_signals_and_length_mismatches_are_refused():
    with pytest.raises(ValueError):
        guardrail.WeightSet.of(["loudness"], [1.0])
    with pytest.raises(ValueError):
        guardrail.WeightSet.of(["tempo", "onset_pattern"], [1.0])
