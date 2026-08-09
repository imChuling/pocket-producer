# PocketRank Context — Frontier Research and Architecture Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Pocket Producer 从“规则加一个小 MLP 的推荐 Demo”升级为一个可信的 session-conditioned music retrieval system：它用 Audiotool 的真实工程结构表示当前创作状态，用冻结的音乐表示模型产生候选，在 linear、DeepSets 和少于 500K 参数的 attention reranker 中按证据选择最简单可用模型，并通过真实插入/撤销反馈持续评估。

**Architecture:** 系统采用两阶段检索。离线 embedding worker 为 fragment 和 Audiotool sample 生成版本化 audio/text representations；在线阶段从 Nexus document 构造 `SessionGraph`，在各表示空间分别做 exact/ANN retrieval 并用 RRF 融合，再比较 linear、DeepSets 与 `PocketRank-Context-450K` 三档 reranker。大型 foundation model 不在同步请求路径中，Hugging Face 服务故障时只影响新 representation 生成，不影响已缓存项目与 rules fallback。

**Tech Stack:** Audiotool Nexus 0.0.17、FastAPI、MongoDB Atlas Vector Search 或 HNSWlib、PyTorch、MS-CLAP / LAION-CLAP、MusicFM / MuQ research bake-off、safetensors、ONNX Runtime、pytest、Vitest。

**Evidence audit:** 所有主张的证据等级、反证、适用边界和验收方法见 [`2026-07-25-pocketrank-evidence-audit.md`](../superpowers/plans/2026-07-25-pocketrank-evidence-audit.md)。证据账本优先于本文中的早期启发式数字。

---

## 0. External schedule locks

