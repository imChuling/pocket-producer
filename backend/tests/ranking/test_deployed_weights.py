"""The container ships its own copy of the fusion weights; it must match the research artifact."""

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]


def test_backend_weights_copy_is_identical_to_the_artifact():
    shipped = REPO / "backend" / "artifacts" / "fusion-deploy" / "weights.json"
    source = REPO / "artifacts" / "fusion-deploy" / "weights.json"
    assert shipped.read_bytes() == source.read_bytes()
