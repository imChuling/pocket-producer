# Pocket Producer 2026 Dual-Track Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 2026-08-22 前交付一个可评审的独立 Pocket Producer：它通过 Audiotool Nexus 读取当前创作上下文，从用户的历史声音碎片中找出最有助于“继续创作”的三个候选，并让用户预听、插入时间线、撤销，同时用一个可评估的小型排序模型形成清晰的研究贡献。

**Architecture:** Pocket Producer 保持独立仓库与品牌，只借用 HARP 的三个方法论：可插拔模型适配器、明确的 Model Card、远程模型服务与本地基线可切换；不得依赖、导入或部署 HARP。浏览器端 Nexus 适配层负责 Audiotool OAuth、项目读取和写回；异步 worker 生成带血缘信息的 audio/text representations；在线 FastAPI 服务以 `SessionGraph` 表示项目上下文，在各表示空间分别检索并用 RRF 融合，再比较 linear、DeepSets 与 `PocketRank-Context-450K` 三档 reranker，始终保留确定性的规则基线。大型 foundation encoder 不进入同步排序请求。

**Tech Stack:** Next.js 16.2.6、React 19、TypeScript、Audiotool Nexus（固定经验证版本）、FastAPI、Pydantic、MongoDB、PyTorch、Transformers、FAISS / MongoDB Vector Search、ONNX Runtime、Vitest、pytest；Hugging Face Space 或容器化 FastAPI 仅承载异步 embedding worker 或研究演示，不作为比赛同步排序的单点依赖。

**Research decision record:** 具体模型对比、许可证风险、`SessionGraph`、训练目标、评估协议和 go/no-go gates 以 [`docs/research/2026-07-25-pocketrank-frontier-architecture.md`](../../research/2026-07-25-pocketrank-frontier-architecture.md) 为准；本冲刺本只保留执行顺序。

**Evidence decision record:** 每项主张的证据强度、反例和允许措辞以 [`2026-07-25-pocketrank-evidence-audit.md`](2026-07-25-pocketrank-evidence-audit.md) 为准；没有 artifact 的计划结果不得写成已完成结果。

---

## 本子的结构：一条主干，两条投稿支线

这不是两份彼此独立的项目计划，也不是把两次投稿混成一套话术。它采用软件分支式结构：

```text
Shared Research Trunk（Task 1–13）
├── Nexus 真实 read/write
├── Session Fingerprint
├── fragment retrieval + Top-3 ranking
├── preview / insert / undo
├── feedback instrumentation
├── versioned representations / exact-or-ANN / ranker ladder
└── evaluation + formative study
             │
             ├── Let's Build Lane（Task 14–15）
             │   └── 产品叙事、稳定部署、2:30 demo、提交
             │
             └── ISMIR LBD Lane（Task 16–18）
                 └── 2+1 页、科学证据、≤5:00 video、poster
```

执行规则：

1. **2026-08-03 前不分叉。** 所有工程工作只服务于同一个 Pocket Producer MVP。
2. **代码和数据永不分叉。** 两条投稿线必须引用同一 commit、同一 evaluation artifact 和同一模型版本。
3. **只分叉表达材料。** Let’s Build 强调体验与 Nexus；ISMIR 强调研究问题、方法、基线和限制。
4. **Shared Trunk 优先。** 任一投稿材料与主闭环冲突时，先保证 Nexus read/write、可撤销性和可信评估。
5. **双重可用证据优先。** 同一个实验图、录屏或用户研究结果，应能同时服务比赛、论文和作品集。

为什么不拆成两本完整计划：

- 两本计划会重复维护任务、日期、模型版本和结果数字。
- 前期如果按投稿类型分工，容易为了视频或论文提前制造不同版本的产品。
- 评委与研究审阅者虽然关心重点不同，但可信度都来自同一个可运行系统。

为什么仍保留两条独立 lane：

- Let’s Build 的完成标准是稳定、清楚、具有平台原生感。
- ISMIR 的完成标准是问题适切、原创、格式合规、证据与限制可信。
- 两套材料有不同截止时间、长度、受众和验收规则，后期不能用同一份文案硬套。

## 0. 共同研究核心与产品论点

### 一句话

> Pocket Producer is a session-aware creative memory system that helps musicians re-enter unfinished work.

### 评委在 30 秒内必须看懂的闭环

```text
Audiotool 当前工程
  → Session Fingerprint
  → 历史碎片召回
  → Continuation Utility 排序
  → 三个有证据的建议
  → 预听 / 插入 / 撤销
  → 接受、跳过、撤销成为研究反馈
```

### 研究问题

1. 加入当前 session context，能否比“最近使用”或“纯 embedding 相似度”更快找到可继续创作的片段？
2. 预测“是否值得下一步使用”的 actionability ranker，能否优于只预测“是否相似”的模型？
3. grounded explanation 与可撤销写回，能否提高音乐人的控制感，而不是让系统替他们创作？

### 只做这些

- 读取 Audiotool 当前项目的轨道、时间位置、节奏、可获得的调性与结构信息。
- 从 Pocket Producer 已有 fragment library 中召回并排序。
- 展示 Top 3，每个建议必须给出可核验依据。
- 预听、插入至 Audiotool、撤销。
- 记录 accept / reject / preview / insert / undo，形成研究数据。
- 对 recency、rules、text-only、audio cosine、mean-session 与 PocketRank-Context 做固定数据集评估。

### 明确不做

- 不做通用 DAW，不重建 Audiotool 编辑器。
- 不做多 Agent 编排，不以 Gemini / ADK 为核心依赖。
- 不从头训练音乐 foundation model。
- 不把 HARP 作为包、子模块、服务依赖或参赛叙事的一部分。
- 不在比赛前扩展到自动编曲、自动混音、多人协作市场或移动端重写。

### 比赛硬门槛

- **Nexus read gate：** 必须从真实 Audiotool 项目读到至少一组可显示的 session 信息。
- **Nexus write gate：** 必须把一个用户选中的 fragment 插入真实项目，且能撤销。
- **Cold-start gate：** 新用户在没有训练模型或外部模型服务时仍可走完整闭环。
- **Research gate：** 至少有两个基线、一个固定测试集、一个预注册指标和可复现评估命令。
- **Portfolio gate：** README 首屏同时呈现一段 15 秒结果视频、系统图、研究结果表和“我具体做了什么”。

## 1. 独立性边界：借 HARP 的方法，不借 HARP 的项目

Pocket Producer 内部定义自己的协议：

```python
class RankerAdapter(Protocol):
    model_card: ModelCard

    def rank(self, request: RankRequest) -> RankResponse:
        ...
```

可插拔实现只有：

- `rules-v1`：比赛保底，零网络、零 GPU。
- `audio-cosine-v1`：冻结 audio encoder 的候选/上下文 cosine。
- `mean-session-v1`：当前项目 active regions 的均值表示。
- `pocketrank-context-v1`：role-aware set encoder + 低秩交互 + 结构化分支。
- `remote-embed-v1`：可选 Hugging Face / FastAPI 异步 embedding worker。

禁止出现：

```text
import pyharp
git submodule ...HARP
HARP runtime required
HARP UI embedded
```

Model Card、`/rank` 协议和 adapter registry 是在 Pocket Producer 中重新定义的轻量实现。这样既能证明从 HARP 学到系统设计能力，也不会让评委误以为这是旧项目换皮。

## 2. 目标目录与文件地图

