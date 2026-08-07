# Reproducing the ISMIR 2026 LBD Results

Every number in the paper is derived from versioned artifacts in `artifacts/`.
This document maps each table and prose claim to the script that produced it
and the command to re-run it.

## Prerequisites

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Embedding files (`items.jsonl`, `items_laion-clap-music.jsonl`) are in
`research/data/fsld/` and require ~200 MB. Chroma and role prompt features
are precomputed in the same directory.

## Reproduction commands

### Table 1: Backbone bake-off

```bash
backend/.venv/bin/python research/run_bakeoff.py \
  --items research/data/fsld/items.jsonl \
  --output artifacts/backbone-bakeoff.json
```

### Table 2: Baseline comparison and fusion (LAION-CLAP)

```bash
# 5-signal fusion (produces artifacts/fusion/fusion.json)
backend/.venv/bin/python research/run_fusion.py \
  --items research/data/fsld/items_laion-clap-music.jsonl \
  --output artifacts/fusion

# 7-signal fusion with session-structure signals
backend/.venv/bin/python research/run_fusion.py \
  --items research/data/fsld/items_laion-clap-music.jsonl \
  --chroma research/data/fsld/chroma.jsonl \
  --role-prompts research/data/fsld/role_prompts.json \
  --output artifacts/fusion-7sig
```

### Cross-space replication (MS-CLAP, deployed)

```bash
backend/.venv/bin/python research/run_fusion.py \
  --items research/data/fsld/items.jsonl \
  --chroma research/data/fsld/chroma.jsonl \
  --role-prompts research/data/fsld/role_prompts.json \
  --output artifacts/fusion-msclap
```

### Signal-human alignment (Section 3.4)

```bash
backend/.venv/bin/python research/human_signal_alignment.py
# Output: artifacts/human-signal-alignment/alignment.json
```

### Precomputed features (chroma + role prompts)

```bash
backend/.venv/bin/python research/extract_fsld_features.py \
  --items research/data/fsld/items_laion-clap-music.jsonl \
  --output-chroma research/data/fsld/chroma.jsonl \
  --output-role-prompts research/data/fsld/role_prompts.json
```

## Verification

### Number consistency check

Cross-checks every statistical claim in the paper against artifact JSONs:

```bash
python research/check_paper_numbers.py
```

### Unit tests (signal functions)

```bash
backend/.venv/bin/python -m pytest backend/tests/ranking/test_features.py \
  backend/tests/ranking/test_harmonic.py \
  backend/tests/ranking/test_role_probe.py \
  backend/tests/ranking/test_fusion.py -v
```

### Build paper

```bash
docs/ismir2026/build.sh
# Runs number check → stages to /tmp → tectonic build → page count assertion
```

## Artifact inventory

| Artifact | Source script | Paper reference |
|----------|-------------|-----------------|
| `artifacts/backbone-bakeoff.json` | `run_bakeoff.py` | Table 1 |
| `artifacts/fusion/fusion.json` | `run_fusion.py` | Table 2, Section 3.2 |
| `artifacts/fusion-7sig/fusion.json` | `run_fusion.py` | Table 2 (rows 4-6), Section 3.2 |
| `artifacts/fusion-msclap/fusion.json` | `run_fusion.py` | Section 4 (+5.2pp claim) |
| `artifacts/human-signal-alignment/alignment.json` | `human_signal_alignment.py` | Section 3.4 |
| `research/data/fsld/chroma.jsonl` | `extract_fsld_features.py` | harmonic signal |
| `research/data/fsld/role_prompts.json` | `extract_fsld_features.py` | role_gap signal |
