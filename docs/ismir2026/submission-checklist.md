# ISMIR 2026 LBD Submission Checklist

Deadline: 2026-08-09

## Format
- [x] 2 pages scientific content + 1 page references only
- [x] Uses official ismir.sty with `[lbd,submission]` options
- [x] Single author, not anonymized (LBD requirement)
- [x] All fonts embedded (tectonic handles this)
- [x] No page numbers in header (ismir.sty handles this)

## Content integrity
- [x] Number consistency check passes (34/34, `check_paper_numbers.py`)
- [x] All table numbers match artifact JSONs
- [x] All prose statistics match artifact JSONs
- [x] Claim-evidence ledger reviewed — C1a/C1b/C1d/C1e verified, C4 verified
- [ ] C2/C3 real-account capture (partial — offline tests done, screencast pending)
- [x] C1d explicitly labeled "post-hoc exploratory (NOT preregistered)"
- [x] C1e explicitly labels role_gap as "UNTESTED" not "null"
- [x] Hard_similar selection effect self-disclosed
- [x] All 5 signals reported in alignment (no selective omission)
- [x] Tempo 3/9 included (initially omitted, added back)

## AI Usage Statement
- [x] Present in manuscript (ISMIR 2026 policy requires it)
- [ ] User decision pending on scope of disclosure

## Build pipeline
- [x] `build.sh` produces PDF from clean /tmp directory
- [x] iCloud-resilient (falls back to ~/dev/ismir-backup/)
- [x] System figure auto-regenerated if corrupt

## Artifacts
- [x] `artifacts/fusion/fusion.json` — 5-signal LAION-CLAP
- [x] `artifacts/fusion-7sig/fusion.json` — 7-signal LAION-CLAP
- [x] `artifacts/fusion-msclap/fusion.json` — MS-CLAP replication
- [x] `artifacts/human-signal-alignment/alignment.json` — signal-human alignment
- [x] `research/protocol-v2.md` — preregistered replication protocol (frozen)
- [x] `research/recruitment-plan.md` — Prolific recruitment logistics

## Tests
- [x] test_features.py — tempo, key, track_gap, intent, novelty, recency
- [x] test_harmonic.py — transpose invariance, session chroma, shift labels
- [x] test_role_probe.py — classify, session_roles, gap_score
- [x] test_fusion.py — BPR convergence, weight direction, complementary signals

## Backup
- [x] ~/dev/ismir-backup/ contains all content files outside iCloud
- [x] git bundle ~/dev/pocket-producer.bundle (799KB, verified @ 7ae5f94)

## Before submission (8/9)
- [x] Full text proofread (no issues found)
- [ ] Compile final PDF with `build.sh` (number check enabled)
- [ ] Upload to ISMIR submission system