```text
project/pocket-producer/
├── backend/
│   ├── api/
│   │   ├── main.py                              # 修改：注册 ranking 路由
│   │   └── routes/
│   │       └── ranking.py                       # 新建：model-card/rank/feedback
│   ├── ranking/
│   │   ├── __init__.py                          # 新建
│   │   ├── schemas.py                           # 新建：稳定协议
│   │   ├── features.py                          # 新建：可解释特征
│   │   ├── representations.py                   # 新建：模态/版本/血缘合同
│   │   ├── session_graph.py                     # 新建：Nexus entities→上下文
│   │   ├── retrieval.py                         # 新建：exact/ANN 决策
│   │   ├── fusion.py                            # 新建：RRF
│   │   ├── baselines.py                         # 新建：rules/cosine/mean-session
│   │   ├── context_model.py                     # 新建：PocketRank-Context
│   │   ├── registry.py                          # 新建：本地/远程 adapter
│   │   └── service.py                           # 新建：召回、排序、降级
│   └── tests/
│       ├── ranking/
│       │   ├── test_features.py                 # 新建
│       │   ├── test_baselines.py                # 新建
│       │   ├── test_service.py                  # 新建
│       │   ├── test_representations.py          # 新建
│       │   ├── test_session_graph.py            # 新建
│       │   └── test_context_model.py            # 新建
│       └── api/test_ranking_routes.py            # 新建
├── frontend/
│   ├── package.json                             # 修改：Nexus + Vitest
│   ├── vitest.config.ts                         # 新建
│   └── src/
│       ├── app/audiotool/page.tsx               # 新建：比赛主界面
│       ├── components/audiotool/
│       │   ├── connection-panel.tsx             # 新建
│       │   ├── session-summary.tsx               # 新建
│       │   ├── candidate-card.tsx                # 新建
│       │   └── continuation-panel.tsx            # 新建
│       ├── hooks/use-audiotool.ts                # 新建
│       ├── lib/audiotool/
│       │   ├── client.ts                         # 新建：Nexus 生命周期
│       │   ├── session-fingerprint.ts            # 新建：实体→稳定上下文
│       │   └── insert-fragment.ts                # 新建：上传/插入/撤销
│       ├── lib/ranking-api.ts                    # 新建
│       ├── types/audiotool.ts                    # 新建
│       └── components/top-nav.tsx                # 修改：加入 Audiotool
├── model-service/
│   ├── app.py                                    # 新建：异步 embedding 端点
│   ├── Dockerfile                                # 新建
│   └── README.md                                 # 新建
├── research/
│   ├── protocol.md                               # 新建：研究预注册
│   ├── annotation-schema.md                      # 新建
│   ├── consent-template.md                       # 新建
│   ├── data/README.md                            # 新建：数据血缘
│   ├── bakeoff_backbones.py                      # 新建：表示模型决策
│   ├── train_context_ranker.py                   # 新建
│   ├── evaluate.py                               # 新建
│   └── fixtures/golden_pairs.jsonl               # 新建：无版权音频
├── docs/letsbuild/
│   ├── demo-script.md                            # 新建
│   ├── submission-copy.md                        # 新建
│   ├── judging-evidence.md                       # 新建
│   └── screenshots/                              # 新建
├── docs/ismir2026/
│   ├── lbd.tex                                   # 新建：2+1 页 extended abstract
│   ├── references.bib                            # 新建：逐条人工核验
│   ├── claim-evidence-ledger.md                   # 新建：论文主张与证据
│   ├── supplementary-video-script.md             # 新建：5 分钟以内
│   ├── poster-outline.md                         # 新建：录取后制作
│   └── submission-checklist.md                   # 新建
├── ARCHITECTURE.md                               # 新建
├── MODEL_CARD.md                                 # 新建
├── DATA_CREDITS.md                               # 新建
└── README.md                                     # 修改：作品集首屏
```

## 3. 稳定协议先行

以下协议一旦进入前后端集成阶段，只能向后兼容地新增字段，避免 Nexus、模型和 UI 三条线互相阻塞。

```python
# backend/ranking/schemas.py
from typing import Literal
from pydantic import BaseModel, Field


class SessionFingerprint(BaseModel):
    project_id: str
    bpm: float | None = None
    key: str | None = None
    playhead_seconds: float = Field(ge=0)
    track_count: int = Field(ge=0)
    active_track_types: list[str] = []
    recent_entity_ids: list[str] = []
    text_intent: str = ""


class FragmentCandidate(BaseModel):
    fragment_id: str
    duration_seconds: float = Field(gt=0)
    bpm: float | None = None
    key: str | None = None
    tags: list[str] = []
    created_at_iso: str
    audio_url: str
    audio_embedding: list[float] | None = None


class RankRequest(BaseModel):
    session: SessionFingerprint
    candidates: list[FragmentCandidate]
    model_id: str = "rules-v1"
    limit: int = Field(default=3, ge=1, le=10)


class RankEvidence(BaseModel):
    code: Literal[
        "tempo_match", "key_match", "track_gap", "intent_match",
        "novelty", "recency", "model_signal"
    ]
    label: str
    contribution: float


class RankedCandidate(BaseModel):
    fragment_id: str
    score: float
    evidence: list[RankEvidence]


class RankResponse(BaseModel):
    request_id: str
    model_id: str
    fallback_used: bool
    candidates: list[RankedCandidate]


class FeedbackEvent(BaseModel):
    request_id: str
    project_id: str
    fragment_id: str
    event: Literal["preview", "accept", "reject", "insert", "undo"]
    rank_position: int = Field(ge=1)
    model_id: str
```

前端对应类型不得自行改名：

```ts
// frontend/src/types/audiotool.ts
export type SessionFingerprint = {
  project_id: string;
  bpm: number | null;
  key: string | null;
  playhead_seconds: number;
  track_count: number;
  active_track_types: string[];
  recent_entity_ids: string[];
  text_intent: string;
};

export type RecommendationEvent =
  | "preview"
  | "accept"
  | "reject"
  | "insert"
  | "undo";
```

## 4. 实施任务

> **Shared Research Trunk — Task 1–13:** 在 Task 13 验收前，不为任何单一投稿复制代码、数据或模型。

### Task 1: 冻结比赛路径与可复现环境

**Files:**

- Modify: `frontend/package.json`
- Modify: `backend/pyproject.toml`
- Create: `docs/letsbuild/judging-evidence.md`
- Create: `research/data/README.md`

- [ ] 在改动 Next.js 代码前完整阅读本仓库 `frontend/AGENTS.md`，再阅读 `frontend/node_modules/next/dist/docs/` 中与 App Router、client components、environment variables 相关的页面。
- [ ] 记录当前可工作的前后端命令和版本。
- [ ] 固定经本地验证的 `@audiotool/nexus` 精确版本，不使用 `^` 或 `latest`。
- [ ] 加入 `vitest`、`jsdom`、Testing Library；后端加入训练所需依赖，但将大型 encoder 下载留到显式 research extra。

