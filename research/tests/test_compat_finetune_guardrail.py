"""Fine-tuning from feedback writes weights only when the guardrail accepts them."""

import importlib.util
import json
import pathlib
import pickle
import sys

import numpy as np
import pytest

RESEARCH = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH.parent))

EXTRA = ["chroma_beat_aligned", "onset_pattern"]


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


finetune = _load("finetune_from_feedback", RESEARCH / "finetune_from_feedback.py")
synthetic = _load("guardrail_store", RESEARCH / "tests" / "test_compat_guardrail.py")


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    path = tmp_path_factory.mktemp("store")
    rng = np.random.default_rng(3)
    for i in range(synthetic.N_TRACKS):
        entry = synthetic._entry(i, rng)
        (path / f"pair{i}.pkl").write_bytes(pickle.dumps(entry))
    return path


def _logs(tmp_path, positive, negative, n_lists=30):
    """Served lists with one accepted and one rejected fragment each."""
    requests, feedback = [], []
    for i in range(n_lists):
        rid = f"r{i}"
        requests.append(
            {
                "request_id": rid,
                "model_id_served": "fusion-5sig-v1",
                "fragment_ids": ["good", "bad"],
                "candidate_signals": [positive, negative],
                "candidate_signal_names": [*finetune.SIGNAL_NAMES, *EXTRA]
                if len(positive) == 7
                else finetune.SIGNAL_NAMES,
                "candidate_signal_available": [[True] * len(positive), [True] * len(negative)],
            }
        )
        feedback += [
            {"request_id": rid, "fragment_id": "good", "event": "insert"},
            {"request_id": rid, "fragment_id": "bad", "event": "reject"},
        ]
    req, fb = tmp_path / "requests.jsonl", tmp_path / "feedback.jsonl"
    req.write_text("\n".join(json.dumps(r) for r in requests))
    fb.write_text("\n".join(json.dumps(f) for f in feedback))
    return req, fb


def _run(monkeypatch, tmp_path, store, req, fb, *extra_args, manifest=True):
    out = tmp_path / "out" / "weights.json"
    argv = [
        "finetune_from_feedback.py",
        "--requests", str(req), "--feedback", str(fb),
        "--weights", str(finetune.REPO / "artifacts" / "fusion-deploy" / "weights.json"),
        "--output", str(out),
        "--extra-signals", ",".join(EXTRA),
        "--guardrail-store", str(store),
        *extra_args,
    ]
    if manifest:
        entries = [pickle.loads(path.read_bytes()) for path in store.glob("*.pkl")]
        manifest_path = tmp_path / "fixture-manifest.json"
        manifest_path.write_text(json.dumps({
            "pair_ids": [entry["pair_id"] for entry in entries],
            "track_ids": sorted({entry["track"] for entry in entries}),
        }))
        argv.extend(["--guardrail-manifest", str(manifest_path)])
    monkeypatch.setattr(sys, "argv", argv)
    return finetune.main(), out


def test_decisions_against_audio_similarity_are_rejected_and_not_written(
    monkeypatch, tmp_path, store
):
    # The musician keeps choosing the fragment that sounds least like the session.
    req, fb = _logs(tmp_path, [0.1, 0.1, 0.5, 0, 0, 0, 0], [0.9, 0.9, 0.5, 0, 0, 0, 0])
    code, out = _run(monkeypatch, tmp_path, store, req, fb, "--l2", "0", "--lr", "0.5")
    assert code == 2
    assert not out.exists()
    verdict = json.loads((out.parent / "guardrail.json").read_text())
    assert verdict["verdict"] == "reject"
    assert any(reason.startswith("P1") for reason in verdict["reasons"])


def test_mild_decisions_pass_and_write_seven_signal_weights(monkeypatch, tmp_path, store):
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0, 0.8, 0.7], [0.5, 0.6, 0.4, 0, 0, 0.2, 0.3])
    code, out = _run(monkeypatch, tmp_path, store, req, fb)
    assert code == 0
    written = json.loads(out.read_text())
    assert written["research_only"] is True
    assert written["deployable"] is False
    assert written["model_id"] != "fusion-5sig-v1"
    with pytest.raises(ValueError, match="research"):
        finetune.load_weights(out)
    assert written["signals"][-2:] == EXTRA
    assert len(written["weights"]) == 7
    assert written["guardrail"]["verdict"] == "accept"
    assert written["weights"][5] > 0 and written["weights"][6] > 0


def test_lists_logged_before_the_extra_signals_are_ignored(monkeypatch, tmp_path, store):
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0], [0.5, 0.6, 0.4, 0, 0])
    rows = [json.loads(line) for line in req.read_text().splitlines()]
    for row in rows:
        row.pop("candidate_signal_names")
    req.write_text("\n".join(json.dumps(row) for row in rows))
    code, out = _run(monkeypatch, tmp_path, store, req, fb)
    assert code == 1
    assert not out.exists()


def test_a_missing_store_writes_nothing(monkeypatch, tmp_path):
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0, 0.8, 0.7], [0.5, 0.6, 0.4, 0, 0, 0.2, 0.3])
    code, out = _run(monkeypatch, tmp_path, tmp_path / "no-store", req, fb)
    assert code == 1
    assert not out.exists()
    assert not (out.parent / "guardrail.json").exists()



