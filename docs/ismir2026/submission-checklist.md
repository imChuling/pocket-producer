# ISMIR 2026 LBD Submission Checklist

Deadline: 2026-09-25 AoE (rolling review)

## Format
- [x] 2 pages scientific content + 1 optional page (references; CfLBD
  explicitly permits acknowledgements and AI usage statement on it —
  verified against the call 2026-08-18)
- [x] Uses official ismir.sty with `[lbd,submission]` options
- [x] No global style overrides: titlesec removed 2026-08-18; only
  local float-adjacent `\vspace` tweaks remain
- [x] Single author, not anonymized (LBD requirement)
- [x] All fonts embedded (tectonic handles this)
- [x] No page numbers in header (ismir.sty handles this)

## Content integrity
- [x] Number consistency check passes (155/155, `check_paper_numbers.py`)
  - Artifact-vs-hardcoded checks + tex-presence checks + tex-absence checks
  - Limitations: substring presence, not semantic context; manual review still required
- [x] Checker self-audit 2026-08-19 (round 9): swept for assertions whose
  *computation* does not match the *claim's subject* — the class of bug
  that let "13–17 pp" pass. Three found and fixed, each mutation-tested
  to confirm it now fails when the claim is removed:
  1. `min(fusion_vs_rules, cosine_vs_rules)` admitted cosine's 13.4 pp
     into a claim about the learned fusion (see rules-gap entry below)
  2. `has_2.1pp` matched the bare string "2.1", which the held-out
     "+2.1" also satisfies — the dev-set −2.1 pp claim could have been
     deleted without failing; now anchored on "by 2.1\,pp" plus
     "negative in all 5 splits"
  3. `bootstrap_ci_per_seed` was read with `.get(..., {})` behind an
     `if`, so the "negative in all 5 splits" check silently vanished if
     the key went missing; now a hard `check` on the key's presence
  - Also tightened `msclap_htk` tolerance from 0.1 to 0.05 (tol=0.1 on a
    1-decimal value had accepted −0.2 and 0.0 as well)
  - Verified NOT a bug: Table 1's MS-CLAP hard_tempo_key −0.1 is the
    bootstrap point estimate (−0.1487), not the rounded seed-mean
    difference (−0.15); the printed value is correct
  - Missing artifacts already fail loudly via `load_json` (MISS), so the
    remaining `if artifact:` gates do not hide assertions
- [x] All prose statistics match artifact JSONs (independently spot-checked
  across audit rounds, 2026-08-18/19)
- [x] Held-out numbers are the corrected protocol values (+2.1 LAION /
  +9.9 MS-CLAP sw-BPR, 7.8 pp swing), labeled exploratory in paper
- [x] Held-out LOSO replication reported for BOTH axes in §4: tempo
  replicates, key does not (−0.12 pp hard_similar, sign unstable);
  key's dev-set result marked descriptive (no CIs, per ledger F2)
- [x] Rules default rationale rewritten (2026-08-19): no longer claims
  "no stable fusion advantage" (contradicted Table 1 MS-CLAP CIs);
  now discloses rules trails the learned fusion 16–17 pp on held-out proxy
- [x] Rules-gap range corrected 2026-08-19 (round 9): was "13–17 pp",
  but 13.4 pp is the *cosine*-vs-rules gap under MS-CLAP, while the
  sentence's subject is the learned fusion (LAION 17.0, MS-CLAP 16.0).
  The checker had encoded the same error via `min(fusion_vs_rules,
  cosine_vs_rules)`; both assertions now bound fusion_vs_rules alone,
  plus a `check_not_in_tex` guard against the stale "13--17" string
- [x] Prototype claims hedged per ledger rule (S2/S3 partial):
  abstract "evaluated offline", contribution (3)
  "offline-evaluated" (softened from "validated" 2026-08-19 to
  avoid reading as user/task validation); §2.2 keeps "validated
  offline against the official Nexus document validator"
  (literal engineering validation)
- [x] Page boundary verified 2026-08-20: conclusion ends on page 2;
  page 3 contains only acknowledgements + references, no floats
- [x] Both figures restored 2026-08-20 (author request): Figure 1
  (system architecture, 0.85\columnwidth) and Figure 2 (two-panel
  configuration-sensitivity analysis, 0.77\columnwidth) are back in
  the body alongside Table 1
- [x] Page-budget compression pass 2026-08-20 (author's plan, A/B/C
  information tiers): compressed §2.3 deployment (i)–(v) list to
  prose, §3.1 training details (dropped 171/981 query counts,
  300 epochs/no-early-stopping, ~75% split detail — now in
  research/README only), protocol-mismatch disclosure to one
  sentence, rules-baseline rationale to one sentence, both captions;
  deduplicated intro question hook (abstract keeps it), §3.1 tag-
  context sentence (§2.3 has it), two §3.2 clauses restating §3.1's
  negative-tier definitions, and the §3.2 key-zeroing disclaimer
  (§2.3 states the metadata reason); dropped the inline BPR loss
  formula (standard, cited). Checker updated in step (152/152):
  deployment/rules/bootstrap needles re-anchored, 171/981/75%
  tex-presence assertions replaced by a no_981_in_body absence guard
