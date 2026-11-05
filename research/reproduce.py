"""Re-run the paper's result chain and compare it with the committed artifacts.

Runs, in order, the scripts behind every paper-facing artifact (see
research/README.md for what each one is), writes their outputs to a scratch
directory, and reports the largest numeric difference against the versions
committed under artifacts/. Standard library only, so it runs the same on
macOS, Linux and Windows; the scripts it calls need numpy and the backend
package (research/README.md, "Prerequisites").

    python research/reproduce.py                 # everything, about 20 minutes
    python research/reproduce.py --only fusion   # one step
    python research/reproduce.py --out my-run    # keep the outputs
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "research" / "data" / "fsld"
ART = ROOT / "artifacts"

# Fields that legitimately differ between runs (wall-clock, environment).
IGNORED_KEYS = {
    "created_at", "generated_at", "timestamp", "run_at", "date",
    "elapsed_seconds", "runtime_seconds", "duration_seconds",
    "python_version", "numpy_version", "host", "hostname", "git_commit",
}
TOLERANCE = 1e-6

STEPS = [
    {
        "name": "split",
        "paper": "section 3: 605 sources, 484 train / 121 held-out, seed 20260810",
        "script": "make_heldout_split.py",
        "args": ["--items", "{data}/items_laion-clap-music_packonly.jsonl",
                 "--seed", "20260810", "--fraction", "0.2",
                 "--output", "{out}/heldout-split-packonly/split.json"],
        "compare": ("heldout-split-packonly/split.json", "heldout-split-packonly/split.json"),
    },
    {
        "name": "fusion",
        "paper": "section 3: dev-set cosine 0.929 / 0.8136 vs fusion 0.925 / 0.8133",
        "script": "run_fusion.py",
        "args": ["--items", "{data}/items_laion-clap-music_packonly_train.jsonl",
                 "--output", "{out}/fusion-packonly"],
        "compare": ("fusion-packonly/fusion.json", "fusion-packonly/fusion.json"),
    },
    {
        "name": "ablation",
        "paper": "section 4: leave-one-signal-out, tempo -0.96 pp / +0.68 pp",
        "script": "run_ablation.py",
        "args": ["--items", "{data}/items_laion-clap-music_packonly_train.jsonl",
                 "--output", "{out}/ablation-packonly"],
        "compare": ("ablation-packonly/ablation.json", "ablation-packonly/ablation.json"),
    },
    {
        "name": "heldout-laion",
        "paper": "Table 1, LAION-CLAP column",
        "script": "run_heldout_correction.py",
        "args": ["--items", "{data}/items_laion-clap-music_packonly.jsonl",
                 "--split", "{art}/heldout-split-packonly/split.json",
                 "--output", "{out}/heldout-eval-correction", "--mode", "laion"],
        "compare": ("heldout-eval-correction/sensitivity.json",
                    "heldout-eval-correction/sensitivity.json"),
    },
    {
        "name": "heldout-msclap",
        "paper": "Table 1, MS-CLAP + source-weighted BPR column",
        "script": "run_heldout_correction.py",
        "args": ["--items", "{data}/items_msclap_packonly.jsonl",
                 "--split", "{art}/heldout-split-packonly/split.json",
                 "--output", "{out}/msclap-sensitivity-correction", "--mode", "msclap"],
        "compare": ("msclap-sensitivity-correction/sensitivity.json",
                    "msclap-sensitivity-correction/sensitivity.json"),
    },
    {
        "name": "weights",
        "paper": "section 2.4: the deployed fusion-5sig-v1 weights",
        "script": "export_fusion_weights.py",
        "args": ["--items", "{data}/items_msclap_packonly_train.jsonl",
                 "--output", "{out}/fusion-deploy/weights.json"],
        "compare": ("fusion-deploy/weights.json", "fusion-deploy/weights.json"),
    },
]


def diff(a, b, path="") -> tuple[float, list[str]]:
    """Largest absolute numeric difference and a list of structural mismatches."""
    if isinstance(a, dict) and isinstance(b, dict):
        worst, notes = 0.0, []
        for key in sorted(set(a) | set(b)):
            if key in IGNORED_KEYS:
                continue
            if key not in a or key not in b:
                notes.append(f"{path}/{key}: only in {'committed' if key in b else 'fresh'}")
                continue
            w, n = diff(a[key], b[key], f"{path}/{key}")
            worst, notes = max(worst, w), notes + n
        return worst, notes
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return math.inf, [f"{path}: length {len(a)} vs {len(b)}"]
        worst, notes = 0.0, []
        for i, (x, y) in enumerate(zip(a, b)):
            w, n = diff(x, y, f"{path}[{i}]")
            worst, notes = max(worst, w), notes + n
        return worst, notes
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str):
        return (0.0, []) if a == b else (math.inf, [f"{path}: {a!r} vs {b!r}"])
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if (a is None) != (b is None):
            return math.inf, [f"{path}: {a!r} vs {b!r}"]
        return abs(float(a) - float(b)), []
    if a is None and b is None:
        return 0.0, []
    return math.inf, [f"{path}: {type(a).__name__} vs {type(b).__name__}"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="directory for fresh outputs (default: temporary)")
    parser.add_argument("--only", action="append", help="run only this step (repeatable)")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE)
    args = parser.parse_args()

    missing = [p for p in DATA.glob("items_*.jsonl")]
    if not missing:
        print("no embedding files in research/data/fsld; run research/fetch_embeddings.py first",
              file=sys.stderr)
        return 2

    tmp = None
    if args.out:
        out = pathlib.Path(args.out).resolve()
    else:
        tmp = tempfile.TemporaryDirectory(prefix="pocket-producer-repro-")
        out = pathlib.Path(tmp.name)
    out.mkdir(parents=True, exist_ok=True)

    steps = [s for s in STEPS if not args.only or s["name"] in args.only]
    failures = 0
    print(f"{'step':16} {'time':>7}  {'max |diff|':>11}  result")
    for step in steps:
        fmt = {"data": str(DATA), "out": str(out), "art": str(ART)}
        cmd = [sys.executable, str(ROOT / "research" / step["script"])]
        cmd += [a.format(**fmt) for a in step["args"]]
        started = time.time()
        # UTF-8 mode: the items files carry non-ASCII tags, and Windows would
        # otherwise read them with the console code page.
        env = {**os.environ, "PYTHONUTF8": "1"}
        run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
        elapsed = time.time() - started
        if run.returncode != 0:
            failures += 1
            print(f"{step['name']:16} {elapsed:6.0f}s  {'':>11}  FAILED to run")
            print(run.stderr.strip().splitlines()[-1] if run.stderr.strip() else run.stdout[-500:])
            continue
        fresh_rel, committed_rel = step["compare"]
        fresh = json.loads((out / fresh_rel).read_text())
        committed = json.loads((ART / committed_rel).read_text())
        worst, notes = diff(fresh, committed)
        ok = worst <= args.tolerance and not notes
        failures += 0 if ok else 1
        print(f"{step['name']:16} {elapsed:6.0f}s  {worst:11.2e}  {'PASS' if ok else 'DIFFERS'}"
              f"   {step['paper']}")
        for note in notes[:5]:
            print(f"    {note}")
    if tmp is not None:
        tmp.cleanup()
    print()
    print("all steps match the committed artifacts" if failures == 0
          else f"{failures} step(s) differ or failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
