# ISMIR 2026 LBD Submission Checklist

Deadline: 2026-08-09

## Format
- [x] 2 pages scientific content + 1 page references only
- [x] Uses official ismir.sty with `[lbd,submission]` options
- [x] Single author, not anonymized (LBD requirement)
- [x] All fonts embedded (tectonic handles this)
- [x] No page numbers in header (ismir.sty handles this)

## Content integrity
- [x] Number consistency check passes (84/84, `check_paper_numbers.py`)
  - Artifact-vs-hardcoded checks + tex-presence checks + tex-absence checks
  - Limitations: substring presence, not semantic context; manual review still required
- [x] All table numbers match artifact JSONs (LAION + MS-CLAP sections)
- [x] All prose statistics match artifact JSONs
- [x] MS-CLAP `cosine+harmonic` row footnoted (role-gap untested in this space)
- [x] Claim-evidence ledger reviewed and synced 2026-08-08
  - C1a/C1b/C1d/C1e verified; removed claims documented
- [ ] C2/C3 real-account capture (partial — offline tests done, screencast pending)
- [x] C1d explicitly labeled "post-hoc exploratory (NOT preregistered)"
- [x] Role-gap 2/9 clarified: fired on 2, matched both, tied on 7
- [x] All 5 signals reported in alignment (no selective omission)
- [x] Domain-shift caveat added (corpus + pair-construction differences)
- [x] Source-grouped splits explained (prevent pack leakage)
- [x] Invalid bootstrap CI error bars removed from Figure 2(a)
- [x] Figure 1 marks role/chroma as offline (grey italic annotation)
- [x] Role/chroma signals described as offline-only in Sections 2.1 and 2.2
- [x] Bootstrap CI and sign test p=0.031 removed from text (pseudoreplication)
- [x] "linear-probe" corrected to "zero-shot"

## AI Usage Statement
- [x] Present in manuscript — scope: engineering, scripting, collation, drafting
- [x] All research claims, design, analysis verified by author

## Build pipeline
- [x] `build.sh` produces PDF from clean /tmp directory
- [x] iCloud-resilient (falls back to ~/dev/ismir-backup/)
- [ ] build.sh does not assert PDF page count (manual verification)

## Artifacts
- [x] `artifacts/fusion/fusion.json` — 5-signal LAION-CLAP
- [x] `artifacts/fusion-7sig/fusion.json` — 7-signal LAION-CLAP
- [x] `artifacts/fusion-msclap/fusion.json` — MS-CLAP replication
- [x] `artifacts/human-signal-alignment/alignment.json` — signal-human alignment
- [x] `artifacts/eval-pack/eval_summary.json` — 9-rater vote data

## Before submission (8/9)
- [x] Full text proofread
- [ ] Compile final PDF with `build.sh` (number check enabled)
- [ ] Upload to ISMIR submission system
