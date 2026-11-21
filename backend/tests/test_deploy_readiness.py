import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(("probe_status", "ready"), [(0, True), (22, False)])
def test_deploy_exits_according_to_readiness(tmp_path, probe_status, ready):
    for name, body in {
        "gcloud": "echo https://unused.invalid",
        "curl": f"exit {probe_status}",
        "sleep": "exit 0",
    }.items():
        stub = tmp_path / name
        stub.write_text(f"#!/bin/sh\n{body}\n")
        stub.chmod(0o755)

    script = Path(__file__).resolve().parents[1] / "deploy" / "deploy.sh"
    result = subprocess.run(
        ["bash", str(script), "--config"], capture_output=True, text=True,
        env={**os.environ, "PATH": f"{tmp_path}:/usr/bin:/bin"}, check=False,
    )
    assert (result.returncode == 0) is ready, result.stdout + result.stderr
