# PocketRank Evidence Audit and Revision Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 Pocket Producer 双轨方案中的问题定义、模型选择、数据、架构、指标、部署、投稿和作品集主张逐项建立可追溯证据，并删除无法被当前代码、官方文档、论文或计划内实验支持的内容。

**Architecture:** 采用 claim–evidence ledger。每个主张标记为直接证据、邻域迁移证据、本项目待验证假设或应删除主张；外部论文只能证明方法有先例，不能替代 PocketBench 和真实 Nexus 测量。所有任意数字改成 validation-selected hyperparameter、目标 SLO 或明确的投稿策略。

**Tech Stack:** Local repository audit、official Audiotool/ISMIR/MIT/Stanford/Hugging Face documentation、peer-reviewed/arXiv primary research、Markdown evidence ledger、pytest/Vitest benchmark artifacts。

---

## 1. 证据等级

| 等级 | 含义 | 允许写法 |
|---|---|---|
| A — Direct | 当前代码/测量、官方接口/规则、直接任务论文 | “代码当前使用…”、“官方规则要求…” |
| B — Transfer | 同类推荐、set modeling、HCI 或 learning-to-rank 研究 | “提供方法依据；仍需在 PocketBench 验证” |
| C — Hypothesis | 产品判断、阈值、权重、未在本任务验证的设计 | “我们将检验…”、“内部目标…” |
| R — Reject | 被本地证据反驳、不可测量或超出研究设计 | 从论文、README 和演示口播删除 |

审核规则：

1. 引用只支持它实际研究的任务，不用 tagging SOTA 证明 continuation utility。
2. “官方文档没有找到”只能支持“不依赖该能力”，不能证明 API 永远不存在。
3. 工程阈值必须叫 target、hyperparameter 或 gate，不能伪装成科学事实。
4. 计划中的结果必须用未来时态；只有 artifact 已生成才写成结果。
5. 录取、获奖和创造力提升都不能由本计划保证。

## 2. 总体裁决

### 保留

- live Nexus read/write、preview/insert/undo；
- session-conditioned continuation retrieval 任务；
- versioned audio/text representations；
- candidate generation 与 reranking 分离；
- PocketBench backbone bake-off；
- rules/linear/DeepSets/attention 容量梯子；
- explicit pairwise preference 为初期主要监督；
- model/data card、失败降级和 claim-evidence ledger。

### 修改

- 不同 backbone 从“向量直接相加”改为独立检索后 RRF late fusion；
- ANN Top-50 改为 exact/ANN 与 `Recall@K–latency` 曲线选择；
- 400K Transformer 从“推荐答案”降为模型梯子中的 L2 challenger；
- implicit event 从固定强弱标签改为原始时间事件；
- EMA decay、MMR 权重、K 和 latency 都改为实测/validation 选择；
- nDCG、MRR、ECE 只在标签语义满足前提时报告；
- 3–5 位参与者只允许 formative/descriptive 结论。

### 删除或禁止

- “现有 embedding 是 audio embedding”；
- “本地 secret 文件已被 Git 跟踪”；
- “最新/SOTA encoder 必然最适合推荐”；
- “50 个事件后模型就能可靠个性化”；
- “8 秒 preview、60 秒保留天然对应标签强度”；
- “提升创造力”、“理解你的音乐意图”、“保证获奖/录取”。

## 3. 逐项证据账本

