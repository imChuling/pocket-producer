# Changelog

Pocket Producer 开发过程中的关键决策和转折点。
详细的冲刺计划和审计文档见 `docs/_archive/`。

## 2026-08-09 — 7-signal LOSO ablation + 提交前收尾

- 新实验: `research/run_ablation_7sig.py` → `artifacts/ablation-7sig/ablation.json`
  - 7 信号 leave-one-signal-out, 与 fusion-7sig 完全同配置 (同 seeds/splits/trainer)
  - tempo 贡献 +3.0pp (hard_similar); harmonic −0.15pp; role_gap −0.25pp
  - harmonic 在弱标签上贡献为零现在是实测结论, 不再是占位/推断
- Figure 2(b) 左侧全部改用同一 LOSO 实验的 delta, harmonic 恢复真实左侧位置
- 信号级数字全文统一为 LOSO 值 (+2.6pp → +3.0pp)
- Figure 2 caption 与正文 "no inferential claim" 措辞同步
- matplotlib 输出 Type 42 字体, PDF 中 Type 3 清零
- checker 空白正规化 (换行不再引起假失败); 99/99 通过

## 2026-08-08 — 第二轮审稿修订 (Weak Reject → targeting Borderline Accept)

第一轮 (Reject → Weak Reject):
- Bootstrap CI 和 sign test p=0.031 全部移除
- "linear-probe" → "zero-shot"
- 人类评估降级为 "exploratory post-hoc pilot"
- 系统 claims 诚实化; 引用更新至 15 篇

第二轮 (Weak Reject → targeting Borderline Accept):
- Table 1 补 MS-CLAP 部分: 3 行 (cosine-mean 0.864, cosine+session 0.863, fusion 0.877)
- role/chroma 信号明确标注 "implemented and evaluated offline; live-session integration pending"
- role-gap 分母澄清: "fired on 2 of 9, matched both, tied on 7" (非 22% 准确率)
- Figure 2 caption 说明 role-gap 因稀疏触发未绘制
- domain-shift caveat: 两评估制度的 corpus/pair-construction 差异不能归因于 label semantics
- "5 random splits" → "5 source-grouped splits", 说明 pack-based grouping 防 leakage
- Figure 2 字体放大 (~35%)
- check_paper_numbers.py 重写: 双层验证 (artifact 一致 + tex 存在/不存在)
  - 84/84 通过; 包含已删除统计的 NOT-in-tex 检查
- claim-evidence-ledger.md 同步: sign test/CI 移入 "Removed claims" 节

## 2026-08-07 — ISMIR LBD 论文冻结

- 论文 PDF 冻结于 `docs/ismir2026/lbd.pdf`
- 51/51 数字验证通过 (`research/check_paper_numbers.py`)
- 15 篇参考文献全部 URL 验证
- Fleiss' kappa = 0.294 从原始投票数据独立复现
- 措辞从"结论性"降级为"exploratory/preliminary"
  - "signal ranking reversal" → "opposite ranking tendencies"
  - bootstrap CI 置于 sign test 之前
  - 5-seed sign test (p=0.031) 保留但不作为主要证据

## 2026-08-06 — MS-CLAP 部署骨架复现

- fusion gain 在部署用 MS-CLAP 1024-dim 骨架上复现 (+5.2pp hard_similar, 5/5 seeds)
- 7-signal fusion (加 role_gap + harmonic) 与 5-signal 不可区分 → 论文只报告 5-signal
- ablation-librosa 实验: librosa DSP 特征替代 CQT chroma, 无改善

## 2026-08-04 — 9-rater 人类评估完成

- 9 位外部评审者 × 20 对盲测 = 180 labels
- 关键发现: tempo 在 weak labels 上最强 (+2.6pp) 但在人类共识上最弱 (3/9)
- harmonic compatibility 在 weak labels 上无贡献但在人类共识上最强 (7/9)
- 这个分歧成为论文核心论点: weak labels ≠ continuation utility

## 2026-08-02 — ISMIR 最终冲刺启动

- 制定冲刺计划 (`docs/_archive/superpowers/plans/2026-08-02-ismir-final-sprint.md`)
- 三条工作流: 审查修复 / MIR 元素 / 论文撰写
- 确定不做: 节拍对齐插入 (MIR-3)、Vercel 部署修复

## 2026-08-01 — 证据审计 + 架构升级

- ladder-serving differential review: 发现 learned adapter 空结果 fallback 缺失
- 修复: `LadderRankerAdapter` 加入 rules-v1 fallback
- 五受众定位研究 (MIT, Stanford, ISMIR, Let's Build, 工业界)
- 确定 Audiotool OAuth client ID 配置问题 → 解决

## 2026-07-31 — 骨架对比 + 弱标签评估

- LAION-CLAP (512-dim) vs MS-CLAP (1024-dim) 在 2,558 FSLD items 上对比
- LAION-CLAP 更优但 MS-CLAP 许可证审计完整 → 部署用 MS-CLAP
- 1,755 leave-one-out 弱标签对构建完成
- frozen CLAP cosine (0.883) 击败两个 learned reranker (DeepSets 0.735, PocketRank 0.742)
  → 关键转折: learned model 不优于 frozen embedding, 论文方向从"新模型"转向"信号分析"

## 2026-07-30 — 研究协议冻结

- 预注册协议 v1 冻结 (`research/protocol.md`)
- 主要假设: session-conditioned ranking 优于最强简单基线
- 失败标准明确: 若 PocketRank 不优于基线, 降级为系统+协议贡献

## 2026-07-25 — 双轨冲刺规划

- 确定双轨: ISMIR LBD (8/9) + Let's Build (8/22)
- 共享研究主干 (Tasks 1-13) + 两条投稿支线
- PocketRank 证据审计: claim-evidence ledger 建立
- 前沿架构文档: SessionGraph, capacity ladder, 表示空间设计

## 2026-06-11 — Hackathon 提交

- Pocket Producer 首次作为 Audiotool Let's Build hackathon 作品提交
- 核心功能: session fingerprint → fragment retrieval → reversible insertion
- 评审期间 repo 和部署冻结
