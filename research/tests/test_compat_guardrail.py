"""The guardrail on a small synthetic store with a known answer.

Every pair's original sounds like its session (high CLAP cosine) and other
tracks' originals do not, so the baseline passes P1. The 6 dB quieter copy is
identical to the original except for its chroma, which matches the session
better, so a weight on chroma_as_is makes a scorer prefer the quieter copy.
"""

import copy
import json
import pathlib
import pickle
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import beatgrid, guardrail, perturb, signals  # noqa: E402

N_TRACKS = 14
DIM = 16


def _features(embedding, chroma, bpm=120.0):
    return signals.ClipFeatures(
        embeddings={"msclap": np.asarray(embedding, dtype=np.float32)},
        bpm=bpm,
        key=None,
        chroma=list(chroma),
        beat_chroma=np.tile(np.asarray(chroma), (8, 1)),
        onsets=np.tile([1.0, 0.0, 0.2, 0.0, 0.7, 0.0, 0.1, 0.0], 8),
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
    perturbed[guardrail.GAIN_TEST].beat_chroma = original.beat_chroma.copy()
    perturbed["beatshift4"].beat_chroma = 0.6 * original.beat_chroma + 0.4 * np.roll(
        original.beat_chroma, 3, axis=1
    )
    return {
        "pair_id": f"track{index}:target",
        "track": f"track{index}",
        "role": "bass",
        "pitched": True,
        "grid": beatgrid.BeatGrid(120.0, np.arange(9) * 0.5),
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


@pytest.mark.parametrize(
    "damage",
    [
        "empty",
        "missing_pitch",
        "missing_control",
        "missing_gain",
        "missing_beat",
        "single_track",
        "duplicate",
        "nonfinite",
        "no_p4",
    ],
)
def test_incomplete_or_invalid_store_fails_closed(entries, baseline, damage):
    data = copy.deepcopy(entries)
    if damage == "empty":
        data = []
    elif damage.startswith("missing_"):
        test = {
            "missing_pitch": next(
                n for n, t in guardrail._tests_needed().items() if t.family == "pitch"
            ),
            "missing_control": "pitch_roundtrip",
            "missing_gain": guardrail.GAIN_TEST,
            "missing_beat": "beatshift4",
        }[damage]
        del data[0]["perturbed"][test]
    elif damage == "single_track":
        for entry in data:
            entry["track"] = "only-song"
    elif damage == "duplicate":
        data.append(data[0])
    elif damage == "nonfinite":
        data[0]["original"].bpm = float("nan")
    else:
        for entry in data:
            entry["pitched"] = False
    result = guardrail.check(baseline, data, baseline)
    assert result["verdict"] == "reject"
    assert result["integrity"]["errors"]
    assert "baseline" not in result  # performance is not assessed on invalid data


@pytest.mark.parametrize(
    "names, weights",
    [
        (["tempo", "tempo"], [1, 2]),
        (["tempo"], [float("nan")]),
        (["tempo"], [float("inf")]),
        ([], []),
    ],
)
def test_invalid_weight_sets_are_refused(names, weights):
    with pytest.raises(ValueError):
        guardrail.WeightSet.of(names, weights)


def test_explicit_manifest_is_enforced(entries, baseline):
    manifest = {
        "pair_ids": [e["pair_id"] for e in entries],
        "track_ids": [e["track"] for e in entries],
    }
    assert guardrail.check(baseline, entries, baseline, manifest=manifest)["verdict"] == "accept"
    manifest["pair_ids"].append("missing:target")
    result = guardrail.check(baseline, entries, baseline, manifest=manifest)
    assert result["verdict"] == "reject"
    assert "manifest" in str(result["integrity"]["errors"])


def test_store_requires_only_protocol_applicable_perturbations(entries, baseline):
    data = copy.deepcopy(entries)
    entry = data[0]
    entry["pitched"] = False
    entry["grid"] = None
    for name, test in guardrail._tests_needed().items():
        if test.family in perturb.PITCHED_ONLY_FAMILIES or test.family == "beatshift":
            del entry["perturbed"][name]
    assert guardrail.check(baseline, data, baseline)["verdict"] == "accept"


def test_direct_decision_rejects_missing_endpoint_data():
    result = guardrail.decide({}, {})
    assert result["verdict"] == "reject"


def test_invalid_direct_weightset_is_a_structured_integrity_rejection(entries, baseline):
    invalid = guardrail.WeightSet(("tempo",), (float("nan"),))
    result = guardrail.check(invalid, entries, baseline)
    assert result["verdict"] == "reject" and result["integrity"]["errors"]
    assert "baseline" not in result


def test_cli_reports_invalid_weight_file_as_structured_verdict(monkeypatch, tmp_path):
    weights = tmp_path / "bad.json"
    weights.write_text(json.dumps({"signals": ["tempo"], "weights": [float("nan")]}))
    out = tmp_path / "verdict.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["guardrail", "--weights", str(weights), "--store", str(tmp_path), "--output", str(out)],
    )
    assert guardrail.main() == 1
    assert json.loads(out.read_text())["integrity"]["status"] == "invalid"



def test_cli_default_manifest_rejects_unexpected_subset(monkeypatch, tmp_path, entries, baseline):
    manifest = tmp_path / "expected.json"
    manifest.write_text(json.dumps({
        "pair_ids": [e["pair_id"] for e in entries] + ["missing:target"],
        "track_ids": [e["track"] for e in entries] + ["missing"],
    }))
    monkeypatch.setattr(guardrail, "DEFAULT_MANIFEST", manifest, raising=False)
    for index, entry in enumerate(entries):
        (tmp_path / f"{index}.pkl").write_bytes(pickle.dumps(entry))
    out = tmp_path / "verdict.json"
    monkeypatch.setattr(sys, "argv", ["guardrail", "--weights", str(guardrail.BASELINE_WEIGHTS),
                                    "--store", str(tmp_path), "--output", str(out)])
    assert guardrail.main() == 1
    assert "manifest" in str(json.loads(out.read_text())["integrity"]["errors"])


def test_unbound_direct_checks_are_labelled_development_only(entries, baseline):
    result = guardrail.check(baseline, entries, baseline)
    assert result["integrity"]["manifest_binding"] == "unbound-development-only"


@pytest.mark.parametrize("contents", ["null", "[]", "1", '"text"'])
def test_cli_refuses_nonobject_manifest(monkeypatch, tmp_path, entries, contents):
    manifest = tmp_path / "invalid-manifest.json"
    manifest.write_text(contents)
    for index, entry in enumerate(entries):
        (tmp_path / f"{index}.pkl").write_bytes(pickle.dumps(entry))
    out = tmp_path / "verdict.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "guardrail",
            "--weights",
            str(guardrail.BASELINE_WEIGHTS),
            "--store",
            str(tmp_path),
            "--manifest",
            str(manifest),
            "--output",
            str(out),
        ],
    )
    assert guardrail.main() == 1
    verdict = json.loads(out.read_text())
    assert verdict["integrity"]["status"] == "invalid"
    assert "manifest must be a JSON object" in str(verdict["integrity"]["errors"])