def test_five_signal_training_artifact_loads_and_scores_online(monkeypatch, tmp_path, store):
    from ranking.fusion_ranker import FusionRanker
    from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint

    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0], [0.5, 0.6, 0.4, 0, 0])
    code, out = _run(monkeypatch, tmp_path, store, req, fb, "--extra-signals", "")
    assert code == 0
    artifact = finetune.load_weights(out)
    assert artifact["research_only"] is False and artifact["deployable"] is True
    response = FusionRanker(artifact).rank(
        RankRequest(
            session=SessionFingerprint(
                project_id="p",
                playhead_seconds=0,
                track_count=1,
                region_audio_embeddings=[[1, 0, 0]],
                bpm=120,
            ),
            candidates=[
                FragmentCandidate(
                    fragment_id="near",
                    duration_seconds=4,
                    created_at_iso="2026-07-01T00:00:00Z",
                    audio_url="/audio",
                    audio_embedding=[1, 0, 0],
                )
            ],
        )
    )
    assert response.candidates[0].fragment_id == "near"
    assert np.isfinite(response.candidates[0].score)


def test_reversed_extra_order_preserves_training_semantics(monkeypatch, tmp_path, store):
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0, 0.85, 0.6], [0.5, 0.6, 0.4, 0, 0, 0.1, 0.4])
    code, out = _run(monkeypatch, tmp_path, store, req, fb)
    assert code == 0
    forward = json.loads(out.read_text())
    code, out = _run(
        monkeypatch, tmp_path, store, req, fb, "--extra-signals", ",".join(reversed(EXTRA))
    )
    assert code == 0
    reverse = json.loads(out.read_text())
    assert dict(zip(forward["signals"], forward["weights"])) == pytest.approx(
        dict(zip(reverse["signals"], reverse["weights"])), rel=1e-12, abs=1e-14
    )


def test_rejected_rerun_quarantines_existing_weights(monkeypatch, tmp_path, store):
    req, fb = _logs(tmp_path, [0.1, 0.1, 0.5, 0, 0, 0, 0], [0.9, 0.9, 0.5, 0, 0, 0, 0])
    out = tmp_path / "out" / "weights.json"
    out.parent.mkdir()
    out.write_text('{"stale": true}')
    code, out = _run(monkeypatch, tmp_path, store, req, fb, "--l2", "0", "--lr", "0.5")
    assert code == 2
    assert not out.exists()
    previous = list(out.parent.glob("weights.json.previous-*"))
    assert len(previous) == 1 and json.loads(previous[0].read_text()) == {"stale": True}


def test_empty_store_cannot_release_weights(monkeypatch, tmp_path):
    store = tmp_path / "empty"
    store.mkdir()
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0, 0.8, 0.7], [0.5, 0.6, 0.4, 0, 0, 0.2, 0.3])
    code, out = _run(monkeypatch, tmp_path, store, req, fb)
    assert code == 2
    assert not out.exists()
    assert (
        json.loads((out.parent / "guardrail.json").read_text())["integrity"]["status"] == "invalid"
    )


def test_trainer_default_manifest_rejects_truncated_store(monkeypatch, tmp_path, store):
    from research.compat_tests import guardrail

    manifest_path = tmp_path / "expected.json"
    manifest_path.write_text(json.dumps({"pair_ids": ["missing"], "track_ids": ["missing"]}))
    monkeypatch.setattr(guardrail, "DEFAULT_MANIFEST", manifest_path, raising=False)
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0, 0.8, 0.7], [0.5, 0.6, 0.4, 0, 0, 0.2, 0.3])
    code, out = _run(monkeypatch, tmp_path, store, req, fb, manifest=False)
    assert code == 2
    assert not out.exists()
    verdict = json.loads((out.parent / "guardrail.json").read_text())
    assert "manifest" in str(verdict["integrity"]["errors"])


def test_exact_serialized_vector_is_the_guarded_vector(monkeypatch, tmp_path, store):
    from research.compat_tests import guardrail

    # These preserve every linear comparison before serialization, but rounding
    # to six decimals would erase all distinctions and lose the P1 baseline pass.
    tiny = (
        np.asarray(
            finetune.load_weights(finetune.REPO / "artifacts/fusion-deploy/weights.json")["weights"]
        )
        * 1e-9
    )
    monkeypatch.setattr(finetune, "finetune_weights", lambda *args, **kwargs: tiny.copy())
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0], [0.5, 0.6, 0.4, 0, 0])
    code, out = _run(monkeypatch, tmp_path, store, req, fb, "--extra-signals", "")
    assert code == 0
    written = json.loads(out.read_text())
    verdict = json.loads((out.parent / "guardrail.json").read_text())
    assert written["weights"] == verdict["candidate"]["weights"]["weights"]
    rechecked = guardrail.check(
        guardrail.WeightSet.of(written["signals"], written["weights"]),
        guardrail.iter_store(store),
        manifest=json.loads((tmp_path / "fixture-manifest.json").read_text()),
    )
    assert rechecked["verdict"] == "accept"


@pytest.mark.parametrize("contents", [None, "not json", "null", "[]", "1", '"text"'])
def test_unreadable_manifest_is_a_structured_rejection(monkeypatch, tmp_path, store, contents):
    manifest = tmp_path / "invalid-manifest.json"
    if contents is not None:
        manifest.write_text(contents)
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0, 0.8, 0.7], [0.5, 0.6, 0.4, 0, 0, 0.2, 0.3])
    code, out = _run(
        monkeypatch, tmp_path, store, req, fb, "--guardrail-manifest", str(manifest), manifest=False
    )
    assert code == 2
    assert not out.exists()
    verdict = json.loads((out.parent / "guardrail.json").read_text())
    assert verdict["integrity"]["status"] == "invalid"
    if contents not in (None, "not json"):
        assert "manifest must be a JSON object" in str(verdict["integrity"]["errors"])
