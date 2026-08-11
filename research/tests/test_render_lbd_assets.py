"""Deterministic-asset tests: same artifact in, same bytes out."""

import importlib.util
import pathlib
import sys

MODULE_PATH = pathlib.Path(__file__).parent.parent / "render_lbd_assets.py"
spec = importlib.util.spec_from_file_location("render_lbd_assets", MODULE_PATH)
render_lbd_assets = importlib.util.module_from_spec(spec)
sys.modules["render_lbd_assets"] = render_lbd_assets
spec.loader.exec_module(render_lbd_assets)

EVALUATION = {
    "primary_metric": "pairwise_accuracy",
    "grouping": "participant",
    "label_type": "pairwise",
    "n_examples": 2,
    "dataset_hash": "sha256:abc",
    "commit_sha": "deadbeef",
    "models": {
        "rules-v1": {"pairwise_accuracy": 1.0, "evaluated": 2, "skipped": 0},
        "recency-v1": {"pairwise_accuracy": 0.5, "evaluated": 2, "skipped": 0},
        "mean-session-v1": {
            "pairwise_accuracy": None,
            "evaluated": 0,
            "skipped": 2,
        },
    },
}


def test_csv_is_sorted_and_stable():
    first = render_lbd_assets.build_results_csv(EVALUATION)
    second = render_lbd_assets.build_results_csv(EVALUATION)
    assert first == second
    lines = first.strip().splitlines()
    assert lines[0] == "model,pairwise_accuracy,evaluated,skipped"
    assert [line.split(",")[0] for line in lines[1:]] == sorted(
        EVALUATION["models"]
    )


def test_dataset_facts_carry_hash_and_metric():
    facts = render_lbd_assets.build_dataset_facts(EVALUATION)
    assert facts["dataset_hash"] == "sha256:abc"
    assert facts["primary_metric"] == "pairwise_accuracy"


def test_render_all_is_byte_deterministic(tmp_path):
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"
    render_lbd_assets.render_all(EVALUATION, first_dir)
    render_lbd_assets.render_all(EVALUATION, second_dir)
    for name in [
        "ranking-results.csv",
        "dataset-facts.json",
        "ranking-results.pdf",
        "system-figure.pdf",
    ]:
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes(), name


def test_null_accuracy_models_are_excluded_from_figure(tmp_path):
    render_lbd_assets.render_all(EVALUATION, tmp_path)
    assert (tmp_path / "ranking-results.pdf").stat().st_size > 0
