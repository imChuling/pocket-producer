# ISMIR 2026 LBD — Claim–Evidence Ledger

规则:正文只能写 `status=verified` 的主张;`pending` 主张只能用未来时态;
提交前逐条核对 `evidence_path` 与 `commit_sha`。

Claim IDs map to paper sections: F = §3 Fusion, E = §4 Evidence lines, S = System, P = Protocol.

| Claim ID | Manuscript claim (§) | Required evidence | Status |
|---|---|---|---|
| F1 | Pack-only corpus: 1,797 items, 605 packs; 484 train sources (171 with ≥3 items form queries → 981 examples); 121 held-out sources (54 form queries → 323 examples); split seed 20260810 committed before evaluation (§3) | `artifacts/heldout-split-packonly/split.json` + `artifacts/heldout-eval-packonly/eval.json`, freeze commit `43e1643`; denominators verified vs items file | verified 2026-08-10 (denominators corrected per review) |
| F2 | Train side (5 source-grouped splits): frozen cosine 0.929 overall / 0.814 hard\_similar; fusion 0.925 / 0.813 (−0.03pp); fusion trails cosine on hard\_tempo\_key by 2.1pp on average, negative in all 5 splits — DESCRIPTIVE only, no significance claim (the earlier pair-level endpoint-averaged dev CI was invalid and is retracted; `run_ablation.py` now does per-seed source-grouped CIs with no cross-seed pooling) (§3) | `artifacts/fusion-packonly/fusion.json` + `artifacts/ablation-packonly/ablation.json` (`bootstrap_ci_per_seed`) | verified 2026-08-10 |
| E1 | Label sensitivity: on the earlier mixed-label corpus (26% uploader-grouped examples, 949 sources), fusion appeared +4.0pp on hard\_similar; pack-only labels erase the gain (§4) | mixed: `artifacts/fusion-7sig/fusion.json`; pack-only: `artifacts/fusion-packonly/fusion.json`; composition count via `research/filter_pack_only.py` | verified 2026-08-09 |
| E2 | LOSO (pack-only train): tempo −0.96pp hard\_similar / +0.68pp hard\_tempo\_key; key +0.94 / +1.21 (removing helps); regime construction partly builds this in (§4, LOSO table removed in restructure — tempo numbers in prose, key numbers in artifact only) | `artifacts/ablation-packonly/ablation.json` | verified 2026-08-09 |
| E3 | Held-out LAION-CLAP (corrective run, full train): hard\_similar +2.1pp, 95% CI [−1.0, +5.3] crosses zero; hard\_tempo\_key +0.0pp, CI [−0.8, +0.5] crosses zero; overall +0.6pp, CI [−0.4, +1.6] crosses zero. Previous 75%-train results (E3-old): +1.5/−1.0/+0.4. Source-grouped bootstrap (10k draws, joint resampling) (§4) | `artifacts/heldout-eval-correction/sensitivity.json` (protocol-heldout-correction-v1); old: `artifacts/heldout-eval-packonly/` | corrective run 2026-08-13 |
| E3b | MS-CLAP sensitivity (corrective run, full train, sw-BPR hs×2.0): hard\_similar +9.9pp, CI [+4.4, +15.4] above zero; hard\_tempo\_key −0.1pp, CI [−2.2, +2.0] crosses zero; overall +2.6pp, CI [+1.0, +4.2] above zero. Previous 75%-train results: +9.2/−1.8/+2.0. Cross-configuration swing: 7.8pp (9.9−2.1). LOSO (full-train): tempo −7.6/+1.0pp (direction holds); key −0.1pp on hard\_similar (near zero). Factorial (dev-set, unchanged): +1.9pp repr / +0.5pp training / +0.3pp interaction (§4) | `artifacts/msclap-sensitivity-correction/sensitivity.json` (protocol-heldout-correction-v1); old: `artifacts/msclap-sensitivity/`; factorial: `artifacts/factorial/factorial.json` | corrective run 2026-08-13 |
| E4 | Residual limitation: signal set/hyperparameters designed on earlier mixed-label corpus; pack-only corpus is a subset of previously inspected data; LAION-CLAP run is sensitivity re-analysis, not de novo confirmation; MS-CLAP sensitivity changed both embedding and training recipe; dev-set factorial decomposes gap shifts (+1.9pp repr / +0.5pp training / +0.3pp interaction); paper now says "cross-configuration swing" not "representation sensitivity". **Protocol mismatch (2026-08-13):** MS-CLAP protocol-v1 line 52 says "Retrain fusion on full train side" but both `run_heldout_eval.py` and `run_msclap_sensitivity.py` use `val_fraction=0.25` internal split (no early stopping or model selection on the held-out 25%); paper now discloses "source-grouped 75% subset" and downgrades "pre-committed" to "fixed" throughout (§3,§4) | stated in paper and in `research/protocol-heldout-v2.md` + `research/protocol-msclap-sensitivity-v1.md` + `artifacts/factorial/factorial.json` | acknowledged |
| E5 | Pilot: 9 raters, 20 blind A/B pairs, Fleiss' κ=0.294; 1 pair excluded ("neither" majority); harmonic matches majority 7/9, tempo 3/9 | `artifacts/human-signal-alignment/alignment.json` | REMOVED from paper 2026-08-13 — raw 9×20 vote matrix unavailable, κ not independently recomputable; artifact retained in repo but not cited in the 2-page body. Space reallocated to full held-out delta table (Table 1) |
| S1 | Deployed ranker (fusion-5sig-v1) follows the SAME RECIPE but is a SEPARATE PRODUCTION MODEL — paper states four deltas: MS-CLAP space (offline: LAION-CLAP), source-weighted BPR weights on all pack-only train examples (hard\_similar×2.0, mean over 5 seeds; offline eval trains per-seed on ~75% internal subsets), key constant zero online, session-tag context. Zero-contribution signals emit no evidence (key never shown as a reason online). **Gate C (2026-08-10): default ranker is rules-v1; fusion selectable but not default** — held-out showed no stable fusion advantage. Undoing an insert also retracts its tags from the ranking context (§2) | `backend/ranking/fusion_ranker.py` + `backend/tests/ranking/test_fusion_ranker.py` (10 pass) + `artifacts/fusion-deploy/weights.json` + default logic in `continuation-panel.tsx`, tag retraction in `audiotool/page.tsx` | verified 2026-08-10 |
| S2 | System reads live Audiotool session via Nexus SDK (§2, Fig 1) | offline fixture tests (`frontend/src/lib/audiotool/session-fingerprint.test.ts`) | partial — offline tests done; real-account capture pending |
| S3 | Insertion is reversible via single Nexus transaction with undo (§2) | offline Nexus document tests (`frontend/src/lib/audiotool/insert-fragment.test.ts`) | partial — offline tests done; real-account capture pending |
| P1 | v2 protocol + split committed before the confirmatory run | `research/protocol-heldout-v2.md` + split at commit `43e1643`; eval artifacts created after | verified 2026-08-09 — freeze provable in git history |
| P2 | v1 preregistration claim | — | RETRACTED — v1 protocol was never committed before evaluation (claimed base commit `3726d0a9` predates the file); file mtime postdates eval.json. All v1 held-out numbers demoted to exploratory and removed from paper |

