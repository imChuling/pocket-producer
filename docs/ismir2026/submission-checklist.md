# ISMIR 2026 LBD Submission Checklist

Deadline: 2026-09-25 AoE (rolling review; internal freeze 2026-08-11)

## Format
- [x] 2 pages scientific content + 1 page references only
- [x] Uses official ismir.sty with `[lbd,submission]` options
- [x] Single author, not anonymized (LBD requirement)
- [x] All fonts embedded (tectonic handles this)
- [x] No page numbers in header (ismir.sty handles this)

## Content integrity
- [x] Number consistency check passes (97/97, `check_paper_numbers.py`)
  - Artifact-vs-hardcoded checks + tex-presence checks + tex-absence checks
  - Limitations: substring presence, not semantic context; manual review still required
- [x] All prose statistics match artifact JSONs
- [x] Claim-evidence ledger reviewed and synced 2026-08-10
- [ ] C2/C3 real-account capture (partial — offline tests done, screencast pending)
- [x] Paper restructured: system-heavy (§2 with 4 subsections), compressed §4 (no LOSO table, no subsections)
- [x] Source-grouped splits explained (prevent pack leakage)

## Provenance integrity
- [x] Held-out eval artifact points to protocol-heldout-v2 (pack-only, 484/121)
- [x] run_heldout_eval.py derives protocol ref from --protocol arg (no hardcoded v1)
- [x] Numerical payload SHA unchanged across metadata migration
- [x] v1 artifacts (759/190) preserved in `artifacts/heldout-eval/` for audit trail
- [x] "≥3 items" query eligibility stated in lbd.tex
- [x] MS-CLAP sensitivity numbers match sensitivity.json (headline +9.2pp and CI)
- [x] Deployed weights match source-weighted BPR recipe described in §2.4
- [x] 7.7pp swing framed as representation sensitivity, not as fusion superiority

## AI Usage Statement
- [x] Present in manuscript — scope: engineering, scripting, collation, drafting
- [x] All research claims, design, analysis verified by author

## Build pipeline
- [x] `build.sh` produces PDF from clean /tmp directory
- [x] iCloud-resilient (falls back to ~/dev/ismir-backup/)
- [x] PDF page count: 3 pages (2 scientific + 1 references), verified 2026-08-10

## Artifacts
- [x] `artifacts/fusion-packonly/fusion.json` — 5-signal LAION-CLAP (pack-only)
- [x] `artifacts/fusion-7sig/fusion.json` — 7-signal LAION-CLAP (mixed labels, for §4 label sensitivity)
- [x] `artifacts/human-signal-alignment/alignment.json` — signal-human alignment
- [x] `artifacts/heldout-eval-packonly/eval.json` — pack-only held-out (protocol-v2)
- [x] `artifacts/heldout-split-packonly/split.json` — pack-only split (484/121)
- [x] `artifacts/msclap-sensitivity/sensitivity.json` — MS-CLAP sensitivity re-analysis
- [x] `artifacts/fusion-deploy/weights.json` — deployed weights (source-weighted BPR)
- [x] `artifacts/ablation-packonly/ablation.json` — LOSO ablation (pack-only dev set)
- [x] `artifacts/factorial/factorial.json` — 2×2 factorial (kept as supporting artifact, not in paper)

## Before submission
- [x] Full text proofread
- [x] Compile final PDF with `build.sh` (number check enabled)
- [ ] Real Audiotool E2E demo recording (≥5 projects)
- [ ] Upload to ISMIR submission system