- [x] Micro-polish pass 2026-08-20 (reviewer feedback, round 11):
  (1) "measures a curator's co-membership" → "captures
  curator-defined pack co-membership"; (2) "rulesranker" confirmed a
  PDF text-extraction artifact only — source reads
  `\emph{rules} ranker`, pdfminer extracts the space correctly;
  (3) four absolute dev accuracies (0.9293/0.8136/0.9249/0.8133)
  compressed to the delta "+4.0 → −0.03 pp" per reviewer suggestion.
  Checker updated (151/151): absolute-accuracy tex-presence needles
  replaced by absence guards + a "+4.0 \to -0.03" arrow needle;
  artifact-level checks on the four accuracies retained.
  Verified post-build: Conclusion complete on page 2, page 3 =
  acknowledgements + references only
- [x] Uncited bib entries removed 2026-08-19 (yi2024drum2bass,
  roychaudhuri2026loopmatcher); 12 entries remain, all cited
- [x] Citation audit completed 2026-08-19 (web-verified): all 12
  entries exist, metadata matches (incl. five 2024–2026 entries);
  two claim-fit fixes applied in intro ("stem coherence and
  retrieval"; "DAW-integrated and context-conditioned generation"
  so he2025tomi/nistal2024diffariff each carry an accurate label)
- [ ] C2/C3 real-account capture (partial — offline tests done, screencast pending)
- [x] Source-grouped splits explained (prevent pack leakage)
- [x] Eight audit rounds completed (five-lens, read-only, through
  2026-08-19); round-7 blockers fixed and re-verified against artifacts
- [x] Restructured 2026-08-19 (author's plan): §2 Pocket Producer
  (2.1 Fingerprinting and Ranking merged, 2.2 Proposal Workflow,
  2.3 Deployment) → §3 Cold-Start Proxy Evaluation (3.1
  Weak-Supervision Setup = method only; 3.2 Three-Axis Sensitivity
  Analysis = all results, mirrors contribution (2) verbatim) →
  §4 Conclusion (restored as standalone section)
- [x] Structural mirroring: contribution (2) "sensitivity analysis
  across three axes" ↔ §3.2 title "Three-Axis Sensitivity
  Analysis"; axis names = bold paragraph heads (Label construction
  / Negative regime / Representation/training configuration),
  singular, identical in contribution (2), §3.2, and conclusion

## Provenance integrity
- [x] Corrected held-out artifacts carry provenance manifests
  (`artifacts/heldout-eval-correction/provenance.json`,
  `artifacts/msclap-sensitivity-correction/provenance.json`): artifact SHA,
  split SHA, n_bootstrap=10000, alpha=0.05, source-level resampling,
  seeds, correction reason, exploratory status
- [x] sw-BPR modifications pre-specified in frozen
  `research/protocol-msclap-sensitivity-v1.md`
- [x] Superseded artifacts preserved for audit trail
  (`artifacts/heldout-eval-packonly/`, `artifacts/heldout-eval/`)
- [x] "≥3 items" query eligibility stated in lbd.tex
- [x] Deployed weights match source-weighted BPR recipe described in §2.4
- [x] 7.8 pp swing framed as cross-configuration sensitivity, not fusion superiority

## AI Usage Statement
- [x] In-paper AI Usage Statement removed by author decision 2026-08-18
  (CfLBD lists it as optional on the extra page)
- [ ] Declare via submission form if the platform requires it — verify at upload
- [x] All research claims, design, analysis verified by author

## Build pipeline
- [x] `build.sh` produces PDF from clean /tmp directory (copies .tex/.pdf/.png assets)
- [x] iCloud-resilient (falls back to ~/dev/ismir-backup/)
- [x] PDF page count: 3 pages (2 scientific + 1 optional), verified 2026-08-18
- [x] CI runs the 151-assertion checker (`.github/workflows/paper-check.yml`)

## Artifacts (paper-facing, see research/README.md for inventory)
- [x] `artifacts/heldout-split-packonly/split.json` — frozen split (605 = 484/121, seed 20260810)
- [x] `artifacts/fusion-packonly/fusion.json` — §3 dev-set accuracies
- [x] `artifacts/fusion-7sig/fusion.json` — §4 label sensitivity (+4.0 pp, mixed labels)
- [x] `artifacts/ablation-packonly/ablation.json` — §4 LOSO (dev set)
- [x] `artifacts/heldout-eval-correction/sensitivity.json` — Table 1 LAION column
- [x] `artifacts/msclap-sensitivity-correction/sensitivity.json` — Table 1 MS-CLAP column + held-out LOSO
- [x] `artifacts/fusion-deploy/weights.json` — §2.4 deployed weights

## Before submission
- [x] Full text proofread (two audit rounds, 2026-08-18)
- [x] Compile final PDF with `build.sh` (number check enabled)
- [x] Demo video / demo page: author decided NOT to submit (2026-08-18);
  the "demonstration video accompanies this submission" sentence was
  removed from the conclusion accordingly
- [ ] Clean-clone verification: one command builds PDF + 151/151 + tests
- [ ] Upload to ISMIR submission system (title, abstract, PDF, subject area)