## Artifact integrity: SHA-256 + commit timeline (Gate A, 2026-08-10)

冻结顺序在 git 历史中可验证：协议+split 先提交(`43e1643` 18:36),
评估产物后提交(`ad0e767` 18:55),held-out 产物此后从未修改。

| Artifact | SHA-256 (16) | First commit | Last modified |
|---|---|---|---|
| heldout-split-packonly/split.json | `94f5f2d34d7af17f` | `43e1643` 08-09 18:36 (freeze) | unchanged |
| heldout-eval-packonly/eval.json | `14e2d80c01f0b09a` | `ad0e767` 08-09 18:55 | unchanged — single confirmatory run |
| heldout-eval-packonly/bootstrap.json | `501a653f651e9254` | `ad0e767` 08-09 18:55 | unchanged |
| heldout-eval-packonly/loso.json | `d854620fee80575c` | `ad0e767` 08-09 18:55 | unchanged |
| heldout-eval-packonly/weights.json | `48bd09d3f1cfce9f` | `ad0e767` 08-09 18:55 | unchanged |
| fusion-packonly/fusion.json | `8b554ec645244431` | `ad0e767` 08-09 18:55 (dev set) | unchanged |
| ablation-packonly/ablation.json | `76b5cc8ea06a8c7e` | `ad0e767` 08-09 18:55 | `122eda8` 08-09 23:43 — dev-set CI methodology fix only (pair-level → source-grouped per-seed); ablation means unchanged; NOT a held-out artifact |
| fusion-deploy/weights.json | `b400fd618c5d0def` | `ad0e767` 08-09 18:55 | 08-10 — re-exported with source-weighted BPR (hard\_similar×2.0) |
| msclap-sensitivity/sensitivity.json | `8f3b837928f4e431` | new 08-10 | new — MS-CLAP sensitivity re-analysis |
| factorial/factorial.json | `843dad79c9fcd54e` | new 08-10 | new — 2×2 factorial (representation × training) |

v1 遗留(`artifacts/heldout-eval/`)保留原样作为撤回记录;其 bootstrap.json
曾于 08-09 用修正后的合并方法重算(per-seed 段与原值一致,pooled 段更宽)。

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
| 2026-08-10 | Claude Code | MS-CLAP sensitivity re-analysis: source-weighted BPR 训练+三基线评测、部署权重重导出、论文双空间对比更新、number checker 扩展(151 checks)、claim-evidence ledger 同步;2×2 factorial 实验脚本+运行(representation×training, dev-set 5-fold CV)、confound caveat 替换为 factorial 分解(+1.9/+0.5/+0.3pp)、checker 扩展至 161 checks;代码库清理(死代码/废弃 artifacts/研究数据 ~8.8GB);论文重构为系统导向叙事(§2 扩展至 4 小节、§4 压缩为无子节段落、LOSO 表删除)、checker 更新至 97 checks;最终审查: 双 agent 代码-论文一致性+严谨性审计、§2 三处表述与代码对齐(rules 信号枚举/evidence chips/日志范围)、abstract "only supervision" 弱化、pilot 排除说明补回、致谢移至第 2 页、bib 清理(98 checks);所有实验设计与结论由作者核验并负责 |