- [ISMIR 2026 LBD official call](https://ismir2026.ismir.net/call-for-late-breaking-demo) 写明：submission portal 于 **2026-07-31** 开放，最终截止 **2026-09-25 AoE**，最多接受 75 项，滚动评审，拒稿不得重投；camera-ready、final video/poster 截止 **2026-10-16 AoE**。
- [Let’s Build official page](https://www.audiotool.com/LetsBuild/) 当前写明开放至 **2026-08-23**。

因此采用：

```text
2026-08-07  LBD manuscript/evidence freeze
2026-08-09  LBD target submission
2026-08-11  LBD internal absolute deadline
2026-08-22  Let's Build internal submission
2026-08-23  recovery only
```

滚动录取意味着不要等到 9 月，但“拒稿不能重投”也意味着不得在真实 Nexus read/write、格式、引用和 limitation gate 未通过时仓促上传。若 learned ranker 尚未过 gate，按系统/任务/benchmark/preliminary evidence 投稿，不伪造模型结果。

## 1. 结论先行

### 推荐方案

```text
PocketRank-Context-450K

Offline / asynchronous:
audio → frozen foundation encoder → versioned multi-window embeddings

Online:
Nexus document
  → typed SessionGraph
  → session query + metadata constraints
  → per-space exact/ANN retrieval + RRF
  → validation-selected candidate K
  → 450K context-aware reranker
  → utility score; optional calibration only with a defined label target
  → diversified Top-3
  → preview / insert / undo
  → propensity-aware feedback log
```

这比原计划中的“小 MLP”更强，因为它：

- 不把整个 session 压成 BPM/key 等几个手工字段；
- 明确建模 track、region、时间位置、role、recent edit 和 user intent；
- 将“召回”和“最终选择”分成两个不同问题；
- 通过 weak pretraining、hard-negative mining 和 pairwise feedback 学习 compatibility；
- 支持完整的 backbone bake-off、ablation、calibration 和 latency evaluation；
- 大模型只做冻结特征提取，真正由我们训练和贡献的是 session representation 与 continuation ranking。

### 不推荐的方案

1. **从头训练音乐 encoder：** 数据、算力和时间都不支持，结果大概率比公开 foundation model 差。
2. **直接把 MuQ-MuLan cosine 当最终系统：** 它约 700M、CC BY-NC 4.0，且外部 zero-shot tagging 成绩不能证明 continuation utility。
3. **让 Gemini/音频 LLM 为每个候选打分：** 延迟、成本、可复现性和 grounded explanation 都不适合比赛与 ISMIR。
4. **只用 BPM/key rules：** 是必要 baseline 和 fallback，但不足以支撑前沿研究贡献。
5. **用 6–8 位用户的数据训练 Transformer from scratch：** 会严重过拟合；用户数据只用于小头适配、校准和真实评估。
6. **依赖 Hugging Face Space 同步冷启动：** 官方文档明确免费 Space 会休眠，scale-to-zero 也可能产生分钟级冷启动。

## 2. 当前系统审计

### 已有可复用资产

- `backend/tools/audio_features.py` 已提取 tempo、粗粒度 key/mode、energy curve、brightness、onset density、rhythm complexity、spectral flatness 和 dynamic range。
- `backend/tools/embedding.py` 已有异步 embedding 接口和 MongoDB vector search 使用经验。
- fragment 已有 audio URL、tags、emotions、themes、style、structure hint、creation time 和 project provenance。
- Audiotool Nexus 可查询全部 document entities、监听实时修改、通过 transaction 写回，并提供 Samples API。
- 现有规则与 Gemini tagging 可作为 metadata source，但不应继续作为排序真值。

### 必须修复的结构性问题

1. 当前 `Fragment.embedding` 是 Voyage `voyage-3` 的 **1024 维文本 embedding**，音频 fragment 也主要由 transcript/tags 生成；它不是 audio embedding。
2. embedding 没有 `model_id`、版本、输入 hash、pooling、sample rate 等血缘信息，无法进行模型对比或安全迁移。
3. `audio_features.py` 的 key 估计是启发式结果，未保存 confidence；不能当作硬约束或 ground truth。
4. 当前没有 session graph、candidate exposure、rank position、propensity 或 undo-window 事件。
5. 当前没有将“检索成功”与“重排成功”分开评估。
6. `backend/.env` 与 `backend/firebase-admin-key.json` 存在于本地，但 2026-07-25 的 `git check-ignore`、`git ls-files`、路径历史和 Git object scan 均未发现它们被提交。发布前仍须运行 secret scan；只有发现曾上传、共享或泄露时才轮换，不能把“本地存在”误报成“已经泄露”。

### 新的数据合同

禁止继续向单一 `embedding` 字段写入不同模型：

以下窗口位置和维度是 schema 示例，不是已验证的最佳配置；实际值必须由 adapter 声明并写入 artifact。

```json
{
  "representations": {
    "text": {
      "model_id": "voyage-3",
      "revision": "api-2026-07",
      "dims": 1024,
      "input_sha256": "..."
    },
    "audio_semantic": {
      "model_id": "msclap-2023",
      "revision": "sha256:...",
      "dims": 1024,
      "sample_rate": "adapter-declared",
      "windows": [0, 0.5, 1],
      "pooling": "mean_l2",
      "input_sha256": "..."
    },
    "audio_music": {
      "model_id": "musicfm-fma",
      "revision": "sha256:...",
      "dims": 1024,
      "sample_rate": 24000,
      "pooling": "multi_window_mean_l2",
      "input_sha256": "..."
    }
  }
}
```

每个 representation 都必须保存：

```text
model id
immutable revision/checksum
weight license
input audio hash
sample rate
window positions
pooling
dimensions
created_at
failure status
```

## 3. 最新模型调研与选择

### 3.1 MuQ / MuQ-MuLan

[MuQ](https://arxiv.org/abs/2501.01108) 使用 Mel-RVQ 自监督目标，在论文的 MIR downstream evaluation 中超过 MERT 和 MusicFM；MuQ-MuLan 在 MagnaTagATune zero-shot tagging 上报告了当时 SOTA。官方仓库提供约 300M 的 MuQ 和约 700M 的 MuQ-MuLan。

官方限制：

- 必须使用 24 kHz 输入；
- 官方建议 MuQ 推理使用 fp32，避免潜在 NaN；
- 开源 MuQ 使用 Million Song Dataset 训练，官方明确提醒其表现可能低于论文中 160K 小时版本；
- 权重为 CC BY-NC 4.0。

**决定：**

```text
用途：research teacher / offline backbone bake-off
比赛同步运行时：否
商业化默认模型：否
ISMIR baseline：是
```

来源：[MuQ paper](https://arxiv.org/abs/2501.01108)、[official repository](https://github.com/tencent-ailab/MuQ)。

### 3.2 M2D-CLAP 2025

[M2D-CLAP 2025](https://arxiv.org/abs/2503.22104) 联合 masked self-supervision 与 audio-text contrastive learning。论文报告 frozen/fine-tuned audio feature、music tasks 与 audio-language tasks 的强结果；官方实现输出 frame-level 和 clip-level representation。

问题：

- 主要 benchmark 不是 composition-aware compatibility；
- 官方仓库 license 显示为自定义/未自动识别，必须人工审阅 `LICENSE.pdf`；
- 官方 portable example 的 frame feature 为 3840 维，直接索引会增加存储与 latency；
- 不是 Hugging Face 标准 inference provider 支持路径。

**决定：**

```text
用途：research bake-off
比赛同步运行时：否
允许进入公开产品：仅在权重许可人工核验后
```

来源：[M2D-CLAP paper](https://arxiv.org/abs/2503.22104)、[official repository](https://github.com/nttcslab/m2d)。

### 3.3 MERT-95M

[MERT-v1-95M](https://huggingface.co/m-a-p/MERT-v1-95M) 参数规模较小、生态成熟、使用量大，适合作为音乐 SSL 基线；但权重是 CC BY-NC 4.0，且没有原生 text tower。

**决定：**

```text
用途：compact music-only research baseline
比赛同步运行时：不作为默认
```

### 3.4 MusicFM

[MusicFM](https://github.com/minzwon/musicfm) 是面向 MIR 的自监督模型，支持 frame-level 和 sequence-level embedding。官方提供使用 Creative Commons FMA 训练的版本，并将它作为避免更大数据集许可复杂性的可复现选择；模型仓库标示 MIT license。

优势：

- 音乐结构、beat、chord、key 和 tagging 都在设计范围内；
- FMA 版本的数据路径比大型 proprietary/copyright-heavy 版本更清楚；
- 可输出时间序列 embedding，而不仅是 clip-level semantic vector。

限制：

- 没有 text tower；
- 官方也指出 foundation embedding 对 key detection 仍有限；
- 运行成本高于小型 structured ranker，仍应离线缓存。

**决定：**

```text
用途：首选 music-structure teacher 候选
同步运行时：否
```

来源：[MusicFM paper](https://arxiv.org/abs/2311.03318)、[official repository](https://github.com/minzwon/musicfm)。

### 3.5 MS-CLAP 2023 与 LAION-CLAP Music

[Microsoft CLAP](https://github.com/microsoft/CLAP) 提供 MIT licensed implementation 与 audio/text embedding；[LAION-CLAP](https://github.com/LAION-AI/CLAP) 提供 music-specific checkpoint，代码仓库为 CC0。2025 PAT 论文列出的参数量约为：

```text
MS-CLAP 2023        ≈159M
LAION-CLAP Music    ≈158M
```

它们比 MuQ-MuLan 小，并且原生支持 audio/text joint embedding。LAION 官方同时说明其大部分训练音频受版权限制，未直接发布处理后的数据。

**决定：**

```text
MS-CLAP 2023：首轮 deployment candidate，仍需 weights/data audit
LAION-CLAP Music：research/deployment challenger，provenance 风险更高
最终选择：必须由 PocketBench 决定，而不是凭外部 benchmark
```

代码许可证不自动解决训练数据、模型权重和未来商业使用中的所有权利问题；`MODEL_CARD.md` 必须分别记录。

### 3.6 2026 前沿结果改变了什么

[Tamm & Aljanaki 2026](https://arxiv.org/abs/2604.23077) 在音乐推荐中比较 MusicFM、MERT、MuQ、MuQ-MuLan 等九种预训练音频表示和 KNN、shallow network、hybrid、BERT4Rec 等五种推荐方法。其核心发现是：模型在传统 MIR task 上强，不代表在 hot/cold-start recommendation 上也强，表示的相对表现存在明显任务差异。

这直接支持本方案最重要的模型决策：

```text
不按 tagging / zero-shot leaderboard 选 backbone
→ 在 PocketBench 的 continuation task 上实测
→ 将 backbone 与 reranker 的贡献分开
→ 保留 handcrafted/rules 强基线
```

[ALM2Vec 2026](https://arxiv.org/abs/2606.30682) 将自然语言 instruction 编入统一音频检索表示，展示了 aspect-conditioned retrieval 的前沿方向；它很适合未来表达“找一个补充低频、但不要改变节奏密度”的可控 query。但当前论文聚焦通用 audio/speech retrieval，论文页未给出可直接审计的代码/权重入口，也没有验证 live composition compatibility，因此只列为 **post-LBD watchlist**，不进入八月关键路径。

[TinyMU 2026](https://arxiv.org/abs/2604.15849) 将 music-language reasoning 缩到 229M，并报告相对大型 LALM 的竞争力；但其训练目标是 music question answering/understanding，不是低延迟候选重排。它说明“小型专用模型”方向成立，却不应被误用为本项目的 ranker。

[SLAP（ISMIR 2025）](https://ismir2025program.ismir.net/poster_47.html) 报告在 text-music retrieval 与 zero-shot classification 上超过 CLAP，并减少 modality gap。它值得后续加入 audio-text backbone bake-off；在公开权重、完整许可和本项目 latency 未核验前，不替换首轮三个可执行 adapter。

### 3.7 模型决策矩阵

| Backbone | Audio/Text | 规模 | 许可/血缘 | Pocket Producer 角色 |
|---|---:|---:|---|---|
| MS-CLAP 2023 | audio + text | ≈159M | MIT repo；需记录 weights/data | 首轮可执行候选 |
| LAION-CLAP Music | audio + text | ≈158M | CC0 repo；训练数据复杂 | challenger |
| MusicFM-FMA | audio | 需实测 | MIT model repo；FMA CC | music teacher |
| MERT-95M | audio | 95M | CC BY-NC 4.0 | compact research baseline |
| MuQ | audio | ≈300M | CC BY-NC 4.0 | research teacher |
| MuQ-MuLan | audio + text | ≈700M | CC BY-NC 4.0 | SOTA-oriented research comparison |
| M2D-CLAP 2025 | audio + text | ViT-base family | custom/需审阅 | research challenger |
| ALM2Vec 2026 | instruction + audio | 需实测 | 未完成 code/weights 审计 | post-LBD watchlist |
| TinyMU 2026 | audio + language | 229M | 未完成 weights/data 审计 | reasoning reference，非 ranker |
| SLAP 2025 | audio + text | 需实测 | 未完成 public artifact 审计 | post-LBD challenger |

**硬规则：** 外部 benchmark 的 SOTA 只决定谁进入 bake-off，不决定谁上线。

## 4. 直接相关研究：我们不能假装这个问题没人做

### Neural Loop Combiner

[Neural Loop Combiner](https://archives.ismir.net/ismir2020/paper/000225.pdf) 从 Free Music Archive 构造同曲 positive loops 和 negative examples，比较 Siamese 与 CNN compatibility model，并用用户研究验证。其 CNN 超过 Siamese 和 rule-based baseline。

对我们的启示：

- negative sampling 是核心研究变量；
- “相似”不等于“兼容”；
- 不能只用随机 negatives；
- 必须包含 human evaluation。

### SampleMatch

[SampleMatch](https://arxiv.org/abs/2208.01141) 将 incomplete song mixture 作为 context，通过 contrastive learning 让来自同一首歌的 drum sample 得到高分，并进行了 listening test。

对我们的启示：

- query 应是当前 composition，而不是用户 profile；
- leave-one-part-out 是可行的 weak supervision；
- 真实音乐上下文比 tags 拼接更有力。

### Drum2Bass

[Drum2Bass](https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/97751/drum2bass_SMC2024_camera_ready.pdf?isAllowed=y&sequence=2) 提出 composition-aware loop recommendation：先生成一个 best-guess bass loop，再将其作为 retrieval anchor，并评估 normalized rank 和 inter-list diversity。

对我们的启示：

- composition-aware retrieval 已形成明确研究脉络；
- diversity 不能在 Top-3 中缺席；
- “生成 anchor 再检索”很有想象力，但对本项目时间和可控性不如 learned session query；
- 我们的差异必须来自 personal memory、live DAW state、edit recency、reversibility 与 implicit utility feedback，而不是只换 encoder。

### Freesound Loop Dataset

[FSLD](https://arxiv.org/abs/2008.11507) 包含 9,455 个 Creative Commons loops，并提供 instrument、tempo、meter、key 和 genre annotations。

用途：

- backbone probe；
- role/key/tempo-aware hard negative pool；
- weak pretraining；
- 不作为真实 continuation utility 的 test ground truth。

## 5. 新的研究主张

### 主任务

给定：

```text
当前 Audiotool document state S
用户历史 fragments F = {f1...fn}
当前创作意图 I（可为空）
```

学习：

```text
u(S, I, fi) → fragment fi 对“下一步创作是否有用”的效用
```

这里的 utility 不是：

```text
semantic similarity
same genre
same key
user generally likes it
```

而是：

> 在当前 session 中，这个个人 fragment 是否值得被预听、插入，并在短时间内保留。

### 可检验的新颖性

1. **Live document-conditioned personal retrieval：** query 来自真实 DAW entity graph，而不是完整歌曲或单个 seed loop。
2. **Continuation utility：** 标签来自 preview/insert/undo 与 pairwise judgment，不把 acoustic similarity 当最终目标。
3. **Memory provenance：** 模型使用 fragment 的创作时间、原项目、过去接受行为，但不使用全局 popularity。
4. **Agency-preserving outcome：** 系统推荐已有个人材料，结果可解释、可预听、可撤销。

### 不应宣称

- “第一个 composition-aware loop recommender”；
- “SOTA music recommendation model”；
- “模型理解音乐人的意图”；
- “提升创造力”——除非正式研究支持。

## 6. SessionGraph：用 Nexus 深度，而不是截图式集成

Nexus 官方文档说明 project 由 entities 构成，可查询实体、监听更新并修改 document。已检查的公开文档给出了 Samples API，但没有找到可依赖的 project mixdown contract。因此 v1 架构只依赖已文档化的 entities/samples；若未来发现 mixdown API，须经 contract test 后才能进入数据路径。

来源：[Nexus 0.0.17 docs](https://developer.audiotool.com/js-package-documentation/)、[document overview](https://developer.audiotool.com/js-package-documentation/documents/Overview.html)。

### 6.1 Graph schema

```python
class SessionRegion(BaseModel):
    entity_id: str
    track_id: str
    kind: Literal["audio", "note", "automation"]
    role: Literal[
        "drums", "bass", "harmony", "melody", "vocal", "fx", "unknown"
    ]
    role_source: Literal["nexus_entity", "user_tag", "classifier", "unknown"]
    role_confidence: float | None
    start_ticks: int
    duration_ticks: int
    distance_to_playhead_ticks: int
    modified_recency: float
    sample_id: str | None
    embedding_ref: str | None
    pitch_class_histogram: list[float] | None
    onset_grid: list[float] | None


class SessionGraph(BaseModel):
    project_id: str
    document_revision: str
    bpm: float | None
    time_signature: tuple[int, int] | None
    playhead_ticks: int
    regions: list[SessionRegion]
    active_roles: list[str]
    missing_role_hints: list[str]
    intent: str
```

### 6.2 Tokenization

每个 region token 的 v0 schema：

```text
128-d projected audio/music embedding
 16-d role embedding
 12-d pitch-class histogram
 16-d onset grid
 16-d sinusoidal start/duration encoding
  8-d edit/playhead recency encoding
  8-d type/track flags
```

限制：

```text
max_region_tokens 由 graph-coverage–latency curve 选择；32 只是首个 benchmark 点
优先保留 playhead 附近、最近修改、未 mute 的 regions
同一 track 超过上限时做 deterministic pooling
不得随机截断造成不可复现
```

子向量维数、token cap、低秩维数、layer 数和 dropout 都是模型超参数，不由相关文献直接保证。它们必须写入 config、进入容量/延迟 ablation，并在 test split 解封前锁定。

`role` 只在 Nexus entity type 或用户 tag 能直接支持时作为高置信特征；classifier 推断必须保存 confidence，低置信时回到 `unknown`，不得用推断出的 “missing bass” 生成确定性解释。

### 6.3 Audio 获取策略

优先级：

1. 已经在 Pocket Producer 缓存中、且 SHA256 相同的 sample embedding；
2. Nexus Samples API 合法可读取的 sample，显式同意后异步计算；
3. 无 audio 权限时只使用 MIDI/entity/metadata token；
4. 从不伪造缺失 embedding；mask 必须进入模型。

原始 Audiotool project token 不进入 model service；浏览器或受控 backend token flow 必须单独 threat-model。

## 7. PocketRank-Context-450K

### 7.1 两阶段架构

#### Stage A：candidate generation

目标是低成本产生高召回候选，不承担最终解释。候选数 `K` 不是先验真理，必须从 `Recall@K–latency` 曲线选择。

```text
CLAP joint space:
  context CLAP audio + CLAP text intent + CLAP memory → semantic ranking

music-only space:
  MusicFM/MuQ context audio + music memory → structural ranking

structured retrieval:
  tempo/key-confidence/role/duration filters → rules ranking

ranked lists → Reciprocal Rank Fusion → candidate pool K
```

不同 backbone 的向量不得直接相加：CLAP 与 MusicFM/MuQ 不是同一向量空间。每个空间独立归一化、检索，再用 [Reciprocal Rank Fusion](https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/) 做无需分数可比性的 late fusion。若 v1 只选出一个 backbone，则只运行该空间和 rules list。

召回：

```text
user_id / deleted / license hard filter
→ exact or ANN search in each representation space
→ per-space ranked lists
→ RRF fusion
→ deleted/invalid/unlicensed hard filter
→ duration/format constraints
→ candidate pool K selected on validation
```

两阶段 candidate-generation/ranking 有成熟推荐系统依据，例如 [YouTube recommendation architecture](https://research.google.com/pubs/archive/45530.pdf)；但个人 fragment library 未必大到需要 ANN。必须在代表性 library-size fixtures 上比较 exact cosine 与 Mongo vector search；若 exact 已满足 SLO 且更易复现，就采用 exact，不能用“前沿”替代必要性证明。

#### Stage B：context-aware reranking

```python
class PocketRankContext(nn.Module):
    def __init__(self, input_dim: int, d_model: int = 128):
        super().__init__()
        # A shared projection keeps region and candidate representations in
        # one metric space and keeps a 1024-d backbone under the 500K budget.
        self.input_projection = nn.Linear(input_dim, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=4,
            dim_feedforward=256,
            dropout=0.10,
            batch_first=True,
            norm_first=True,
        )
        self.context_encoder = nn.TransformerEncoder(layer, num_layers=2)
        self.low_rank_u = nn.Linear(d_model, 16, bias=False)
        self.low_rank_v = nn.Linear(d_model, 16, bias=False)
        self.structured_head = nn.Sequential(
            nn.Linear(18, 32),
            nn.GELU(),
            nn.Linear(32, 1),
        )

    def forward(self, region_tokens, mask, candidate, structured):
        encoded = self.context_encoder(
            self.input_projection(region_tokens),
            src_key_padding_mask=mask,
        )
        context = masked_attention_pool(encoded, mask)
        candidate = self.input_projection(candidate)
        compatibility = (
            self.low_rank_u(context) * self.low_rank_v(candidate)
        ).sum(dim=-1)
        return compatibility + self.structured_head(structured).squeeze(-1)
```

当 `input_dim=1024` 时预计可训练参数约 400K；最终以导出脚本实际统计为准，并以 `<500K` 单元测试为硬门。Model Card 只能写实际统计值，不能写估计值。

`TransformerEncoder` 的合理性来自 Nexus region 是集合且 region 之间存在交互；[Set Transformer](https://proceedings.mlr.press/v97/lee19d.html) 为 attention-based permutation-invariant set modeling 提供了方法依据。但它并不证明两层 Transformer 会赢。必须按模型容量梯子比较：

```text
L0  rules / linear or logistic ranker
L1  mean-pooled DeepSets/MLP
L2  PocketRank-Context attention model
```

选择规则为 held-out 表现、稳定性与延迟共同决定。是否启用 L2 由 source-separated learning curve 决定：若增加训练数据未带来稳定 validation 收益，或不同 seed 方差大于相对 L0/L1 的收益，L2 只能作为 exploratory model。

### 7.2 Structured features

```text
tempo distance with octave/double-time awareness
key compatibility + key confidence
role complementarity
duration/bar fit
onset-density complementarity
spectral occupancy complementarity
candidate recency
candidate prior accepts/previews/undos
same-project penalty or boost
distance from current playhead context
intent similarity
missing-modality masks
```

“complementarity”不能被写死为总是越不同越好；模型学习其影响，规则只负责安全和格式约束。

### 7.3 Explanation

解释由三类可核验证据组成：

```text
Document evidence:
“Your current session has drums and harmony but no bass region.”

Feature evidence:
“121 BPM is close to the project’s 120 BPM.”

Memory provenance:
“Captured three weeks ago while working on ‘Night Bus’.”
```

禁止：

```text
“This will make the chorus emotionally powerful.”
“The model understands this is what your song needs.”
```

Neural score 本身不伪装成完整可解释性；UI 必须区分：

```text
Why it was eligible
Why it ranked highly
What remains uncertain
```

### 7.4 Top-3 slate

先得到 utility score，再用 constrained MMR 选择 slate。[MMR](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf) 支持在 relevance 与 novelty 之间重排，但不能证明下面的音乐权重：

```python
slate_score = (
    utility
    - lambda_similarity * max_similarity_to_selected
    + lambda_role * missing_role_coverage
)
```

`lambda_similarity` 与 `lambda_role` 由 validation/pilot 选择并写入 artifact，不在论文中伪装成通用常数。ILD 只是离线 proxy；音乐推荐研究显示离线 intra-list similarity 与人类多样性感知未必一致，因此 pilot 同时收集 perceived diversity。

最终三张卡标记：

```text
Best fit
Useful contrast
From your memory
```

标签由可计算规则决定，不由 LLM 美化。

## 8. 训练数据：三层证据，不混淆强弱

### Layer A：weak public pretraining

来源：

- FSLD 中逐条许可证允许研究处理与再分发的子集，不把 “Creative Commons” 当作统一许可；
- Neural Loop Combiner 的 FMA construction recipe；
- 明确许可的自有/Audiotool demo materials。

任务：

```text
context = 2–4 个 compatible regions
positive = leave-one-region-out fragment
easy negative = tempo/key/role 不匹配
hard negative A = tempo/key 相同但来自不同 composition
hard negative B = timbre 相似但 role 重复
hard negative C = same tag but poor temporal fit
```

public weak labels 只能用于 pretraining；held-out human test 不能以同样的 heuristics 生成，否则评估会循环论证。

### Layer B：explicit pairwise labels

```json
{
  "session_id": "s...",
  "left_fragment_id": "f...",
  "right_fragment_id": "f...",
  "choice": "left",
  "reason_codes": ["supports_next_step", "rhythmic_fit"],
  "confidence": 4,
  "participant_hash": "p...",
  "models_hidden": true
}
```

最低目标：

```text
pilot: 1 participant × 20 pairs
LBD initial: 3–5 participants × 20 pairs
camera-ready: 6–8 participants × 30 pairs
```

### Layer C：implicit action feedback

先记录原始事件，不在采集时把任意时长阈值固化成标签：

```text
preview_started / preview_stopped + duration_ms
insert + timestamp
undo + timestamp + target insertion id
explicit skip
session close / next edit
not exposed = unknown, never negative
```

`preview duration`、`retention duration` 与 `undo delay` 如何映射成训练权重属于本项目假设，必须在 pilot 后预注册；初投只把 explicit pairwise choice 当主要监督，把行为事件作为描述性或敏感性分析。

每个 exposure 必须记录：

```text
request_id
model_id
candidate set hash
rank position
selection propensity
timestamp
session revision
event
```

研究流量采用预注册的受控 interleaving/randomization，避免只从当前模型展示的结果中学习，造成 position/exposure bias；比例由 pilot 的风险与样本量决定，不预先伪装成有统计把握。比赛 demo 关闭 exploration。

## 9. Loss、负样本与个性化

### 9.1 预训练

InfoNCE：

```python
loss_retrieval = cross_entropy(
    context_embeddings @ candidate_embeddings.T / temperature,
    target_indices,
)
```

### 9.2 重排

Pairwise BPR：

```python
loss_pair = -F.logsigmoid(
    preferred_score - rejected_score
).mean()
```

当每个 session 有可靠 graded relevance 时，再加入 LambdaLoss / listwise objective 优化 nDCG@3；没有 graded labels 时不要为了“前沿”硬上 listwise loss。

### 9.3 个性化

比赛前不训练 per-user parameter。`accepted-memory centroid` 只作为 non-parametric baseline：

```python
accepted_memory_centroid = exponential_moving_average(
    embeddings_of_retained_inserts,
    decay=validation_selected_decay,
)
```

EMA 及其 decay 没有 task-specific 先验证据，必须做 `no personalization / mean history / EMA history` ablation。per-user adapter 不使用任意“50 个事件”门槛；只有预先定义的最小训练/验证分割可形成、且 temporal held-out session 有稳定收益时才启用。

## 10. PocketBench：先证明 backbone，再训练

### 10.1 固定任务

```text
P1  audio-to-audio fragment similarity
P2  text intent-to-fragment retrieval
P3  session-to-compatible-fragment retrieval
P4  human pairwise continuation preference
```

P1/P2 是 representation diagnostics，不是最终研究任务；P3/P4 才能支持 continuation claim。即使 backbone 在 P1/P2 获胜，只要 P3/P4 未改善，就不能成为产品选择依据。

### 10.2 Backbone bake-off

```bash
python research/benchmark_backbones.py \
  --models msclap-2023,laion-clap-music,musicfm-fma,mert-95m,muq,m2d-clap-2025 \
  --dataset research/data/pocketbench-v1.jsonl \
  --out artifacts/backbone-bakeoff.json
```

输出：

```json
{
  "dataset_hash": "sha256:...",
  "models": {
    "model-id": {
      "recall_at_10": 0.0,
      "ndcg_at_10": 0.0,
      "pairwise_accuracy": 0.0,
      "latency_p50_ms": 0,
      "latency_p95_ms": 0,
      "peak_vram_mb": 0,
      "embedding_bytes_per_fragment": 0,
      "license_status": "approved|research-only|blocked"
    }
  }
}
```

### 10.3 选择函数

production backbone 必须：

```text
license_status == approved
Recall@K curve reported and K selected before test evaluation
cached query latency measured on demo hardware
no numerical instability on 100% benchmark audio
```

若多个模型通过，以 session retrieval nDCG 优先，不以参数量或外部排行榜优先。

## 11. 评估设计

### 11.1 Offline

必须报告：

```text
Stage A: Recall@K curve, candidate-pool coverage
Stage B with pairwise labels: pairwise accuracy, log loss, participant-level wins
Stage B only with independent 0–3 grades: nDCG@3
Stage B only with one known positive: MRR
Slate: ILD@3 + role coverage + perceived diversity
Calibration: Brier/reliability plot only for a defined probability target and adequate N
System: p50/p95 latency, peak RAM/VRAM, cache hit rate
```

nDCG 需要 graded relevance，不能从单个 pairwise choice 自动制造；ECE 在小样本下也不稳定。LBD 若只有 3–5 位 participant，应报告原始计数、participant-level descriptive interval 和 effect direction，不把 bootstrap CI 写成总体显著性证明。

baselines：

```text
random
recency
rules-v1
text-only Voyage cosine
CLAP cosine
mean-session embedding
PocketRank-Context
```

ablations：

```text
no Nexus region structure
no audio embeddings
no intent
no personal memory centroid
no edit recency
no structured branch
no hard negatives
no MMR diversity
```

split：

```text
public weak data: by source track/pack/uploader
human study: by participant and project
personal feedback: temporal split
```

同一音频的 time-stretch、pitch-shift 或 duplicate hash 不得跨 split。

### 11.2 Online/formative

主要行为指标：

```text
time to first meaningful insert
preview-to-insert conversion
retained insert at 60 seconds
undo rate
number of candidates previewed
```

体验指标：

```text
perceived control
perceived relevance
interruption to flow
surprise without loss of authorship
```

“creativity increased”不是短实验能可靠支持的主要 outcome。

## 12. Serving：不把 foundation model 放在点击路径

### 12.1 三个 plane

```text
Embedding plane:
GPU/CPU worker, asynchronous, idempotent, cached by SHA256

Ranking plane:
CPU FastAPI/ONNX, loaded PocketRank-Context only

Interaction plane:
browser Nexus client, preview/insert/undo, rules fallback
```

### 12.2 产品目标，非已有测量

```text
candidate embedding: asynchronous, ≤30 s acceptable
session graph construction: p95 ≤150 ms
exact/ANN candidate search at selected K: p95 ≤100 ms
rerank selected K: p95 ≤100 ms CPU
end-to-end cached rank: p95 ≤500 ms
fallback activation: ≤2 s
```

这些是 demo UX/SLO targets，不是文献结论，也不是当前系统测量。必须在目标机器、冷缓存和 warm cache 三种条件下 benchmark；未达成时报告实测值并触发简化路径。

### 12.3 Hugging Face

Hugging Face Space 用途：

```text
public research demo
backbone benchmark
asynchronous embedding worker
model card and reproducible artifact hosting
```

不承担：

```text
唯一 production rank endpoint
OAuth token storage
uncached synchronous foundation inference during live demo
```

官方说明免费 CPU Space 长期无访问会休眠；Inference Endpoint scale-to-zero 也会冷启动，可能返回错误或等待数分钟。因此所有在线路径必须有 cache/fallback。

来源：[Spaces hardware](https://huggingface.co/docs/hub/spaces-gpus)、[Inference Endpoint autoscaling](https://huggingface.co/docs/inference-endpoints/en/guides/autoscaling)。

## 13. LBD 最小可信版本与后续版本

### 2026-08-09 初投允许的版本

```text
Required:
真实 Nexus read/write
SessionGraph schema
recency/rules/text-only/CLAP baselines
PocketBench v1
至少 1 pilot 或小规模 pairwise listening evidence
完整 limitations

Preferred:
PocketRank-Context weak-pretrained result

Not required:
完整 6–8 人研究
个性化 user adapter
PocketRank 必须赢
远程 GPU production deployment
```

如果 `PocketRank-Context` 未在 manuscript freeze 前通过 held-out gate：

```text
论文主张 = task + live system + benchmark
learned model = ongoing work
比赛默认 = rules/CLAP hybrid
```

### Camera-ready / poster

```text
6–8 participant formative study
PocketRank-Context full result
ablation
calibration
latency
failure cases
model/data card
```

### 正式论文潜力

LBD 后的正式论文可以聚焦：

> Learning continuation utility from reversible actions in a live music-production environment.

真正需要的增量：

```text
larger multi-session dataset
counterfactual/propensity-aware evaluation
cross-user generalization
comparison with composition-aware loop baselines
longitudinal creative workflow study
```

## 14. Implementation Tasks

### Task A: Secret audit and representation migration gate

**Files:**

- Modify: `.gitignore`
- Create: `backend/representations/schemas.py`
- Create: `backend/tests/representations/test_schemas.py`
- Create: `docs/security/credential-rotation-checklist.md`

- [ ] 运行 tracked-file、Git object、历史路径和 secret scanner 四项检查；保存不含 secret 内容的审计日志。
- [ ] 若审计发现曾暴露才轮换相应 credentials；当前被 ignore 的本地文件不进入 Docker context、submission archive 或录屏。
- [ ] 写 representation schema tests，拒绝没有 model revision、input hash 或 dims 的向量。
- [ ] 将旧 `embedding` 明确迁移为 `representations.text`，不猜测其模态。
- [ ] Commit:

```bash
git add .gitignore backend/representations backend/tests/representations docs/security
git commit -m "security: audit credentials and version model representations"
```

### Task B: Backbone bake-off harness

**Files:**

- Create: `backend/representations/adapters/base.py`
- Create: `backend/representations/adapters/msclap.py`
- Create: `backend/representations/adapters/laion_clap.py`
- Create: `backend/representations/adapters/musicfm.py`
- Create: `research/benchmark_backbones.py`
- Create: `research/tests/test_benchmark_backbones.py`

- [ ] 先用 fake adapters 测试 identical input hash cache、dimension validation、NaN rejection 和 deterministic pooling。
- [ ] 所有 adapter 实现相同协议：

```python
class AudioRepresentationAdapter(Protocol):
    model_card: RepresentationModelCard

    def encode_audio(self, waveform: FloatArray, sample_rate: int) -> FloatArray:
        ...

    def encode_text(self, texts: list[str]) -> FloatArray | None:
        ...
```

- [ ] 首轮只实现 MS-CLAP、LAION-CLAP Music 和 MusicFM-FMA；MuQ/MERT/M2D 在时间允许时作为 research adapters。
- [ ] 输出 bake-off JSON 和不可变 dataset hash。
- [ ] Commit:

```bash
git add backend/representations research
git commit -m "research: benchmark music representation backbones"
```

### Task C: Nexus SessionGraph

**Files:**

- Create: `frontend/src/lib/audiotool/session-graph.ts`
- Create: `frontend/src/lib/audiotool/session-graph.test.ts`
- Create: `backend/ranking/session_graph.py`
- Create: `backend/tests/ranking/test_session_graph.py`

- [ ] 用 Nexus offline document 构造 audio/note/automation fixtures。
- [ ] 验证 entity 顺序变化不影响 canonical graph。
- [ ] 验证最多 32 tokens、playhead/recent edit priority 和 missing modality mask。
- [ ] 对 document revision 做 hash；同 revision 不重复生成 query。
- [ ] Commit:

```bash
git add frontend/src/lib/audiotool backend/ranking backend/tests/ranking
git commit -m "feat: encode nexus documents as deterministic session graphs"
```

### Task D: Exact/ANN candidate retrieval decision

**Files:**

- Create: `backend/ranking/retrieval.py`
- Create: `backend/tests/ranking/test_retrieval.py`
- Create: `backend/scripts/backfill_audio_representations.py`

- [ ] 先测试 user isolation、top-k、deleted filter、cache miss 和 empty library。
- [ ] backfill 按 SHA256 幂等，失败可恢复，单个坏音频不终止批次。
- [ ] 将 Stage A 与 Stage B 指标分开记录。
- [ ] Commit:

```bash
git add backend/ranking/retrieval.py backend/tests/ranking/test_retrieval.py backend/scripts
git commit -m "feat: add versioned audio retrieval index"
```

### Task E: PocketRank-Context

**Files:**

- Create: `backend/ranking/context_model.py`
- Create: `backend/ranking/context_features.py`
- Create: `backend/tests/ranking/test_context_model.py`
- Create: `research/train_context_ranker.py`

- [ ] 先测试 padding invariance、masked modality、parameter count、checkpoint schema 和 CPU inference。
- [ ] parameter count hard gate：

```python
assert sum(p.numel() for p in model.parameters() if p.requires_grad) < 500_000
```

- [ ] 使用 weak pretraining + BPR fine-tuning；split by project/source。
- [ ] 保存 safetensors、feature schema、model card、metrics、split manifest。
- [ ] Commit:

```bash
git add backend/ranking backend/tests/ranking research/train_context_ranker.py
git commit -m "feat: train compact session-conditioned context ranker"
```

### Task F: Calibration, slate and feedback

**Files:**

- Create: `backend/ranking/calibration.py`
- Create: `backend/ranking/slate.py`
- Create: `backend/tests/ranking/test_slate.py`
- Modify: `backend/api/routes/ranking.py`

- [ ] 测试 Top-3 不重复、utility order 基本保持、role coverage 和低置信度 abstention。
- [ ] feedback 记录 exposure/propensity，未展示候选不写负标签。
- [ ] 比赛 mode 固定 exploration 为 0；study mode 由 feature flag 控制。
- [ ] Commit:

```bash
git add backend/ranking backend/tests/ranking backend/api/routes/ranking.py
git commit -m "feat: calibrate and diversify continuation recommendations"
```

## 15. Go / No-Go Gates

### Backbone gate

```text
GO:
valid PocketBench result
Recall@K curve and preselected K
license approved
100% finite embeddings

NO-GO:
只凭外部 SOTA 选择
模型卡/权重 revision 不清楚
音频出现 NaN
```

### Learned ranker gate

```text
GO:
held-out task-appropriate metric > strongest simpler baseline
participant-level effect and uncertainty reported
no participant/project leakage
rerank meets measured demo-hardware SLO

NO-GO:
训练集提升、test 无提升
只比较 random
用 heuristics 生成 test labels
```

### LBD claim gate

```text
若模型过 gate：
“The compact context ranker improved ... on PocketBench v1.”

若模型未过 gate：
“We introduce the task, system and benchmark; learned ranking remains ongoing.”
```

### Product gate

```text
foundation service down → cached ranking or rules works
new fragment embedding pending → visible pending state
low confidence → expose uncertainty
OAuth/token absent from model service logs
```

## 16. 最终推荐优先级

```text
P0  Credential exposure audit and public-repo safety
P0  Nexus real read/write
P0  Versioned audio representations
P0  PocketBench + MS-CLAP/LAION/MusicFM bake-off
P1  exact/ANN retrieval decision + SessionGraph
P1  PocketRank-Context-450K
P1  Top-3 slate + insert/undo feedback
P2  MuQ/M2D research comparisons
P2  6–8 participant study
P3  per-user adapter
P3  remote GPU serving optimization
```

这套顺序的核心判断是：

> “不 toy”来自任务定义、数据构造、上下文表示、负样本、评估和真实工作流，而不是把模型参数量做大。