目标脚本：

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "check": "next lint && tsc --noEmit && vitest run"
  }
}
```

后端依赖分组：

```toml
[project.optional-dependencies]
research = [
  "torch>=2.6,<3",
  "transformers>=4.53,<5",
  "sentence-transformers>=5,<6",
  "safetensors>=0.5,<1",
]
```

- [ ] 写 `judging-evidence.md`，只使用可截图或可运行命令证明的主张：

```md
| Claim | Evidence | Status |
|---|---|---|
| Reads an Audiotool project | 15s screen capture + offline fixture test | pending |
| Inserts a fragment | continuous screen capture | pending |
| Reversible | undo test + screen capture | pending |
| Model beats recency baseline | evaluate.py JSON output | pending |
```

- [ ] 运行基线验证：

```bash
cd frontend && npm run check
cd ../backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -q
```

Expected: 两个命令退出码为 0；若已有失败，先记录到 `judging-evidence.md` 的 “Pre-existing failures”，不可把它们算作新功能完成。

- [ ] Commit:

```bash
git add frontend/package.json frontend/package-lock.json backend/pyproject.toml docs/letsbuild/judging-evidence.md research/data/README.md
git commit -m "chore: freeze letsbuild development environment"
```

### Task 2: 用测试锁定 ranking contract 与规则基线

**Files:**

- Create: `backend/ranking/__init__.py`
- Create: `backend/ranking/schemas.py`
- Create: `backend/ranking/features.py`
- Create: `backend/ranking/baselines.py`
- Create: `backend/tests/ranking/test_features.py`
- Create: `backend/tests/ranking/test_baselines.py`

- [ ] 先写失败测试，验证 tempo 接近、调性一致和意图标签命中能提高分数：

```python
def test_rules_ranker_prefers_actionable_match():
    session = SessionFingerprint(
        project_id="p1", bpm=120, key="A minor", playhead_seconds=18,
        track_count=2, active_track_types=["drums"], text_intent="dark bass"
    )
    matching = candidate("match", bpm=121, key="A minor", tags=["dark", "bass"])
    unrelated = candidate("other", bpm=88, key="C major", tags=["bright", "vocal"])

    result = RulesRanker().rank(RankRequest(session=session, candidates=[unrelated, matching]))

    assert result.candidates[0].fragment_id == "match"
    assert {e.code for e in result.candidates[0].evidence} >= {
        "tempo_match", "key_match", "intent_match"
    }
```

- [ ] 运行并确认失败原因是模块尚未实现：

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest tests/ranking/test_baselines.py -q
```

Expected: `ModuleNotFoundError` 或未定义 `RulesRanker`。

- [ ] 实现确定性特征，所有数值归一化到 `[0, 1]`：

```python
def tempo_match(session_bpm: float | None, fragment_bpm: float | None) -> float:
    if session_bpm is None or fragment_bpm is None:
        return 0.0
    ratio = abs(session_bpm - fragment_bpm) / max(session_bpm, 1.0)
    return max(0.0, 1.0 - ratio / 0.25)
```

- [ ] 实现可解释规则分数；每个权重同时生成 evidence，不允许先生成自然语言再反推理由：

```python
WEIGHTS = {
    "tempo_match": 0.30,
    "key_match": 0.20,
    "track_gap": 0.10,
    "intent_match": 0.25,
    "novelty": 0.10,
    "recency": 0.05,
}
```

- [ ] 加入边界测试：空 candidates、缺失 BPM/key、相同分数稳定按 `fragment_id` 排序、limit 裁切、非法 duration。
- [ ] 运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest tests/ranking -q
```

Expected: PASS。

- [ ] Commit:

```bash
git add backend/ranking backend/tests/ranking
git commit -m "feat: add explainable continuation ranking baseline"
```

### Task 3: 建立 rank / model-card / feedback API 与安全降级

**Files:**

- Create: `backend/ranking/registry.py`
- Create: `backend/ranking/service.py`
- Create: `backend/api/routes/ranking.py`
- Modify: `backend/api/main.py`
- Create: `backend/tests/ranking/test_service.py`
- Create: `backend/tests/api/test_ranking_routes.py`

- [ ] 先写 API 失败测试：

```python
def test_rank_requires_authenticated_user(client):
    response = client.post("/api/ranking/rank", json=rank_payload())
    assert response.status_code == 401


