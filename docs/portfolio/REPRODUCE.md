# Reproduce the submission revision

This describes a local source revision; it is not a statement of what is
deployed. Video recording and demo materials are not part of it.

## Local regression checks

Use Python 3.11+ with the backend and research dependencies from
`backend/pyproject.toml`, plus lightning and efficientnet_pytorch for COCOLA.
Use a compatible Torch/torchvision pair; an incompatible pair fails at
test collection.
A writable Numba cache is needed under restricted filesystem permissions.

```bash
NUMBA_CACHE_DIR=/tmp/pocket-numba-cache python -m pytest \
  research/tests backend/tests/ranking backend/tests/api -q
cd frontend
pnpm install
pnpm run check
```

COCOLA-dependent tests require the external source/checkpoint. Missing
optional models may cause documented skips; a dependency import failure is
not a passing test. The existing test of a deliberately slow ranker logs
its eventual exception after timeout; assess the pytest exit code and counts.

## Frozen result checks

The committed JSONs are readable offline without credentials or audio.
The 2026-11-16 errata explain limitations and do not change those numbers.
`research/check_paper_numbers.py` is a partial legacy checker, not verification
of every new narrative claim; report its skips as well as its passes.

With the feature cache available, regenerate into a **new output directory**:

```bash
python -m research.compat_tests.run_behavioral report \
  --store /path/to/musdb18_v1 --output /tmp/behavioral-rerun --dataset musdb18hq
python -m research.compat_tests.run_retrieval \
  --store /path/to/musdb18_v1 --output /tmp/retrieval-rerun --dataset musdb18hq
```

Compare each regenerated `report.json` with the committed one by SHA256.
This reproduces cache-to-report computation,
not original-audio-to-feature extraction. The external COCOLA source commit
and checkpoint hash are recorded; the full historical extraction environment
and per-window raw-audio manifest were not independently reconstructed.
The cache identity/checksum manifest was captured **after** results on
2026-11-16; it must not be described as part of the original freeze.

## Evaluation and learning contracts

The guardrail CLI and feedback trainer default to
`research/manifests/musdb18-behavioral-v1-cache.json` (594 pair IDs / 149 song
IDs). A different development dataset requires an explicit `--manifest`
(guardrail) or `--guardrail-manifest` (trainer) with nonempty unique
`pair_ids` and `track_ids`. This checks identity, not file hashes or training
provenance. Cache file hashes are recorded for separate inspection.

```bash
python -m research.compat_tests.guardrail \
  --weights artifacts/fusion-deploy/weights.json --store /path/to/musdb18_v1 \
  --output /tmp/guardrail-verdict.json
```

No-data/incomplete/unusable endpoints reject before performance comparisons.
A complete evaluation protects only baseline-passing endpoints and the
specified gain win-rate criterion; it is not a quality floor for all five
endpoints, an equivalence test or independent held-out confirmation after
repeated model selection. Direct Python `check(..., manifest=None)` is an
unbound development check, not a claim of coverage of the 594-pair evaluation.

Feedback vectors are aligned by `candidate_signal_names`, and optional beat
measurements need an availability mask. Historical unnamed five-signal rows
use their known canonical order; ambiguous extended rows are refused.
Seven-signal artifacts are research-only. The online fusion loader accepts
its canonical five signals, not seven. Previous output/verdict files are
quarantined with run IDs before another training attempt so an old accepted
artifact cannot masquerade as a newly accepted run. Train-fit accuracy and
exposure-position logging do not prove generalization or remove position bias.
