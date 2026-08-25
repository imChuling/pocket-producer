# Key-Axis Audit Protocol v1

Status: **FROZEN at the commit that introduces this file.**

## Purpose

The key signal does not replicate under held-out LOSO (−0.12 pp
hard_similar, sign unstable across seeds); the paper reports its dev-set
result as descriptive only. Two pre-registered hypotheses:

- **H-label**: FSL10K annotation keys are noisy enough to wash out the
  signal.
- **H-match**: exact string matching is too brittle (relative
  major/minor and fifth-related keys are musically compatible but score
  zero).

Either a fix or a documented cause is an acceptable outcome; all results
are reported regardless of direction.

## Step A — Label quality audit (no model training)

- Sample: up to 100 items from the pack-only corpus, stratified by
  annotation key class (up to 5 per pitch-class/mode cell, filled
  round-robin with a fixed seed 20260825 until 100 or the corpus is
  exhausted).
- Audio estimate: CQT chroma via the existing
  `backend/ranking/harmonic_probe.chroma_from_audio`, scored against
  Krumhansl-Schmuckler major/minor profiles over all 24 rotations;
  argmax is the estimated key.
- Report (artifacts/key-audit/key_audit.json): exact agreement rate,
  agreement-within-{relative major/minor, perfect fifth}, and the full
  confusion structure.
- Decision rule, fixed in advance: exact agreement < 60% supports
  H-label; >= 80% weakens H-label; between the two is inconclusive and
  both Steps B and C still run (they run in every case; the rule only
  fixes the interpretation wording).

## Step B — Tolerant matching (dev only)

`key_match` variants, implemented behind a parameter with the current
behavior as default:

| Variant | Scores 1.0 for | Partial credit |
|---|---|---|
| exact (current) | same tonic + mode | none |
| relative | + relative major/minor | 1.0 |
| fifth | + relative, and 0.5 for tonic a perfect fifth apart (same mode) | 0.5 |

Evaluation: dev-side LOSO (`run_ablation.py`) per variant, 5 seeds
[20260725, 20260801-04]. Selection rule, fixed in advance: the variant
whose key-removal LOSO delta on hard_similar has the largest mean while
keeping a consistent sign across all 5 seeds; ties break toward the
simpler variant (exact > relative > fifth). If no variant achieves a
consistent sign, H-match is unsupported and no held-out run occurs for
Step B.

## Step C — Feature-source swap (dev first, held-out once)

Replace the annotation key with the audio-estimated key (Step A
estimator) as the input to `key_match` (exact variant), for both session
fingerprint and candidates. Dev-side 5-split + LOSO first. A single
held-out LOSO run (`loso_heldout.py`) is permitted only for the one
configuration selected by the Step B/C dev results under the rules
above; output `artifacts/key-audio-est/` with provenance.json.
**No re-runs permitted.**

## Reporting

The outcome statement is one of:
- "key replicates under [variant/source] (held-out LOSO delta, CI)", or
- "key failure attributed to [label noise | matching brittleness |
  neither; unresolved]" with the supporting numbers.

Framing stays descriptive; no causal claims beyond the audit's direct
measurements. The held-out split's reuse count increases by at most one
run under this protocol and must be disclosed wherever results appear.