def test_unknown_model_falls_back_to_rules(auth_client):
    payload = rank_payload(model_id="missing-model")
    response = auth_client.post("/api/ranking/rank", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["model_id"] == "rules-v1"
    assert body["fallback_used"] is True
```

- [ ] 实现 registry，远程模型超时、无效响应或未配置时都降级，但不得吞掉审计信息：

```python
class RankerRegistry:
    def resolve(self, requested: str) -> tuple[RankerAdapter, bool]:
        adapter = self._adapters.get(requested)
        if adapter is not None and adapter.healthy():
            return adapter, False
        return self._adapters["rules-v1"], requested != "rules-v1"
```

- [ ] 暴露端点：

```text
GET  /api/ranking/model-card
POST /api/ranking/rank
POST /api/ranking/feedback
```

- [ ] `feedback` 文档必须包含 `user_id`（来自 Firebase token，不接受请求体传入）、时间、模型版本、request id、rank position 和事件；不得存 OAuth access token。
- [ ] `request_id` 使用服务端 UUID；rank response 和反馈文档可关联。
- [ ] 将 router 注册到 `backend/api/main.py`。
- [ ] 运行：

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest tests/ranking tests/api/test_ranking_routes.py -q
```

Expected: PASS，且 unknown model 测试明确看到 fallback。

- [ ] Commit:

```bash
git add backend/api backend/ranking backend/tests
git commit -m "feat: expose versioned ranking and feedback api"
```

### Task 4: Nexus 离线文档与浏览器生命周期

**Files:**

- Create: `frontend/src/lib/audiotool/client.ts`
- Create: `frontend/src/hooks/use-audiotool.ts`
- Create: `frontend/src/types/audiotool.ts`
- Create: `frontend/src/lib/audiotool/client.test.ts`

- [ ] 先用 Nexus 官方离线文档/fixture 写测试，不以真实账号作为唯一测试方式。
- [ ] 测试状态机：

```ts
type AudiotoolStatus =
  | "idle"
  | "authorizing"
  | "connected"
  | "project-open"
  | "error";

it("never opens a project before authorization succeeds", async () => {
  const nexus = fakeNexus({ authorize: "pending" });
  const controller = createAudiotoolController(nexus);
  controller.connect();
  expect(nexus.openProject).not.toHaveBeenCalled();
});
```

- [ ] 在浏览器端封装 Nexus；OAuth token 只存在 Nexus/browser 生命周期中，不发送给 Pocket Producer 后端：

```ts
export async function connectAudiotool() {
  const nexus = getNexusSingleton();
  await nexus.authorize({ scopes: ["project:write"] });
  return nexus;
}
```

- [ ] `useAudiotool` 暴露 `connect`、`openProject`、`closeProject`、`status`、`error`，页面卸载时清理监听器。
- [ ] 对拒绝授权、弹窗关闭、项目不存在、重复 connect、离线状态写明确测试。
- [ ] 运行：

```bash
cd frontend
npm test -- src/lib/audiotool/client.test.ts
```

Expected: PASS；测试不得访问真实网络。

- [ ] 在真实 Audiotool 账号上手工通过 read gate，证据保存为截图和 15 秒连续录屏；不提交 token。
- [ ] Commit:

```bash
git add frontend/src/lib/audiotool frontend/src/hooks frontend/src/types
git commit -m "feat: add isolated audiotool nexus lifecycle"
```

### Task 5: 从 Nexus 实体生成稳定 Session Fingerprint

**Files:**

- Create: `frontend/src/lib/audiotool/session-fingerprint.ts`
- Create: `frontend/src/lib/audiotool/session-fingerprint.test.ts`
- Create: `frontend/src/components/audiotool/session-summary.tsx`

- [ ] 先写 fixture 测试，输入顺序不同必须得到相同 fingerprint：

```ts
it("is deterministic across entity order", () => {
  const a = fingerprintFromEntities(project, [trackA, trackB]);
  const b = fingerprintFromEntities(project, [trackB, trackA]);
  expect(a).toEqual(b);
});
```

- [ ] 转换时只保留排序所需的最小信息，不上传完整 Audiotool 工程：

```ts
return {
  project_id: project.id,
  bpm: finiteOrNull(project.tempo),
  key: normalizeKey(project.key),
  playhead_seconds: Math.max(0, transport.positionSeconds),
  track_count: tracks.length,
  active_track_types: uniqueSorted(tracks.map(classifyTrack)),
  recent_entity_ids: recentIds.slice(0, 20).sort(),
  text_intent: userIntent.trim().slice(0, 240),
};
```

- [ ] 对缺失 tempo/key、空项目、未知 entity、NaN playhead 写测试。
- [ ] UI 显示系统实际读到的字段，并允许用户编辑 text intent；不能假装读到了 Nexus 没提供的数据。
- [ ] 运行：

```bash
npm test -- src/lib/audiotool/session-fingerprint.test.ts
```

Expected: PASS。

- [ ] Commit:

```bash
git add frontend/src/lib/audiotool frontend/src/components/audiotool/session-summary.tsx
git commit -m "feat: derive transparent audiotool session fingerprints"
```

### Task 6: 完成 Top-3 continuation UI

**Files:**

- Create: `frontend/src/lib/ranking-api.ts`
- Create: `frontend/src/components/audiotool/candidate-card.tsx`
- Create: `frontend/src/components/audiotool/continuation-panel.tsx`
- Create: `frontend/src/app/audiotool/page.tsx`
- Modify: `frontend/src/components/top-nav.tsx`
- Create: `frontend/src/components/audiotool/continuation-panel.test.tsx`

- [ ] 先写交互测试：成功返回三个候选、空库、后端失败、规则 fallback 标签、重复点击。
- [ ] API 只发送 session fingerprint 与候选元数据；音频文件沿用受保护 fragment audio route。
- [ ] 卡片必须显示：

```text
标题 / 时长
“Why this now” 证据（最多 3 条）
Preview
Insert into Audiotool
Skip
```

- [ ] 排序解释来自 `RankEvidence` 的固定 label，不让 LLM 生成无依据的解释。
- [ ] 页面状态使用清楚的单一主动作：

```tsx
if (status === "idle") return <ConnectionPanel onConnect={connect} />;
if (status === "connected") return <ProjectPicker onOpen={openProject} />;
if (status === "project-open") return <ContinuationPanel session={session} />;
return <RecoverableError error={error} onRetry={retry} />;
```

- [ ] 在 top nav 加入 `Audiotool` 项；保留已有 Capture / Projects / DNA。
- [ ] 运行：

```bash
cd frontend
npm test
npm run check
```

Expected: PASS；360px 与 1440px 宽度无横向滚动。

- [ ] Commit:

```bash
git add frontend/src
git commit -m "feat: add session-aware continuation workspace"
```

### Task 7: 预听、写回与可撤销交易

**Files:**

- Create: `frontend/src/lib/audiotool/insert-fragment.ts`
- Create: `frontend/src/lib/audiotool/insert-fragment.test.ts`
- Modify: `frontend/src/components/audiotool/candidate-card.tsx`
- Modify: `frontend/src/components/audiotool/continuation-panel.tsx`

- [ ] 先写交易测试：等待 sample ready 后才插入；失败不产生部分状态；undo 只撤销本次插入。

```ts
it("inserts only after the uploaded sample is ready", async () => {
  const nexus = fakeNexus();
  await insertFragment(nexus, fragment, position);
  expect(nexus.calls).toEqual([
    "uploadSample",
    "waitUntilSampleReady",
    "beginTransaction",
    "insertSample",
    "commitTransaction",
  ]);
});
```

- [ ] 实现 `InsertReceipt`，用于精确撤销：

```ts
export type InsertReceipt = {
  transactionId: string;
  createdEntityIds: string[];
  fragmentId: string;
  insertedAtSeconds: number;
};
```

- [ ] 上传音频时从现有受保护 route 获取 blob；不得把 Firebase token 写入公开 URL、日志或 Audiotool metadata。
- [ ] 插入位置默认 playhead，UI 在执行前显示目标位置。
- [ ] 插入按钮具备 pending/disabled 防重复状态；失败后给可重试错误。
- [ ] 每次 preview / insert / undo 都异步写 feedback；反馈失败不能阻止用户创作，但需本地排队重试。
- [ ] 运行离线测试：

```bash
npm test -- src/lib/audiotool/insert-fragment.test.ts
```

Expected: PASS。

- [ ] 在真实账号通过 write gate：同一段连续录屏里显示 Pocket Producer 选择、Audiotool 插入结果与撤销结果。
- [ ] Commit:

```bash
git add frontend/src/lib/audiotool frontend/src/components/audiotool
git commit -m "feat: insert and undo fragments through nexus"
```

### Task 8: 建立研究数据协议，而不是先训练

**Files:**

- Create: `research/protocol.md`
- Create: `research/annotation-schema.md`
- Create: `research/consent-template.md`
- Create: `research/fixtures/golden_pairs.jsonl`
- Create: `backend/tests/ranking/test_feedback_export.py`

- [ ] 在看结果前写死主要假设和指标：

```md
Primary hypothesis:
Session-conditioned ranking improves held-out pairwise continuation
preference prediction over the strongest simpler baseline.

Primary metric:
Pairwise accuracy and log loss, reported per participant.
nDCG@3 is secondary only if a separate 0–3 graded relevance task is collected.

Secondary:
top-1 acceptance, time-to-first-meaningful-edit, undo rate,
perceived relevance and perceived control (7-point Likert).

Failure criterion:
For the planned 3–8 participant formative study, report participant-level
descriptive effects and do not claim population-level significance.
A later confirmatory study requires an effect-size-informed design and
preregistered participant-clustered uncertainty analysis.
```

- [ ] annotation 单位定义为同一个 session 下的 pairwise 偏好：

```json
{
  "participant_hash": "p_...",
  "session_id": "s_...",
  "left_fragment_id": "f1",
  "right_fragment_id": "f2",
  "preference": "left",
  "reason_codes": ["tempo_fit", "supports_next_step"],
  "model_ids_hidden": true
}
```

- [ ] `golden_pairs.jsonl` 只放合成/自有/明确授权的元数据与 fixture id，不提交参与者音频。
- [ ] 写 export 测试：删除 token、邮箱、原始 project title，并将 user id 单向 hash。
- [ ] 招募目标 6–8 位音乐创作者，每人 3 个 session、每个 session 5–10 个 pair；若数量不足，明确标为 formative study，不夸大统计结论。
- [ ] Commit:

```bash
git add research backend/tests/ranking/test_feedback_export.py
git commit -m "docs: preregister pocketrank evaluation protocol"
```

### Task 9: 实现版本化表示、两阶段检索与 PocketRank-Context

**Files:**

- Create: `backend/ranking/representations.py`
- Create: `backend/ranking/session_graph.py`
- Create: `backend/ranking/retrieval.py`
- Create: `backend/ranking/fusion.py`
- Create: `backend/ranking/linear_ranker.py`
- Create: `backend/ranking/deepsets_ranker.py`
- Create: `backend/ranking/context_model.py`
- Modify: `backend/ranking/features.py`
- Create: `backend/tests/ranking/test_representations.py`
- Create: `backend/tests/ranking/test_session_graph.py`
- Create: `backend/tests/ranking/test_context_model.py`
- Create: `research/bakeoff_backbones.py`
- Create: `research/train_context_ranker.py`

- [ ] 完整执行前沿架构本的 Task A–E；不得跳过 credential rotation、表示血缘或 held-out gate。
- [ ] 将旧 `Fragment.embedding` 明确登记为 `representations.text["voyage-3"]`；不把它称为 audio embedding，也不向同一字段混写不同模型。
- [ ] 每个表示记录 `modality`、`model_id`、`revision`、`input_sha256`、`sample_rate`、`window_policy`、`pooling`、`created_at`。
- [ ] 先在 PocketBench 固定子集 bake off `MS-CLAP`、`LAION-CLAP Music`、`MusicFM-FMA`；MuQ、MERT、M2D-CLAP 仅在时间允许时作为研究 challengers。
- [ ] 用检索质量、CPU/GPU 时间、峰值内存、embedding bytes、license/provenance 一起决策，不按单一公开 benchmark 选模型。
- [ ] 从 Nexus entity 集合构造 `SessionGraph`，禁止假设 API 提供项目 mixdown；缺失声部表示必须显式 mask。
- [ ] 固定在线路径：

```text
versioned cached representations
  → per-space exact/ANN retrieval
  → Reciprocal Rank Fusion
  → validation-selected candidate K
  → PocketRank-Context rerank
  → constrained MMR Top-3
  → grounded reason codes
```

- [ ] 在同一 split 比较 L0 linear、L1 DeepSets、L2 `PocketRank-Context-450K`；foundation encoders 全冻结。450K 是 L2 参数预算，不是预定胜者；选择最简单且 held-out 表现稳定的模型。
- [ ] 弱监督预训练使用可追溯授权的同曲/同包关系；人工显式偏好使用 BPR，按 participant/song-source 分组切分，禁止来源泄漏：

```python
loss = -torch.nn.functional.logsigmoid(
    preferred_score - rejected_score
).mean()
```

- [ ] implicit events 只用于有曝光记录的 preview/insert/retained/undo 样本；没有 propensity/interleaving 证据时，不宣称无偏在线提升。
- [ ] 个性化先比较 no-history、mean-history、EMA-history；EMA decay 由 validation 选择。只有 temporal held-out learning curve 支持时才训练 per-user 参数，不使用任意事件数门槛。
- [ ] Top-3 用 constrained MMR 分成 `Best fit`、`Useful contrast`、`From your memory`；不得把三个近重复片段当作多样性。
- [ ] 保存 `model.safetensors`、`representation_schema.json`、`feature_schema.json`、`metrics.json`、`split_manifest.json`、`model_card.json`；不得 pickle 整个模型对象。
- [ ] 运行：

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest \
  tests/ranking/test_representations.py \
  tests/ranking/test_session_graph.py \
  tests/ranking/test_context_model.py -q
cd ..
python research/bakeoff_backbones.py \
  --manifest research/data/pocketbench.jsonl \
  --models msclap,laion-clap-music,musicfm-fma \
  --output artifacts/backbone-bakeoff.json
python research/train_context_ranker.py \
  --weak-data research/data/weak_pairs.jsonl \
  --preference-data research/data/pairs.jsonl \
  --output artifacts/pocketrank-context-v1 \
  --seed 20260725
```

Expected: 测试 PASS；所有 embedding finite 且可按 hash 命中缓存；参数统计不超过预算；同 seed 指标一致到允许误差。

- [ ] Commit:

```bash
git add backend/ranking backend/tests/ranking \
  research/bakeoff_backbones.py research/train_context_ranker.py
git commit -m "feat: add context-conditioned pocketrank pipeline"
```

### Task 10: 以基线为中心评估，不让模型成为比赛单点故障

**Files:**

- Create: `research/evaluate.py`
- Modify: `MODEL_CARD.md`
- Modify: `docs/letsbuild/judging-evidence.md`

- [ ] 先写指标单元测试：pairwise 数据验证 accuracy/log loss；独立 0–3 graded labels 才验证 nDCG@3；单一已知 positive 才验证 MRR。
- [ ] 固定比较：

```text
recency-v1             最近碎片
text-only-v1           现有 Voyage 文本向量
audio-cosine-v1        candidate/context 音频 cosine
mean-session-v1        active regions 均值上下文
rules-v1               可解释 session heuristics
pocketrank-context-v1  role-aware context reranker
```

- [ ] 评估命令：

```bash
python research/evaluate.py \
  --dataset research/data/heldout.jsonl \
  --models recency-v1,text-only-v1,audio-cosine-v1,mean-session-v1,rules-v1,pocketrank-context-v1 \
  --bootstrap 2000 \
  --seed 20260725 \
  --out artifacts/evaluation.json
```

Expected JSON:

```json
{
  "primary_metric": "ndcg@3",
  "grouping": "participant",
  "models": {},
  "pairwise_bootstrap_ci": {},
  "dataset_hash": "sha256:..."
}
```

- [ ] 决策门：

```text
若 manuscript freeze 前 PocketRank-Context 没有在 participant/song-source held-out split 上，以与标签类型匹配的指标超过最强基线：
1. 比赛默认仍使用 rules-v1；
2. LBD 的主张降级为系统、任务定义、benchmark/protocol 与 preliminary study；
3. PocketRank-Context 保留为诚实的 ongoing experiment；
4. README 不写 “AI model improves creativity”；
5. Demo 聚焦 Nexus 闭环、透明解释与可撤销控制。
```

- [ ] Commit:

```bash
git add research/evaluate.py MODEL_CARD.md docs/letsbuild/judging-evidence.md
git commit -m "research: benchmark continuation ranking methods"
```

### Task 11: 部署异步 embedding worker 与本地 CPU ranker

**Files:**

- Create: `model-service/app.py`
- Create: `model-service/Dockerfile`
- Create: `model-service/README.md`
- Modify: `backend/ranking/registry.py`
- Create: `backend/tests/ranking/test_remote_adapter.py`

- [ ] 先写 adapter contract test，使用假 HTTP server 覆盖成功、2 秒超时、500、错误 schema。
- [ ] 远程端点用于异步表示生成与研究复现；比赛同步 `/rank` 默认加载本地 ONNX 小模型。远程协议只暴露：

```text
GET  /health
GET  /model-card
POST /embed
```

- [ ] Model Card 必须可机器读取：

```json
{
  "id": "pocketrank-context-v1",
  "task": "session-conditioned fragment retrieval and ranking",
  "trainable_parameters": "measured-at-export",
  "representation_model": "selected-by-pocketbench-bakeoff",
  "representation_revision": "immutable-revision",
  "training_data": ["licensed weak pairs", "consented pairwise preferences"],
  "limitations": ["small formative preference sample", "not a music generator"]
}
```

- [ ] Docker 默认以非 root 用户运行，不把 secrets 写入 image：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY model-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY model-service/app.py .
USER 65532
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
```

- [ ] 后端对 remote 使用严格超时、schema validation 和 content hash；新 embedding 失败进入 visible pending 状态，不阻塞已缓存候选或本地 rules fallback。
- [ ] 本地运行：

```bash
docker build -f model-service/Dockerfile -t pocketrank-service .
docker run --read-only -p 7860:7860 pocketrank-service
curl --fail http://localhost:7860/health
```

Expected: HTTP 200；关闭容器后，已有缓存的完整 ranking 闭环仍可运行。

- [ ] 只有在不影响 Nexus 主闭环时才部署 Hugging Face Space；比赛演示前必须实测冷启动和 fallback。
- [ ] Commit:

```bash
git add model-service backend/ranking/registry.py backend/tests/ranking/test_remote_adapter.py
git commit -m "feat: add optional asynchronous embedding service"
```

### Task 12: 隐私、授权与故障恢复审计

**Files:**

- Create: `backend/tests/api/test_ranking_privacy.py`
- Modify: `ARCHITECTURE.md`
- Modify: `DATA_CREDITS.md`
- Modify: `frontend/src/lib/audiotool/client.ts`

- [ ] 自动测试日志和 Mongo 文档中不存在：

```text
access_token
refresh_token
Authorization
user email
raw Audiotool project document
```

- [ ] OAuth 权限说明写入 UI：为什么需要 `project:write`、何时使用、如何断开。
- [ ] 写失败矩阵：

```md
| Failure | User-visible behavior | Data safety |
|---|---|---|
| Nexus unavailable | reconnect action | no queued write |
| rank API timeout | rules fallback | session fingerprint only |
| sample upload fails | retry | no partial timeline entity |
| feedback API fails | local retry queue | no token persisted |
```

- [ ] `DATA_CREDITS.md` 列出每个 encoder、许可证、版本、模型主页、训练用途与音频来源。
- [ ] 运行：

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest tests/api/test_ranking_privacy.py -q
```

Expected: PASS。

- [ ] Commit:

```bash
git add backend/tests/api/test_ranking_privacy.py ARCHITECTURE.md DATA_CREDITS.md frontend/src/lib/audiotool/client.ts
git commit -m "security: document and test nexus data boundaries"
```

### Task 13: 真实用户研究与作品集结果

**Files:**

- Modify: `research/protocol.md`
- Create: `research/results.md`
- Modify: `MODEL_CARD.md`

- [ ] 先做 1 位 pilot，验证问题是否能理解、流程是否在 20 分钟内完成；pilot 数据不混入最终测试集。
- [ ] 对 6–8 位参与者执行同一脚本：

```text
2 min 介绍与同意
3 min 选择真实或示例 session
5 min 盲选 pairwise 候选
5 min 使用 Top-3 continuation
3 min CSI / 控制感量表
2 min 访谈：哪里帮助、哪里打断
```

- [ ] 记录 task completion、time-to-first-meaningful-edit、preview/insert/undo、nDCG@3 与定性主题。
- [ ] 结果页必须区分：

```text
Observed result
Participant quote (匿名且获同意)
Interpretation
Limitation
```

- [ ] 不使用显著性语言描述小样本；展示置信区间与所有失败案例。
- [ ] 更新 Model Card 的 intended use、out-of-scope、known limitations、伦理与隐私。
- [ ] Commit:

```bash
git add research/results.md research/protocol.md MODEL_CARD.md
git commit -m "research: report formative pocket producer study"
```

> **Let's Build Lane — Task 14–15:** 从同一个冻结版本提取比赛叙事与发布证据。

### Task 14: 比赛 Demo 与作品集叙事

**Files:**

- Create: `docs/letsbuild/demo-script.md`
- Create: `docs/letsbuild/submission-copy.md`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`

- [ ] Demo 固定为 2 分 30 秒，所有镜头证明一个主张：

```text
00:00–00:12  Hook：几十个碎片，但今晚不知道从哪继续
00:12–00:30  在 Audiotool 打开未完成 session
00:30–00:50  Pocket Producer 读取 tempo/track/context
00:50–01:20  Top 3 + “Why this now”
01:20–01:45  Preview → Insert → Audiotool 时间线出现
01:45–01:58  Undo，强调 human agency
01:58–02:18  rules / similarity / PocketRank 结果图
02:18–02:30  结尾：creative memory, not autopilot
```

- [ ] README 首屏顺序：

```text
一句话 + GIF
Try it / Watch demo
真实 Audiotool 闭环
Research question + 结果表
Architecture
Responsible design
Run locally
My contribution
```

- [ ] “My contribution” 明确列出 Nexus integration、ranking protocol、PocketRank、研究设计、前后端与部署；不要让旧 Gemini agent 抢占叙事。
- [ ] submission copy 针对目标类别：

```text
Primary: Songstarter / Composition
Secondary: Connect
Core proof: meaningful Nexus read + write, not a standalone recommendation mockup
```

- [ ] 所有截图使用同一个示例 session、同一组候选与同一视觉主题，避免像多个未完成原型。
- [ ] Commit:

```bash
git add README.md ARCHITECTURE.md docs/letsbuild
git commit -m "docs: package pocket producer letsbuild submission"
```

### Task 15: 最终验收、部署和应急演练

**Files:**

- Modify: `docs/letsbuild/judging-evidence.md`
- Create: `docs/letsbuild/release-checklist.md`

- [ ] 全量测试：

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -q
cd ../frontend
npm run check
npm run build
```

Expected: 全部退出码 0。

- [ ] 使用全新浏览器 profile 走完整验收：

```text
Connect Audiotool
Open project
See accurate fingerprint
Receive Top 3
Preview protected audio
Insert at visible playhead
Observe entity in Audiotool
Undo exact insertion
Disconnect
Verify no OAuth token in backend logs/database
```

- [ ] 模拟模型服务关闭，确认 2 秒内切换 `rules-v1`，UI 标注 fallback，主流程仍完成。
- [ ] 模拟空 fragment library，提供示例数据导入或明确空状态，不展示假推荐。
- [ ] 检查移动端、桌面端、Safari/Chrome、慢网、冷启动。
- [ ] 录制一镜到底的 evidence video，再剪正式 demo；保留未剪版本作为真实性证据。
- [ ] 对照官方当日 submission 表单逐项核对名称、链接、类别、团队信息、公开权限和截止时区。
- [ ] 最后提交时间设为 **2026-08-22**；2026-08-23 仅用于应急，不用于开发新功能。
- [ ] Commit:

```bash
git add docs/letsbuild/release-checklist.md docs/letsbuild/judging-evidence.md
git commit -m "chore: complete letsbuild release evidence"
```

## 5. 日期冲刺本

| 日期 | 唯一主目标 | 当日退出条件 |
|---|---|---|
| 07-25 | 冻结协议与范围 | 本计划、文件地图、比赛 gates 确认 |
| 07-26–07-29 | Nexus read | 真实工程 → 稳定 fingerprint |
| 07-30–08-03 | Nexus write | preview → insert → undo 连续通过 |
| 08-03 | MVP freeze | 无模型服务也可完整演示 |
| 08-04–08-06 | 数据协议与 baselines | rules/recency/embedding 可评估 |
| 08-07 | ISMIR manuscript freeze | 2+1 页完整、数字由脚本生成 |
| 08-08 | ISMIR internal review | originality、suitability、引用与格式通过 |
| 08-09 | ISMIR target submission | CMT、PDF、supplementary video 复核并提交 |
| 08-10–08-12 | PocketRank-Context | bakeoff、训练、保存、重载、固定 split |
| 08-13–08-15 | Pilot + 用户研究 | 至少 1 pilot，目标 6–8 participants |
| 08-16–08-18 | 研究结果与 UI polish | 结果表、限制、关键交互稳定 |
| 08-19–08-20 | Demo / README / submission | 2:30 成片与作品集首屏 |
| 08-21 | 全新环境演练 | 新账号/冷启动/断网降级通过 |
| 08-22 | 提交 | 所有公开链接用无痕窗口复核 |
| 08-23 | Emergency only | 不加入新功能 |

## 6. Kill Criteria：什么时候必须砍功能

1. **到 08-03 Nexus write 未稳定：** 立即停止模型训练和视觉扩展，全力完成真实写回。
2. **到 08-07 没有可审计的 audio representations：** LBD 不写 learned ranking improvement，只提交系统、任务与 protocol。
3. **到 08-10 数据不足 100 个有效 pair：** PocketRank-Context 只报告 weak-pretraining 或方法原型，不宣传个性化提升。
4. **到 08-12 PocketRank-Context 未超过最强基线：** 比赛默认使用 rules-v1，结果页诚实报告负结果。
5. **远程服务 p95 超过 2 秒或冷启动不可控：** 比赛环境关闭 remote adapter。
6. **任何自动生成解释无法追溯到特征：** 删除生成解释，改用 evidence labels。
7. **任何功能不能在 15 秒内向评委证明价值：** 从主 Demo 删除，移到未来工作。

## 7. 评审与申请材料的双重呈现

### Let's Build 评委看到

- 真正使用 Nexus，而不是在旁边运行的推荐网站。
- 一次完整、可撤销的音乐创作动作。
- 有趣且聚焦的使用场景：重新进入未完成作品。
- 模型不是装饰：它有明确任务、基线、指标和失败策略。
- demo 稳定，模型服务挂掉仍能完成。

### MIT / CCRMA 作品集审阅者看到

- 对 human-AI co-creation 的研究问题，而不只是产品功能。
- 将“相似”重新定义为“对下一步创作有用”的建模选择。
- 音频系统、交互系统、模型系统和实验设计的完整能力链。
- 对 agency、explanation、reversibility、privacy 的成熟判断。
- 诚实的消融、负结果和限制。

作品集摘要建议：

> I built Pocket Producer to study a narrow question: can a system use the state of an unfinished music session to retrieve memories that help a musician make the next move—without taking authorship away? The prototype connects directly to Audiotool through Nexus, ranks personal fragments by continuation utility, and makes every recommendation previewable, explainable, insertable, and reversible.

## 8. ISMIR 2026 Late-Breaking/Demo 双轨

> **ISMIR LBD Lane — Task 16–18:** 从同一个冻结版本提取科学主张、论文图表和演示材料。

### 官方约束与判断

依据 [ISMIR 2026 官方 LBD Call](https://ismir2026.ismir.net/call-for-late-breaking-demo)：

- 投稿入口于 **2026-07-31** 开放，官方截止为 **2026-09-25 AoE**。
- 采用滚动评审，最多 75 个 poster，满额会提前关闭。
- 被拒稿件不能修改后重投，因此目标不是“开门即投”，而是尽早交一份证据完整的版本。
- 投稿为不匿名的 **2+1 页**：最多两页科学内容，加一页仅放参考文献；最终 PDF 使用 2026 LBD 模板。
- 初投可附不超过 5 分钟、H.264、100MB、带 closed captions 的 demo video。
- LBD abstract 不进入正式 ISMIR 2026 proceedings。这适合展示 work-in-progress，也保留未来扩展为正式论文的空间。
- 接收后至少一名作者须注册并线上或线下参会；camera-ready、poster、thumbnail 和最终视频截止 **2026-10-16**。

结论：**两条线可以同时进行，而且比单独做比赛更强。** 但只能共享一个工程核心，不能维护两个版本。

| 共享资产 | Let's Build 解释 | ISMIR LBD 解释 |
|---|---|---|
| Nexus read/write | 有意义的平台集成 | 真实创作环境中的研究仪器 |
| Session Fingerprint | 更贴合当前工程 | session-conditioned representation |
| Top-3 ranking | 帮用户继续创作 | continuation utility retrieval task |
| Preview/insert/undo | 完整、好看的闭环 | agency-preserving intervention |
| Feedback events | 产品行为反馈 | implicit preference signals |
| Baseline evaluation | 证明 AI 不是装饰 | 初步 MIR empirical result |
| Demo video | 2:30 产品故事 | ≤5:00 方法、实验和局限 |

两条线必须分开的部分：

```text
Let's Build:
稳定性、Nexus 使用深度、视觉完成度、现场冲击力。

ISMIR LBD:
任务定义、相关工作、数据协议、基线、指标、限制与可复现性。
```

推荐 LBD 标题：

> **Re-entering Unfinished Music: Session-Conditioned Retrieval of Personal Audio Fragments with Reversible DAW Actions**

核心 scientific contribution 限制为三个，避免两页内过度承诺：

1. 将 personal fragment retrieval 定义为 **continuation utility ranking**，而不是通用相似度搜索。
2. 提出透明的 `SessionFingerprint` 与 session-conditioned baselines。
3. 在真实 DAW 工作流中实现 preview / insert / undo，并报告初步离线评估与 formative user evidence。

### Task 16: 先写 ISMIR claim skeleton，再收集证据

**Files:**

- Create: `docs/ismir2026/lbd.tex`
- Create: `docs/ismir2026/references.bib`
- Create: `docs/ismir2026/claim-evidence-ledger.md`
- Create: `docs/ismir2026/submission-checklist.md`

- [ ] 从官方仓库复制并固定 `ISMIR2026_lbd_template.tex`，不得用普通 conference paper 模板替代。
- [ ] 在 07-31 前建立两页结构，先写问题和评估设计，不预填胜利结果：

```tex
\section{Introduction}
\section{Pocket Producer}
\subsection{Session Fingerprint}
\subsection{Continuation Utility Ranking}
\subsection{Reversible Audiotool Interaction}
\section{Preliminary Evaluation}
\section{Discussion and Limitations}
```

- [ ] 为每个主张建立证据 ledger：

```md
| Claim ID | Manuscript claim | Required evidence | Status |
|---|---|---|---|
| C1 | session context improves ranking | graded labels: nDCG@3；pairwise labels: accuracy/log loss；participant-level uncertainty | pending |
| C2 | system operates in a real DAW | Nexus read/write capture | pending |
| C3 | interaction preserves agency | insert/undo logs + interviews | pending |
```

- [ ] 文献只允许来自已打开核验的 DOI、出版社页面或论文 PDF；每条 BibTeX 记录保存核验 URL。
- [ ] 根据 [ISMIR 2026 AI Usage Policy](https://ismir2026.ismir.net/ai-usage-policy) 建立 AI usage log：编程/语法辅助与影响 literature review、分析或方法的使用分别记录；所有作者对内容、图表和引用负责。
- [ ] 初次编译：

```bash
cd docs/ismir2026
latexmk -pdf -interaction=nonstopmode lbd.tex
pdfinfo lbd.pdf | rg "^Pages:"
```

Expected: 编译退出码 0，最多 3 页，第三页只有 references / acknowledgements / 合规 AI statement。

- [ ] Commit:

```bash
git add docs/ismir2026
git commit -m "docs: scaffold ismir 2026 late-breaking demo"
```

### Task 17: 让比赛日志直接生成 ISMIR 表格

**Files:**

- Modify: `research/evaluate.py`
- Create: `research/render_lbd_assets.py`
- Create: `research/tests/test_render_lbd_assets.py`
- Create: `docs/ismir2026/assets/.gitkeep`
- Modify: `docs/ismir2026/lbd.tex`

- [ ] 先写 deterministic asset test：相同 `evaluation.json` 必须生成字节稳定的 CSV 和固定维度图表。
- [ ] 只从 versioned evaluation artifact 生成论文资产：

```bash
python research/render_lbd_assets.py \
  --evaluation artifacts/evaluation.json \
  --study research/data/study-summary.json \
  --out docs/ismir2026/assets
```

Expected:

```text
docs/ismir2026/assets/ranking-results.csv
docs/ismir2026/assets/ranking-results.pdf
docs/ismir2026/assets/system-figure.pdf
docs/ismir2026/assets/dataset-facts.json
```

- [ ] 图表必须显示样本量、participant-level split、置信区间和 dataset hash；不允许从截图手工抄数。
- [ ] 用同一 evaluation artifact 更新 README 结果表和 LBD 表格，避免比赛页面与论文数字不一致。
- [ ] `system-figure.pdf` 只展示六步研究闭环：

```text
Audiotool session → fingerprint → retrieval → ranking
→ reversible action → preference feedback
```

- [ ] 编译并检查 overflow、字体嵌入、图中文字和两页科学内容限制。
- [ ] Commit:

```bash
git add research docs/ismir2026 README.md
git commit -m "research: generate reproducible ismir lbd evidence"
```

### Task 18: LBD 提交、视频与录取后材料

**Files:**

- Create: `docs/ismir2026/supplementary-video-script.md`
- Create: `docs/ismir2026/poster-outline.md`
- Modify: `docs/ismir2026/submission-checklist.md`
- Modify: `docs/ismir2026/lbd.tex`

- [ ] **2026-07-31 前**完成标题、两页结构、相关工作核验表和 claim-evidence ledger；结果位置只由脚本注入，不预写胜利结论。
- [ ] **2026-08-06 前**形成完整初稿：至少包含真实 Nexus read/write 证据、recency/rules/embedding 三个 baseline 和明确 limitation。
- [ ] **2026-08-07** 冻结 manuscript content；此后只允许修复事实、格式、可读性和合规问题。
- [ ] **2026-08-08** 完成一轮研究者/导师式内部审阅，重点检查 novelty、ISMIR suitability、引用真实性与主张强度。
- [ ] **目标 2026-08-09 投稿，2026-08-11 为绝对内部 deadline**；除非存在数据完整性、伦理或引用真实性问题，不等待 PocketRank、完整用户研究或 Let's Build 成片。
- [ ] 初投正文将尚未完成的 PocketRank 和用户研究明确写为 ongoing work，不把计划中的实验描述成结果。
- [ ] 初投使用已有连续录屏制作简洁 supplementary video；Let's Build 后再为 10-16 camera-ready 补录更完整的 method、baseline 和 limitations 版本。
- [ ] 初投视频验收：

```text
duration ≤ 5:00
codec = H.264
size ≤ 100 MB
closed captions present
no private project/user data
```

- [ ] PDF 验收：

```bash
pdfinfo lbd.pdf
pdffonts lbd.pdf
rg -n "T""ODO|T""BD|citation needed|result here" lbd.tex
```

Expected: 页面合规、字体嵌入、placeholder scan 无输出。

- [ ] 由作者逐条打开并核验所有引用；不能仅依靠引用管理器或 LLM 输出。
- [ ] CMT 提交前检查：非匿名、作者顺序、title/abstract 一致、PDF 正确、supplementary video 可播放。
- [ ] 接收后在 **2026-10-16** 前交付：

```text
camera-ready PDF
portrait poster ≤ A0 or 36 × 48 inches
thumbnail PNG ≤ 1920 × 1080 and ≤ 1 MB
final H.264 captioned video ≤ 5:00 and ≤ 350 MB
```

- [ ] 预留注册成本和参会责任：至少一名作者须注册并线上或线下展示；接受后再次核验 LBD 对应注册类别、speaker permit 和最新会议通知。
- [ ] Commit:

```bash
git add docs/ismir2026
git commit -m "docs: prepare ismir lbd submission package"
```

### 双轨资源分配

07-25 至 08-03：

```text
70%  Shared Trunk：Nexus MVP、真实写回、数据协议
20%  ISMIR：论文骨架、相关工作、claim ledger
10%  Let's Build：提交结构与 demo shot list
```

08-04 至 08-09：

```text
45%  Shared Trunk：baselines、评估、可靠性
45%  ISMIR：两页正文、图表、视频、投稿审计
10%  Let's Build：体验、部署、demo shot collection
```

08-10 至 08-22：

```text
35%  Shared Trunk：PocketRank、用户研究、bug fixes
60%  Let's Build：体验、demo、README、部署与提交
 5%  ISMIR：投稿状态、证据归档、camera-ready change log
```

关键原则：为了 ISMIR 增加的任何工程功能，若不能直接改善研究证据，不得在 08-22 前进入主分支。

## 9. Definition of Done

只有以下全部成立才叫完成：

- [ ] HARP 不在 dependency tree、runtime 或参赛部署中。
- [ ] Gemini / ADK 不在比赛关键路径中。
- [ ] Nexus 真实 read 和 write 均有自动测试与连续录屏证据。
- [ ] 用户可 preview、insert、undo。
- [ ] `rules-v1` 离线可用，remote 模型失败自动降级。
- [ ] 音频与文本 representations 分字段、带不可变模型 revision/input hash，且没有不同模态混写。
- [ ] tracked files、Git object/history、Docker context 和 submission archive 均完成 secret scan；只有发现暴露时才轮换凭据。
- [ ] 所有排序解释来自结构化 evidence。
- [ ] 至少比较 recency、text-only、audio-cosine、mean-session、rules 和 PocketRank-Context。
- [ ] 训练/测试按 participant 与 song/source group 隔离且能用固定 seed 重现。
- [ ] Model Card、Data Credits、研究协议、局限齐全。
- [ ] README 首屏能在 60 秒内说明问题、闭环、研究与个人贡献。
- [ ] 新浏览器 profile、冷启动、慢网和模型服务关闭均完成演练。
- [ ] 2026-08-22 前完成正式提交。
- [ ] ISMIR LBD 的每个主张都能映射到版本化数据、代码、录屏或明确 limitation。
- [ ] ISMIR PDF 符合 2+1 页、非匿名、官方模板和引用核验要求。
- [ ] 目标 2026-08-09、绝对内部截止 2026-08-11 完成 LBD 投稿。

## 10. 本计划自身的复核命令

```bash
rg -n "T""BD|TO""DO|implement la""ter|appropriate er""ror|add valida""tion|Write tests f""or" \
  docs/superpowers/plans/2026-07-25-pocket-producer-dual-track-sprint.md
```

Expected: 无输出。

```bash
rg -n "^### Task|^- \[ \]" \
  docs/superpowers/plans/2026-07-25-pocket-producer-dual-track-sprint.md
```

Expected: 18 个 task，且每个 task 都有可勾选的测试、实现、验证和提交步骤。
