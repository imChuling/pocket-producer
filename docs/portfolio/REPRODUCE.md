# Reproduce the results

How to rerun the tests and regenerate the reported results from the source
tree. What is deployed is described in the README.

## Tests

You need Python 3.11+ with the backend and research dependencies from
`backend/pyproject.toml`, plus `lightning` and `efficientnet_pytorch` for the
COCOLA comparison. Torch and torchvision have to be a compatible pair, or the
tests fail while they are being collected. On a machine with restricted file
permissions, point Numba at a writable cache:

```bash
NUMBA_CACHE_DIR=/tmp/pocket-numba-cache python -m pytest \
  research/tests backend/tests/ranking backend/tests/api -q
cd frontend
pnpm install
pnpm run check
```

The COCOLA tests need its source and checkpoint from a separate checkout and
skip without them. An import error from a missing dependency is a failure,
not a skip. One test uses a deliberately slow ranker, which logs an exception
after its timeout; judge the run by the pytest exit code and counts.

## Committed results

The committed result JSONs can be read offline, with no credentials or audio.
The dated errata in the protocols (2026-11-16) explain their limits without
changing any number. `research/check_paper_numbers.py` checks the numbers in
the paper against these files; it does not cover every statement in the
documentation, and its skips should be reported along with its passes.

With the MUSDB18-HQ feature cache available, regenerate each study into a
new output directory:

```bash
python -m research.compat_tests.run_behavioral report \
  --store /path/to/musdb18_v1 --output /tmp/behavioral-rerun --dataset musdb18hq
python -m research.compat_tests.run_retrieval \
  --store /path/to/musdb18_v1 --output /tmp/retrieval-rerun --dataset musdb18hq
python -m research.compat_tests.run_assignment \
  --store /path/to/musdb18_v1 --output /tmp/assignment-rerun
```

Then compare each new `report.json` with the committed one by SHA-256. This
reruns the step from cached features to report; it does not re-extract the
features from the original audio. The COCOLA source commit and checkpoint
hash are recorded, but the full extraction environment and a per-window
manifest of the raw audio were not rebuilt. The cache identity manifest was
written on 2026-11-16, after the results, so it documents the cache rather
than being part of the original freeze.

## The behavioural guardrail and feedback training

The guardrail and the feedback trainer use
`research/manifests/musdb18-behavioral-v1-cache.json` by default (594 pair IDs
from 149 songs). For any other dataset, pass `--manifest` to the guardrail or
`--guardrail-manifest` to the trainer, listing non-empty, unique `pair_ids`
and `track_ids`. This checks which pairs and songs are used, not file hashes
or where the training data came from; the cache file hashes are recorded
separately.

```bash
python -m research.compat_tests.guardrail \
  --weights artifacts/fusion-deploy/weights.json --store /path/to/musdb18_v1 \
  --output /tmp/guardrail-verdict.json
```

An evaluation with missing or unusable endpoints is rejected before any
comparison. A complete one only protects the endpoints the baseline already
passes, plus the gain win-rate criterion. It is not a minimum standard for
all five endpoints, an equivalence test, or a fresh held-out confirmation
after repeated model selection. Calling `check(..., manifest=None)` directly
from Python is a development shortcut and does not tie the result to the
594-pair set.

Each training pair compares a proposal with a retained logged insertion to an
explicitly rejected proposal in the same served list. The join drops feedback
marked unverified and rows with conflicting participant hashes. An accept
without a logged insert counts as an attempt, not as a positive. Retries for
the same region ID count once, and undo cancels that region. Older exports
lack region IDs, so the trainer counts unmatched insertions in server
timestamp order, using file order for ties or undated histories. Duplicate
events and incorrect attribution in those older logs cannot be resolved.
Manual DAW edits and missing telemetry also limit what the recorded outcomes
establish.

The feedback report groups Beat Fit lists by the revision that served them.
For older lists it uses the logged signal names to distinguish full-window
from shared-beat measurements. Lists without either field have their own
unknown-revision group.

Feedback vectors are matched by `candidate_signal_names`, and optional beat
measurements need an availability mask. Older unnamed five-signal rows are
read in their known order; extended rows that are ambiguous are refused.
Seven-signal weights are for research only: the online fusion loader accepts
exactly its five signals. Before each training attempt, earlier output and
verdict files are renamed with a run ID, so an old accepted file cannot be
mistaken for a new one. Accuracy on the training pairs and logged display
positions do not show that the weights generalise or that position bias is
gone.
