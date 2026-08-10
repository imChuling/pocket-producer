"""Capacity measurement harness sanity checks."""

from ranking.capacity import measure_ladder
from ranking.context_model import LadderConfig

SMALL = LadderConfig(input_dim=32, d_model=16, structured_dim=4, low_rank=8)


def test_reports_all_three_ladder_rungs():
    report = measure_ladder(SMALL, repeats=3, batch_size=4, tokens=4)
    assert set(report["models"]) == {
        "linear-v1",
        "deepsets-v1",
        "pocketrank-context-v1",
    }


def test_parameters_increase_up_the_ladder_and_stay_in_budget():
    report = measure_ladder(SMALL, repeats=3, batch_size=4, tokens=4)
    models = report["models"]
    assert (
        models["linear-v1"]["trainable_parameters"]
        < models["deepsets-v1"]["trainable_parameters"]
        < models["pocketrank-context-v1"]["trainable_parameters"]
    )
    assert all(entry["within_budget"] for entry in models.values())


def test_latencies_positive_and_outputs_finite():
    report = measure_ladder(SMALL, repeats=3, batch_size=4, tokens=4)
    for entry in report["models"].values():
        assert entry["cpu_latency_ms_p50"] > 0
        assert entry["cpu_latency_ms_p95"] >= entry["cpu_latency_ms_p50"]
        assert entry["outputs_finite"] is True


def test_parameter_counts_are_deterministic():
    first = measure_ladder(SMALL, repeats=2, batch_size=2, tokens=3)
    second = measure_ladder(SMALL, repeats=2, batch_size=2, tokens=3)
    for model_id in first["models"]:
        assert (
            first["models"][model_id]["trainable_parameters"]
            == second["models"][model_id]["trainable_parameters"]
        )
