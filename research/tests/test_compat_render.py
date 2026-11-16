"""Report figures render from a small hand-written report, including gaps."""

import copy
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from research.compat_tests import render_report  # noqa: E402

FILES = [
    f"{stem}.{ext}"
    for stem in ("pass_matrix", "pitch_response", "artefact_inflation")
    for ext in ("png", "pdf")
]


def _summary(wins, lo, hi, drop=0.1):
    return {"n": 40, "wins": wins, "ci95": [lo, hi], "tie_rate": 0.0, "drop_in_sd": drop}


def _report():
    scorers = ["chroma_as_is", "cocola", "tempo"]
    tests = {}
    for value in (-3, 1, 3):
        tests[f"pitch{value:+d}"] = {
            "kind": "directional",
            "family": "pitch",
            "value": value,
            "control": "pitch_roundtrip",
            "scorers": {
                s: {
                    "vs_original": _summary(0.7, 0.55, 0.82, drop=0.2 * abs(value)),
                    "vs_control": _summary(0.6, 0.45, 0.72),
                }
                for s in scorers
            },
        }
    tests["pitch_roundtrip"] = {
        "kind": "control",
        "family": "pitch_roundtrip",
        "value": 1.0,
        "control": None,
        "scorers": {s: {"vs_original": _summary(0.55, 0.4, 0.68, drop=0.05)} for s in scorers},
    }
    for value in (0.94, 1.06):
        tests[f"tempo{value}"] = {
            "kind": "directional",
            "family": "tempo",
            "value": value,
            "control": "tempo_roundtrip",
            "scorers": {
                s: {"vs_original": _summary(0.8, 0.7, 0.9), "vs_control": _summary(0.5, 0.4, 0.6)}
                for s in scorers
            },
        }
    tests["beatshift4"] = {
        "kind": "directional",
        "family": "beatshift",
        "value": 4,
        "control": None,
        "scorers": {
            s: {"vs_original": _summary(0.6, 0.5, 0.7), "harmony_moves": _summary(0.3, 0.2, 0.4)}
            for s in scorers
        },
    }
    tests["beatshift0.37"] = {
        "kind": "directional",
        "family": "beatshift",
        "value": 0.37,
        "control": None,
        "scorers": {s: {"vs_original": _summary(0.5, 0.4, 0.6)} for s in scorers},
    }
    pooled = {
        name: {s: _summary(0.6, 0.52, 0.7) for s in scorers}
        for name in ("pitch_vs_control", "tempo_vs_control", "varispeed")
    }
    return {
        "scorers": scorers,
        "reference_true_vs_random": {s: _summary(0.9, 0.85, 0.95) for s in scorers},
        "pooled": pooled,
        "tests": tests,
    }


def _assert_files(directory: pathlib.Path):
    for name in FILES:
        path = directory / name
        assert path.is_file(), name
        assert path.stat().st_size > 0, name


def test_all_six_files_are_written(tmp_path):
    paths = render_report.render(_report(), tmp_path)
    assert sorted(p.name for p in paths) == sorted(FILES)
    _assert_files(tmp_path)


def test_a_missing_scorer_is_skipped(tmp_path):
    report = _report()
    report["scorers"].remove("cocola")
    for test in report["tests"].values():
        test["scorers"].pop("cocola", None)
    for pooled in report["pooled"].values():
        pooled.pop("cocola", None)
    report["reference_true_vs_random"].pop("cocola")
    render_report.render(report, tmp_path)
    _assert_files(tmp_path)


def test_missing_controls_and_pooled_entries_render(tmp_path):
    report = copy.deepcopy(_report())
    for test in report["tests"].values():
        for entry in test["scorers"].values():
            entry.pop("vs_control", None)
    del report["tests"]["pitch_roundtrip"]
    del report["pooled"]["tempo_vs_control"]
    report["tests"]["beatshift4"]["scorers"]["tempo"].pop("harmony_moves")
    render_report.render(report, tmp_path)
    _assert_files(tmp_path)


@pytest.mark.parametrize(
    "summary, expected",
    [
        ({"wins": 0.7, "ci95": [0.55, 0.8]}, "pass"),
        ({"wins": 0.3, "ci95": [0.2, 0.45]}, "reversed"),
        ({"wins": 0.52, "ci95": [0.4, 0.62]}, "blind"),
        (None, None),
    ],
)
def test_verdict(summary, expected):
    assert render_report.verdict(summary) == expected


def test_unknown_scorers_keep_their_names_and_land_in_other():
    report = _report()
    report["scorers"].append("new_signal")
    groups = render_report.grouped_scorers(report)
    assert groups[-1] == ("Other", ["new_signal"])
    assert render_report.display("new_signal") == "new_signal"


def test_out_of_scope_table_names_real_scorers_and_columns():
    columns = {key for key, _, _ in render_report.ENDPOINTS} | {render_report.CONTROL_COLUMN[0]}
    assert set(render_report.OUT_OF_SCOPE) <= set(render_report.DISPLAY_NAMES)
    for keys in render_report.OUT_OF_SCOPE.values():
        assert keys <= columns
    for general in ("clap_cos_mix", "laion_cos_mix", "fusion5_online", "cocola"):
        assert general not in render_report.OUT_OF_SCOPE


def test_hatched_cells_render(tmp_path):
    report = _report()
    report["scorers"].append("onset_pattern")
    for test in report["tests"].values():
        test["scorers"]["onset_pattern"] = copy.deepcopy(test["scorers"]["tempo"])
    for pooled in report["pooled"].values():
        pooled["onset_pattern"] = _summary(0.13, 0.05, 0.25)
    report["reference_true_vs_random"]["onset_pattern"] = _summary(0.93, 0.9, 0.96)
    render_report.render(report, tmp_path)
    _assert_files(tmp_path)