### A. 外部时间与投稿

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| A1 | ISMIR LBD 滚动录取 | [ISMIR 2026 official call](https://ismir2026.ismir.net/call-for-late-breaking-demo) 明列 2026-07-31 开放、2026-09-25 AoE 截止、最多 75 项、滚动审查、拒稿不可重投、2026-10-16 camera-ready | A | 保留；每次提交前重新打开官方页截图/存档 |
| A2 | 8 月 9 日提交 | 官方没有要求 8 月 9 日；这是为滚动容量和双轨开发设置的内部日期 | C | 写成 target，不写成官方 deadline；真实 Nexus、格式与引用 gate 未过时可推迟，但不得晚于内部 8 月 11 日而不重新决策 |
| A3 | Let’s Build 8 月 23 日截止 | [official page](https://www.audiotool.com/LetsBuild/) 当前显示 “Open now until 23 August 2026” | A | 8 月 22 日为内部 deadline，8 月 23 日只作恢复 |
| A4 | 一项作品可跨类别获奖 | Let’s Build 官方页说明评委为项目匹配类别，单个项目可符合多个类别 | A | 可以提及跨类别资格；未拿到完整 judging rubric 前不声称具体评分权重 |

### B. 问题定义与研究价值

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| B1 | composition-aware compatibility 是真实 MIR 问题 | [Neural Loop Combiner](https://archives.ismir.net/ismir2020/paper/000225.pdf)、[SampleMatch](https://arxiv.org/abs/2208.01141)、[Drum2Bass](https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/97751/drum2bass_SMC2024_camera_ready.pdf?isAllowed=y&sequence=2) 均研究 context/loop compatibility | A | 保留；不得声称首创 composition-aware retrieval |
| B2 | “相似”不等于“适合下一步” | 上述研究使用 compatibility/context，而非只做 generic similarity；Neural Loop Combiner 还比较 rule/Siamese/CNN | A | 可作为研究动机；本项目仍需人类 continuation labels |
| B3 | “帮助音乐人重新进入未完成作品”是已证明需求 | 当前没有访谈、日志或引用直接证明目标用户把它列为主要痛点 | C | 在首轮 3–5 位访谈中验证；若多数参与者不认可，叙事改为 fragment reuse/continuation support |
| B4 | 三个候选是最佳数量 | 当前只有 demo 清晰度和 UI 空间判断，没有任务研究证明 | C | pilot 比较 Top-3 与 Top-5 的决策时间和满意度；八月可把 Top-3 当产品约束，不当科学发现 |
| B5 | 系统提升创造力 | 短期排序实验无法识别 creativity change；human-AI co-creativity 研究强调 control、trust、ownership 等多维结果 | R | 禁止作为主结果；评估 relevance、control、flow interruption 和 time-to-insert |

### C. 当前代码与数据事实

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| C1 | 当前 embedding 是文本表示 | `backend/tools/embedding.py:20-40` 调用 Voyage `voyage-3`，输入为 text，注释写明 1024-d；`frontend/src/types/index.ts:7-35` 只有单一 `embedding` 字段 | A | 必须迁移为 `representations.text`; 不允许称为 audio embedding |
| C2 | 当前已有音频结构特征 | `backend/tools/audio_features.py:38-136` 计算 tempo、chroma key、mode、RMS、onset、spectral features | A | 可复用为 baseline；key/mode 为 heuristic，需 confidence 与缺失值 |
| C3 | 当前已有向量检索经验 | `backend/jobs/resurrect.py:45-60` 使用 MongoDB `$vectorSearch`、user filter、numCandidates 和 limit | A | 复用基础设施；它只证明文本向量检索代码存在，不证明音频召回质量 |
| C4 | 当前已有 PocketRank/Nexus | `backend/pyproject.toml` 没有 torch/CLAP；`frontend/package.json` 没有 `@audiotool/nexus`；仓库没有 ranking/session-graph 文件 | A | 这些仍是待实现，不得在 LBD 中写成已完成 |
| C5 | 本地 secrets 已被 Git 跟踪 | 2026-07-25：`.gitignore` 命中两文件；`git ls-files`、路径历史与 object scan 无结果 | R | 更正为“本地存在但未发现进入 Git”；发布前仍需 secret/archive/container scan |
| C6 | 当前 agent pipeline 可直接删除 | `backend/pyproject.toml:8-12` 仍依赖 Google ADK/GCP；现有产品其他路径可能使用 | C | 比赛关键路径可以独立于 Gemini；是否物理删除依赖必须先跑现有测试和 dependency usage audit |

### D. Audiotool/Nexus 集成

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| D1 | Nexus 能 read/write live project | [Developer Dashboard](https://developer.audiotool.com/) 和 [Nexus overview](https://developer.audiotool.com/js-package-documentation/documents/Overview.html) 明确 project read/write、实时 document modification；v0.0.17 quick start 要求 `project:write` | A | 保留；必须用真实账号和录屏证明，不以 mock 代替 |
| D2 | project 可表示为 entities | Nexus overview 将 document 的基本单元定义为 typed entities | A | `SessionGraph` 从 entity canonicalization 构造合理 |
| D3 | Nexus 提供可靠 project mixdown | 已审查公开文档只找到 entities 和 Samples API，没有找到可依赖的 mixdown contract | C/R | v1 不依赖 mixdown；不能写“API 绝对没有”，只写“未验证，故不依赖” |
| D4 | SessionGraph 必然包含 audio embedding | synth/note/automation entity 未必有可读 audio sample | C | modality mask 是必需；用 entity-only fixture 验证完整 fallback |
| D5 | Nexus API latency 可忽略 | 官方 overview 给出 central Europe 到 US-Central 约 150–300 ms 的示例，并说明不是 playhead-synchronous | A/C | 不能把 Nexus 当 sample-accurate transport；真实地区/网络重新测量 |

### E. Foundation model 选择

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| E1 | 应直接采用外部 MIR SOTA | [Tamm & Aljanaki 2026](https://arxiv.org/abs/2604.23077) 比较九种表示，发现传统 MIR 与 hot/cold recommendation 表现存在明显差异 | R | 外部 SOTA 只决定进入 bake-off，不决定上线 |
| E2 | MuQ 是强 research challenger | [paper](https://arxiv.org/abs/2501.01108) 与 [official repo](https://github.com/tencent-ailab/MuQ) 报告 MIR 结果；repo 明列约 300M/700M、24 kHz、fp32/NaN 提示、开放版数据差异、权重 CC BY-NC | A | research-only；不进入商业默认和同步路径 |
| E3 | M2D-CLAP 值得比较 | [official repo](https://github.com/nttcslab/m2d) 推荐 2025 checkpoint，示例 frame feature 3840-d；license 要求阅读 `LICENSE.pdf` | A | 许可审计完成前 research-only |
| E4 | MERT-95M 是部署默认 | [model card](https://huggingface.co/m-a-p/MERT-v1-95M) 为 CC BY-NC 且 audio-only | R | 只作 compact research baseline |
| E5 | MusicFM-FMA 有音乐结构价值 | [official repo](https://github.com/minzwon/musicfm) 提供 frame/sequence representations 和 FMA checkpoint | A/B | 进入首轮 music-only bake-off；不能仅凭设计目标宣称本任务更好 |
| E6 | MS-CLAP 适合首轮实现 | [Microsoft CLAP repo](https://github.com/microsoft/CLAP) 有 MIT code、2022/2023 weights、audio/text similarity API | A/B | 是可执行候选，不是 license-approved product；分别审查 code、weights、training data |
| E7 | LAION-CLAP Music 可无风险上线 | [official repo](https://github.com/LAION-AI/CLAP) 提供 music checkpoints，但明确因版权不能发布训练数据 | R | 保留为 challenger；Data Card 显式记录 provenance uncertainty |
| E8 | ALM2Vec/TinyMU/SLAP 应进入八月主线 | [ALM2Vec](https://arxiv.org/abs/2606.30682) 是 instruction-aware general audio retrieval；[TinyMU](https://arxiv.org/abs/2604.15849) 是 229M music QA/reasoning；[SLAP](https://ismir2025program.ismir.net/poster_47.html) 是 audio-text representation | C/R | 作为 related work/watchlist；无公开 artifact/许可/任务 benchmark 时不阻塞主线 |

### F. 检索与融合架构

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| F1 | candidate generation + ranking 分层合理 | [YouTube recommendation paper](https://research.google.com/pubs/archive/45530.pdf) 明确两阶段架构；直接 loop research 也区分 candidate/context scoring | B | 保留作为系统分解；个人库规模小不代表必须使用 ANN |
| F2 | 必须 ANN Top-50 | 当前没有 library-size、Recall@K 或 latency 数据 | C | benchmark exact/Mongo ANN；用 validation `Recall@K–latency` 选择 K 和实现 |
| F3 | CLAP、MusicFM、MuQ 向量可加权相加 | 它们由不同目标训练，维度/几何空间不共享；只有 CLAP 自身 audio/text tower 在联合空间中可比较 | R | 每个空间单独检索，再用 [RRF](https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/) 融合 ranked lists |
| F4 | RRF 一定优于 learned score fusion | RRF 论文证明其在所测 IR fusion 中有效，不证明 Pocket Producer 最优 | B/C | 将 RRF 作为低数据 baseline；有足够 validation queries 后再比较 calibrated score fusion |
| F5 | metadata hard filter 可安全使用 | user/deleted/license/format 是权限和有效性约束；tempo/key/role 是有噪音乐特征 | A/C | 前者 hard filter；后者 soft feature，避免 false-negative recall |

### G. SessionGraph 与模型容量

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| G1 | set encoder 适合 entity context | [Set Transformer](https://proceedings.mlr.press/v97/lee19d.html) 为集合元素交互与 permutation invariance 提供依据；Nexus document 由 entities 构成 | B | 模型必须通过 entity-order permutation test |
| G2 | 时间信息与集合不冲突 | region token 显式携带 start/duration/playhead distance；set order 无意义，但字段有意义 | B/C | shuffle entities 输出不变；改变时间字段应改变输出 |
| G3 | 两层 Transformer 优于 mean pooling | 没有本任务证据；小数据容易过拟合 | C | 容量梯子 L0 linear、L1 DeepSets、L2 attention；选择最简单且 held-out 不劣的模型 |
| G4 | 400,897 参数数目成立 | 对 `input_dim=1024,d=128,ff=256,two layers` 和共享投影的独立公式核算为 400,897；未含 frozen encoder | A | 实现后由 `sum(p.numel())` 单元测试替代纸面计算 |
| G5 | 少于 500K 是科学阈值 | 它是部署/叙事约束，没有论文证明 500K 是最佳分界 | C | 称为 engineering budget；同时报告实际参数、CPU latency 和性能曲线 |
| G6 | structured features 有效 | tempo/key/role/duration 与 loop compatibility 直觉和相关研究一致；当前 key estimator 有噪 | B/C | 每项做 ablation；key 使用 confidence，不做 hard truth |
| G7 | 32 tokens、128/16-d 子空间、rank 16、dropout 0.1 是合理固定值 | 它们是初始工程配置，没有 task-specific 证据 | C | 进入 graph coverage、容量、seed stability 和 latency ablation；test 解封前锁定 |
| G8 | role/missing-role 可由系统直接知道 | 某些 Nexus entity type 提供设备/轨道结构，但 role 可能来自 user tag 或 classifier | C | 保存 `role_source/confidence`；低置信回到 `unknown`，解释不得把推断当事实 |

### H. 数据、loss 与反馈

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| H1 | same-song/leave-one-out weak positives 合理 | Neural Loop Combiner 与 SampleMatch 都从 composition/context 构造 positive | A/B | 可预训练；必须按 source song/pack/uploader split，不能作为 human test truth |
| H2 | FSLD 全部可自由用于训练/发布 | [Freesound API](https://freesound.org/docs/api/resources_apiv2.html) 返回 CC0、CC BY、CC BY-NC 等逐条 license；许可不同 | R | manifest 保存每条 license；公开/商业 artifact 使用允许子集 |
| H3 | BPR 适合 pairwise preference | [BPR](https://arxiv.org/abs/1205.2618) 为 implicit personalized ranking 提供 pairwise objective | B | explicit pair 也可用 logistic/BPR；必须与 simpler logistic baseline 比较 |
| H4 | InfoNCE 能解决 continuation | contrastive objective 与直接 compatibility 研究提供方法依据，但 weak labels 可能学习 source artifacts | B/C | source-held-out、hard negatives、human test 和 no-pretrain ablation |
| H5 | preview/insert/undo 是有效反馈 | 行为与兴趣相关是合理观测；[unbiased LTR](https://arxiv.org/abs/1608.04468) 证明位置/曝光会使 implicit feedback 偏置 | B | 记录 exposure、rank、raw duration；初投不直接宣称因果偏好 |
| H6 | 8 秒 preview、60 秒 retained 是标签真值 | 无本任务证据 | R | 删除固定标签；pilot 后预注册敏感性分析 |
| H7 | interleaving 可减少比较所需流量 | [Generalized Team Draft Interleaving](https://eprints.gla.ac.uk/108076/) 将其定义为混合结果、以交互比较 ranker，并关注小流量敏感度 | B | 仅在 study mode、知情同意和安全 slate 内使用；小样本只作 formative |
| H8 | EMA history 是可靠个性化 | 没有本任务直接证据 | C | no-history/mean/EMA ablation；decay validation-selected |
| H9 | 50 个事件是 user adapter 门槛 | 无统计功效或 learning-curve 依据 | R | 由 temporal learning curve、可形成的 train/validation split 和稳定收益决定 |
| H10 | 2–4 region context 与三类 hard negatives 是最佳构造 | 相关 loop work 支持 same-composition 与 hard-negative 思路，但不支持这些具体数量/类别最优 | C | 在 weak validation 上比较 context size/negative mix，并在 human test 上检查 shortcut |

### I. Slate、解释与人类控制

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| I1 | MMR 可平衡相关性与冗余 | [MMR original paper](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf) 直接提出 relevance/novelty trade-off | B | 作为 baseline；lambda 由 validation/pilot 选择 |
| I2 | ILD 代表人类感知的音乐多样性 | [Jesse et al.](https://link.springer.com/article/10.1007/s11257-022-09351-w) 指出具体 ILS 实现与人类感知的关系依领域而异；[ISMIR user insights](https://archives.ismir.net/ismir2020/paper/000311.pdf) 讨论音乐多样性感知 | R/B | ILD 只作 proxy，同时收集 perceived diversity 与 role coverage |
| I3 | Best fit / Useful contrast / From your memory 是正确 taxonomy | 没有用户研究 | C | pilot 询问标签是否可理解、是否与听感相符；不当作 learned explanation |
| I4 | grounded reason codes 等于模型可解释 | reason codes 可避免 LLM hallucination，但 neural score 仍非完全可解释 | C | 分开显示 eligibility、ranking evidence、uncertainty；做 feature perturbation/faithfulness test |
| I5 | preview/insert/undo 有助于 agency | [2025 co-creativity review](https://arxiv.org/abs/2506.21333) 将 user control 与 satisfaction/trust/ownership 联系；[music co-creation evaluation](https://arxiv.org/abs/2504.14071) 报告 controllability/predictability 是实际限制 | B | 评估 perceived control；不从功能存在直接推断 agency 已提升 |

### J. 指标与研究设计

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| J1 | Stage A 用 Recall@K | candidate generation 的职责是覆盖 relevant candidates | B | 报告完整 Recall@K curve；K 在 validation 选择后锁定 |
| J2 | pairwise labels 可直接计算 nDCG@3 | nDCG 需要每个 query 下可排序的 graded relevance；单个 pair 只给局部偏好 | R | pairwise 主指标为 accuracy/log loss/wins；另收 0–3 grades 才用 nDCG |
| J3 | MRR 总是适用 | MRR 假设可定义第一个 relevant item；纯 preference pair 没有该语义 | C/R | 只在 leave-one-out 或明确 relevant candidate task 使用 |
| J4 | ECE 适合小型 pilot | binned ECE 对样本量/binning 敏感；[SmoothECE](https://arxiv.org/abs/2309.12236) 专门讨论传统 ECE 缺陷 | C | 小样本用 Brier/log loss和 reliability plot；足够 N 后再报告预注册 calibration measure |
| J5 | bootstrap CI 能弥补 3–5 位 participant | resampling 不能创造更多独立参与者，cluster 数太少时总体推断脆弱 | R | 报 participant-level raw results、descriptive interval、effect direction；明确 formative |
| J6 | participant/project/source split 必要 | 同一人、同一曲、变速/移调 duplicate 跨 split 会造成身份/来源泄漏 | A/B | manifest 记录 participant、source、audio hash family；测试 split intersection 为空 |
| J7 | 6–8 位用户足以证明普遍提升 | 无 power analysis；用户异质性高 | R | 只支持 formative usability/feasibility；正式论文前做 effect-size-informed power/design |
| J8 | model win 是 LBD 必需 | ISMIR LBD screening 关注 suitability、originality、format；不要求 learned model 必赢 | A | 模型未过 gate时主张降为 task/system/benchmark/preliminary study |
| J9 | PocketBench P1/P2 能证明 continuation | P1/P2 只测 generic audio/text retrieval；2026 recommender study显示传统任务表现不能替代推荐任务表现 | R | P1/P2 只诊断 representation；最终选择以 P3 session retrieval 与 P4 human preference 为准 |

### K. Serving、隐私和可靠性

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| K1 | foundation encoder 应离线缓存 | 模型规模、MuQ fp32/24 kHz、M2D 3840-d 与 live interaction latency共同支持；属于工程推断 | B | hash-idempotent worker；cached path 不调用 foundation model |
| K2 | Hugging Face 可作为唯一同步后端 | [Spaces hardware](https://huggingface.co/docs/hub/spaces-gpus) 与 [Endpoint autoscaling](https://huggingface.co/docs/inference-endpoints/en/guides/autoscaling) 说明休眠/scale-to-zero/cold start | R | 只作异步 worker/研究 demo；本地 rules 与 cached ranker 保底 |
| K3 | p95 100/500 ms 已经能达到 | 当前没有实现和目标硬件 benchmark | C | 标成 SLO target；cold/warm/cache-miss 三种环境测量 |
| K4 | ONNX 一定支持该模型 | ONNX Runtime 是合理目标，但 attention、mask 和 opset 仍需导出测试 | C | PyTorch/ONNX 数值一致性与 target CPU benchmark 过门后才采用 |
| K5 | secrets 当前安全 | Git 审计未发现跟踪，但不能证明未通过日志、云端、压缩包或屏幕共享暴露 | C | secret scanner、Docker context、deployment env、submission archive 四项检查 |

### L. 获奖与申请价值

| ID | 方案内容 | 证据 | 等级 | 结论与验收 |
|---|---|---|---|---|
| L1 | 本项目保证 Let’s Build 获奖 | 评审是竞争性判断，完整 rubric 未被当前公开页面展开 | R | 只能优化可理解 demo、Nexus 原生性、稳定性、原创任务和完成度 |
| L2 | “MIT CCRMA”是一个项目 | CCRMA 属于 Stanford；MIT 另有 Music Technology and Computation/Media Lab | R | 申请叙事分成 MIT MTC/Media Lab 与 Stanford MA/MST 两套，不混称 |
| L3 | Pocket Producer 对 MIT MTC 有相关性 | [MIT MTC official program](https://musictech.mit.edu/mtcgp/) 列出 MIR、AI/ML、interaction、audio DSP、creative-expression software；[MIT OGE](https://oge.mit.edu/programs/music-technology-and-computation/) 的 MASc 要求 portfolio of two projects | A/B | Pocket Producer 可作为其中一个项目；还需音乐经历、coding test、statement、推荐信等，项目不能替代整份申请 |
| L4 | Pocket Producer 对 Stanford CCRMA/MST 有相关性 | [Stanford MA/MST](https://music.stanford.edu/academics/graduate-studies/graduate-programs/ma-music-science-and-technology) 明列 music perception、signal processing、HCI、synthesis、inter-media；[graduate admissions](https://music.stanford.edu/admissions/prospective-graduate-students/graduate-admissions) 要求 statement/recommendations/transcripts，并对 MA 要求 scholarly writing sample | A/B | LBD/technical report、实验日志和系统演示构成契合证据；不能预测录取 |
| L5 | 一个华丽 Demo 足够申请 | MIT 与 Stanford 官方要求还包括研究/目标陈述、音乐与技术准备、推荐信、写作材料等 | R | 作品集必须同时有 runnable system、research question、evidence、个人贡献、失败分析和音乐实践 |

## 4. 经证据修正后的最小架构

```text
Nexus documented entities/samples
  → deterministic SessionGraph with modality masks

Versioned representations
  ├── CLAP joint space retrieval
  ├── selected music-only space retrieval
  └── rules/metadata retrieval
        ↓
  RRF late fusion
        ↓
  candidate K selected from Recall@K–latency curve
        ↓
  capacity ladder
  L0 linear/rules → L1 DeepSets → L2 attention
        ↓
  task-appropriate evaluation
  pairwise labels → accuracy/log loss
  graded labels   → nDCG@3
        ↓
  validation-tuned MMR slate
        ↓
  preview / insert / undo
        ↓
  raw exposure/action log, not invented labels
```

这套架构不承诺 Transformer、ANN 或任何 backbone 获胜。它承诺每个复杂组件都有较简单对照，并且只有赢过对照后才进入主叙事。

## 5. 投稿允许写的主张

### 当前即可写

```text
We formulate session-conditioned continuation retrieval from personal
creative fragments and design a Nexus-integrated reversible workflow.
```

前提：措辞是“提出/设计”，不是“已经验证改善”。

### 实现真实 Nexus read/write 后可写

```text
The prototype reads a live Audiotool document and inserts a selected
fragment through a reversible user-controlled action.
```

证据：固定 commit、真实录屏、transaction log、undo test。

### PocketBench 生成后可写

```text
We benchmark frozen representations under source-separated splits and
report retrieval quality, latency, numerical stability and licensing.
```

证据：dataset hash、split manifest、benchmark JSON、model/data cards。

### 模型过 gate 后才可写

```text
The context model improved [metric] over [strongest baseline] on
[locked split], with participant/source-level uncertainty reported.
```

必须填入真实模型、指标、样本数和区间；禁止使用计划值。

## 6. 实施任务

### Task 1: 锁定 evidence ledger

**Files:**

- Create: `docs/research/claim-evidence-ledger.md`
- Modify: `docs/ismir2026/claim-evidence-ledger.md`
- Test: `research/tests/test_claim_evidence_ledger.py`

- [ ] 为每个论文/README 主张登记 `claim_id`、`status`、`evidence_path`、`dataset_hash`、`commit_sha`、`allowed_wording`。
- [ ] 测试拒绝 `status=pending` 但正文使用过去时结果动词的主张。
- [ ] 运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/pytest \
  research/tests/test_claim_evidence_ledger.py -q
```

Expected: pending claim fixture FAIL；补齐状态规则后 PASS。

- [ ] Commit:

```bash
git add docs/research/claim-evidence-ledger.md \
  docs/ismir2026/claim-evidence-ledger.md \
  research/tests/test_claim_evidence_ledger.py
git commit -m "research: enforce claim evidence status"
```

### Task 2: 修复表示融合与 K 选择

**Files:**

- Create: `backend/ranking/fusion.py`
- Create: `backend/tests/ranking/test_fusion.py`
- Create: `research/select_candidate_k.py`
- Create: `research/tests/test_select_candidate_k.py`

- [ ] 写 RRF 测试：分数尺度改变不改变融合结果；重复 candidate 只出现一次；hard-filter item 永不返回。
- [ ] 写 K 选择测试：只读取 validation split，输出完整 Recall@K–latency curve，禁止读取 test labels。
- [ ] exact 与 Mongo vector search 使用同一 manifest 比较。
- [ ] 运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/pytest \
  backend/tests/ranking/test_fusion.py \
  research/tests/test_select_candidate_k.py -q
```

Expected: 所有测试 PASS，输出选定 K 及选择理由。

- [ ] Commit:

```bash
git add backend/ranking/fusion.py backend/tests/ranking/test_fusion.py \
  research/select_candidate_k.py research/tests/test_select_candidate_k.py
git commit -m "research: select retrieval fusion and candidate depth"
```

### Task 3: 建立模型容量梯子

**Files:**

- Create: `backend/ranking/linear_ranker.py`
- Create: `backend/ranking/deepsets_ranker.py`
- Create: `backend/ranking/context_model.py`
- Create: `backend/tests/ranking/test_model_ladder.py`
- Create: `research/compare_model_capacity.py`

- [ ] 同一 split、features、seed 比较 L0/L1/L2。
- [ ] 测试 entity permutation invariance、padding mask、parameter count、CPU inference。
- [ ] 选择最简单且 validation performance 不劣于最佳模型预注册 tolerance 的模型；tolerance 在看 test 前写入 protocol。
- [ ] 运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/pytest \
  backend/tests/ranking/test_model_ladder.py -q
python research/compare_model_capacity.py \
  --manifest research/data/pocketbench-v1.jsonl \
  --out artifacts/model-capacity.json \
  --seed 20260725
```

Expected: artifact 含实际参数、validation metric、CPU latency 和选择结果。

- [ ] Commit:

```bash
git add backend/ranking backend/tests/ranking \
  research/compare_model_capacity.py
git commit -m "research: compare context ranker capacity"
```

### Task 4: 让标签与指标严格匹配

**Files:**

- Modify: `research/annotation-schema.md`
- Create: `research/metrics.py`
- Create: `research/tests/test_metric_eligibility.py`

- [ ] pairwise schema 输出 accuracy/log loss；0–3 grade schema 才输出 nDCG；single-positive schema 才输出 MRR。
- [ ] 测试错误组合直接失败并说明缺少何种标签。
- [ ] implicit events 保存 raw timestamps/durations，不在 ingestion 时生成 strong positive/negative。
- [ ] 运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/pytest \
  research/tests/test_metric_eligibility.py -q
```

Expected: 三种合法 schema PASS，pairwise→nDCG fixture FAIL。

- [ ] Commit:

```bash
git add research/annotation-schema.md research/metrics.py \
  research/tests/test_metric_eligibility.py
git commit -m "research: enforce label compatible metrics"
```

### Task 5: 投稿与作品集事实检查

**Files:**

- Modify: `docs/ismir2026/submission-checklist.md`
- Modify: `docs/letsbuild/judging-evidence.md`
- Modify: `README.md`

- [ ] 每次提交当天重新核对 ISMIR 与 Let’s Build 官方页面。
- [ ] README 禁止 `SOTA`、`improves creativity`、`understands intent`、`guarantees`，除非 ledger 有直接证据。
- [ ] 分开写 MIT MTC/Media Lab 与 Stanford CCRMA/MST 契合点；不使用“MIT CCRMA”。
- [ ] 用以下扫描作为发布 gate：

```bash
rg -n "SOTA|improves creativity|understands.*intent|guarantee|MIT CCRMA" \
  README.md docs/ismir2026 docs/letsbuild
```

Expected: 无未经 evidence ledger 允许的匹配。

- [ ] Commit:

```bash
git add docs/ismir2026/submission-checklist.md \
  docs/letsbuild/judging-evidence.md README.md
git commit -m "docs: align claims with submission evidence"
```

## 7. 最终审计结论

当前最有根据的方案不是“用最新模型做一个更复杂 Demo”，而是：

1. 用官方 Nexus 能力建立真实、可撤销的创作闭环；
2. 用直接相关 loop-compatibility 研究定义任务和弱监督；
3. 用 2026 推荐研究证明必须做 task-specific backbone bake-off；
4. 用两阶段检索、set modeling、BPR、RRF 和 MMR 作为可检验的方法先例；
5. 把所有具体 K、权重、时长、模型容量和 latency 标记为待验证工程选择；
6. 用 label-compatible metrics 和小样本边界保护 ISMIR 可信度；
7. 将项目定位为 MIT 音乐技术与 Stanford CCRMA/MST 都能理解的 research-through-building 作品，但不预测录取。
