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
        requests.append({
            "request_id": rid,
            "model_id_served": "fusion-5sig-v1",
            "fragment_ids": ["good", "bad"],
            "candidate_signals": [positive, negative],
        })
        feedback += [
            {"request_id": rid, "fragment_id": "good", "event": "insert"},
            {"request_id": rid, "fragment_id": "bad", "event": "reject"},
        ]
    req, fb = tmp_path / "requests.jsonl", tmp_path / "feedback.jsonl"
    req.write_text("\n".join(json.dumps(r) for r in requests))
    fb.write_text("\n".join(json.dumps(f) for f in feedback))
    return req, fb


def _run(monkeypatch, tmp_path, store, req, fb, *extra_args):
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
    assert written["signals"][-2:] == EXTRA
    assert len(written["weights"]) == 7
    assert written["guardrail"]["verdict"] == "accept"
    assert written["weights"][5] > 0 and written["weights"][6] > 0


def test_lists_logged_before_the_extra_signals_are_ignored(monkeypatch, tmp_path, store):
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0], [0.5, 0.6, 0.4, 0, 0])
    code, out = _run(monkeypatch, tmp_path, store, req, fb)
    assert code == 1
    assert not out.exists()


def test_a_missing_store_writes_nothing(monkeypatch, tmp_path):
    req, fb = _logs(tmp_path, [0.6, 0.7, 0.9, 0, 0, 0.8, 0.7], [0.5, 0.6, 0.4, 0, 0, 0.2, 0.3])
    code, out = _run(monkeypatch, tmp_path, tmp_path / "no-store", req, fb)
    assert code == 1
    assert not out.exists()
    assert not (out.parent / "guardrail.json").exists()
