# ISMIR 2026 LBD — Claim–Evidence Ledger

规则:正文只能写 `status=verified` 的主张;`pending` 主张只能用未来时态;
提交前逐条核对 `evidence_path` 与 `commit_sha`。

Claim IDs map to paper sections: F = §3 Fusion, E = §4 Evidence lines, S = System, P = Protocol.

| Claim ID | Manuscript claim (§) | Required evidence | Status |
|---|---|---|---|
| F1 | Pack-only corpus: 1,797 items, 605 packs; 484 train sources (171 with ≥3 items form queries → 981 examples); 121 held-out sources (54 form queries → 323 examples); split seed 20260810 committed before evaluation (§3) | `artifacts/heldout-split-packonly/split.json` + `artifacts/heldout-eval-packonly/eval.json`, freeze commit `43e1643`; denominators verified vs items file | verified 2026-08-10 (denominators corrected per review) |
| F2 | Train side (5 source-grouped splits): frozen cosine 0.929 overall / 0.814 hard\_similar; fusion 0.925 / 0.813 (−0.03pp); fusion trails cosine on hard\_tempo\_key by 2.1pp on average, negative in all 5 splits — DESCRIPTIVE only, no significance claim (the earlier pair-level endpoint-averaged dev CI was invalid and is retracted; `run_ablation.py` now does per-seed source-grouped CIs with no cross-seed pooling) (§3) | `artifacts/fusion-packonly/fusion.json` + `artifacts/ablation-packonly/ablation.json` (`bootstrap_ci_per_seed`) | verified 2026-08-10 |
| E1 | Label sensitivity: on the earlier mixed-label corpus (26% uploader-grouped examples, 949 sources), fusion appeared +4.0pp on hard\_similar; pack-only labels erase the gain (§4.1) | mixed: `artifacts/fusion-7sig/fusion.json`; pack-only: `artifacts/fusion-packonly/fusion.json`; composition count via `research/filter_pack_only.py` | verified 2026-08-09 |
| E2 | LOSO (pack-only train): tempo −0.96pp hard\_similar / +0.68pp hard\_tempo\_key; key +0.94 / +1.21 (removing helps); regime construction partly builds this in, stated in paper (§4.2, Table 1) | `artifacts/ablation-packonly/ablation.json` | verified 2026-08-09 |
| E3 | Held-out (single run, frozen split): hard\_similar +1.5pp, 95% CI [−1.5, +4.7] crosses zero → pre-registered wording "small and uncertain"; hard\_tempo\_key −1.0pp, CI entirely below zero; overall +0.4pp, CI crosses zero. Joint source resampling of the 54 example-bearing source clusters, shared across seeds (§4.3) | `artifacts/heldout-eval-packonly/eval.json` + `artifacts/heldout-eval-packonly/bootstrap.json` | verified 2026-08-09; cluster denominator clarified 2026-08-10 |
| E4 | Residual limitation: signal set/hyperparameters designed on earlier mixed-label corpus; pack-only corpus is a subset of previously inspected data; run is sensitivity re-analysis, not de novo confirmation (§4.3) | stated in paper and in `research/protocol-heldout-v2.md` | acknowledged |
| E5 | Pilot: 9 raters, 20 blind A/B pairs, Fleiss' κ=0.294; 1 pair excluded ("neither" majority), 9 of the remaining 19 preference pairs at ≥7/9 consensus; harmonic matches majority 7/9, tempo 3/9 — descriptive divergence, post-hoc, different corpus; exclusion rule now stated in paper (§4.4) | `artifacts/human-signal-alignment/alignment.json` (n\_pairs=20, n\_preference=19, n\_consensus=9) | verified 2026-08-10 (exclusion disclosed per review) |
| S1 | Deployed ranker (fusion-5sig-v1) follows the SAME RECIPE but is a SEPARATE PRODUCTION MODEL — paper states four deltas: MS-CLAP space (offline: LAION-CLAP), weights retrained on all pack-only train examples (mean over 5 seeds; offline eval trains per-seed on ~75% internal subsets), key constant zero online, session-tag context. Zero-contribution signals emit no evidence (key never shown as a reason online) (§2) | `backend/ranking/fusion_ranker.py` + `backend/tests/ranking/test_fusion_ranker.py` (10 pass) + `artifacts/fusion-deploy/weights.json` + frontend default in `continuation-panel.tsx` | verified 2026-08-10 ("same model" claim retracted per review; wording corrected to "same recipe, separate production model") |
| S2 | System reads live Audiotool session via Nexus SDK (§2, Fig 1) | offline fixture tests (`frontend/src/lib/audiotool/session-fingerprint.test.ts`) | partial — offline tests done; real-account capture pending |
| S3 | Insertion is reversible via single Nexus transaction with undo (§2) | offline Nexus document tests (`frontend/src/lib/audiotool/insert-fragment.test.ts`) | partial — offline tests done; real-account capture pending |
| P1 | v2 protocol + split committed before the confirmatory run | `research/protocol-heldout-v2.md` + split at commit `43e1643`; eval artifacts created after | verified 2026-08-09 — freeze provable in git history |
| P2 | v1 preregistration claim | — | RETRACTED — v1 protocol was never committed before evaluation (claimed base commit `3726d0a9` predates the file); file mtime postdates eval.json. All v1 held-out numbers demoted to exploratory and removed from paper |

## Removed claims (previously in paper, now deleted)

- **"949 FSLD packs" / "pack-membership weak labels" (v1)**: 344 of 949 sources were `user:<username>` fallback groupings (26% of examples). Corrected to pack-only corpus 2026-08-09
- **v1 held-out numbers (+0.83pp, CI [−2.38,+4.17]; tempo −0.73/+3.38 replication)**: removed — v1 split evaluated without provable freeze; superseded by pack-only v2 run
- **v1 dev numbers (0.883/0.754→0.894/0.794, +4.0pp) as headline**: retained only as the mixed-label condition in §4.1's label-sensitivity comparison
- **v1 pooled bootstrap CI [−0.85,+2.67]**: methodologically invalid (per-seed resampling averaged positionally); fixed to joint resampling
- **Sign test p=0.031**: removed — pseudoreplication across seeds
- **"viable cold-start candidate generator"**: weakened to "operational" — no robust advantage over cosine under clean labels
- **MS-CLAP replication table / backbone bake-off / 7-signal LOSO**: no longer in paper

## 禁用措辞(除非获得直接证据)

`state-of-the-art` / `improves creativity` / `understands intent` /
`first composition-aware recommender` / population-level significance claims /
`preregistered`(对 v1)/ `proper generalization test`.

## AI usage log(按 ISMIR 2026 AI Usage Policy)

| Date | Tool | Scope |
|---|---|---|
| 2026-07-30/31 | Claude Code | 工程实现、测试编写、文档起草;所有研究主张、引用与图表由作者核验并负责 |
| 2026-08-01/06 | Claude Code | baseline/fusion/7-signal 实验脚本、结果整理、论文修订;实验设计与所有结论由作者核验并负责 |
| 2026-08-08 | Claude Code | 外部审稿修订: CI/p-value 删除、zero-shot 更正、MS-CLAP 表格补充、role-gap 分母澄清、domain-shift caveat、source-grouped splits 说明、ledger/checker 同步 |
| 2026-08-09 | Claude Code | 审稿硬伤修复: v1 预注册撤回、bootstrap 合并修正、pack-only 全链路重跑(fusion/LOSO/held-out)、fusion-5sig-v1 线上部署、论文叙事更新;所有实验设计与分析计划由作者核验并负责 |
