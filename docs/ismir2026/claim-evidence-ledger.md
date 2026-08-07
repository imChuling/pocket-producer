# ISMIR 2026 LBD — Claim–Evidence Ledger

规则:正文只能写 `status=verified` 的主张;`pending` 主张只能用未来时态;
提交前逐条核对 `evidence_path` 与 `commit_sha`。

| Claim ID | Manuscript claim | Required evidence | Status |
|---|---|---|---|
| C1a | Multi-signal fusion (5 params) beats frozen cosine on hard\_similar negatives (+4.0pp, one-sided sign test p=0.031, 5/5 seeds) | `artifacts/fusion/fusion.json` + `artifacts/baselines-laion/baselines.json` | verified 2026-08-06 |
| C1b | Session-structure signals (role\_gap, harmonic) show no gain on pack-membership weak labels | `artifacts/fusion-7sig/fusion.json` | verified 2026-08-06 (negative result, reported as such) |
| C1c | Session context improves ranking on human continuation preferences | pairwise labels per participant — insufficient power at current sample size | pending — only future-tense statements allowed |
| C1d | Post-hoc exploratory (NOT preregistered, 5 signals compared, all 5 reported): consensus-pair alignment harmonic 7/9, cosine 6/9, cos\_max 4/9, tempo 3/9, role\_gap 3/3 on fired pairs; no single difference significant at n=9; direction consistent with weak-label/human reversal | `artifacts/human-signal-alignment/alignment.json` + `research/human_signal_alignment.py` | verified 2026-08-07 |
| C2 | System operates in a real DAW (reads live Audiotool document) | real-account 15s continuous capture + offline fixture tests (`frontend/src/lib/audiotool/session-fingerprint.test.ts`) | partial — offline tests done @ acf4b7a; real-account capture pending |
| C3 | Insertion is reversible: undo restores exact prior entity set | offline Nexus document tests with official WASM validator (`frontend/src/lib/audiotool/insert-fragment.test.ts`) + real-account capture | partial — offline tests done @ 5f7889c; real-account capture pending |
| C4 | Representations are versioned with model id, revision, input hash | representation schema tests (`backend/tests/ranking/test_representations.py`) | pending |
| C5 | Evaluation protocol preregistered before result inspection | `research/protocol.md` frozen 2026-07-30 @ 6f96032 | verified |
| C6 | Explainable baseline produces structured evidence, not generated prose | `backend/ranking/baselines.py` + tests @ 43e7c92 | verified |
| C7 | Rules fallback keeps the loop working without any model service | registry fallback tests @ ad8e9d8 + failure-drill capture | partial — tests done; drill capture pending |

## 禁用措辞(除非获得直接证据)

`state-of-the-art` / `improves creativity` / `understands intent` /
`first composition-aware recommender` / population-level significance claims.

## AI usage log(按 ISMIR 2026 AI Usage Policy)

| Date | Tool | Scope |
|---|---|---|
| 2026-07-30/31 | Claude Code | 工程实现、测试编写、文档起草;所有研究主张、引用与图表由作者核验并负责 |
| 2026-08-01/06 | Claude Code | baseline/fusion/7-signal 实验脚本、结果整理、论文修订;实验设计与所有结论由作者核验并负责 |
