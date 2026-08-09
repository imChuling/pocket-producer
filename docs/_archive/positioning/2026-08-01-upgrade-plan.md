# Pocket Producer 升级方案(2026-08-01,经代码审计修订)

依据:当前代码实况 + [五受众定位研究](2026-08-01-five-audience-strategy.md)中的证据。
每项标注**证据依据**(有文献/官方支持 vs 纯工程判断)与**服务受众**。

---

## 审计发现:三件比原方案任何一项都关键的事

### 🔴 阻塞级:`NEXT_PUBLIC_AUDIOTOOL_CLIENT_ID` 没有配置

`/audiotool` 页面的 OAuth clientId 读的是这个环境变量,当前**为空**。后果:

- Nexus 连不上 → **比赛两个硬门槛(read gate / write gate)都过不了**
- 拿不到连续录屏 → LBD 的 C2/C3 主张永远停在 `partial`
- demo 无法演示 → Let's Build 参赛资格实质不成立

**这是整个项目最硬的单点阻塞**,而解法只是去 developer.audiotool.com/applications 注册应用(约 15 分钟,只能由你做)。所有 Nexus 相关工作的价值都被这一项锁着。

### 🔴 README 还是六月黑客松版本

首屏写着 "Google Cloud Rapid Agent Hackathon 2026 · MongoDB Track"。这是**五个受众全部会看到的第一眼**,而它现在在自我介绍成另一个比赛的作品。零技术难度、最高杠杆。

### 🟡 MODEL_CARD.md 不存在

Definition of Done 明确要求,三所学校 + LBD 都会看模型卡。所有数字(400,225 参数、bake-off 结果、许可分类)都已在 artifact 里,只是没汇编成卡。

### 计划内但缺失的其余文件

`docs/letsbuild/{demo-script,submission-copy,release-checklist}.md`、`research/results.md`、
`backend/ranking/{slate,calibration}.py`、`model-service/app.py`、
`docs/ismir2026/{supplementary-video-script,poster-outline}.md`

---

## 优化决策:砍掉三项计划内的工作

原计划有些内容在当前证据下**已经不该做**,不是延后:

| 项目 | 原计划位置 | 砍掉理由 |
|---|---|---|
| `calibration.py` | Task F | 预注册协议明确规定**小样本不报 calibration**(ECE 在 N 小时不稳定)。做了也不能用。 |
| `model-service/`(远程 embedding worker) | Task 11 | 计划自己写明"比赛同步路径不依赖它";CLAP 本地 CPU 跑得动。八月做它=给自己加一个故障点。 |
| 清理六月遗留 lint/test 债(5 error + 2 failure) | Task 15 | **只要不宣称 "lint clean" 就不是阻塞**。已记录在 judging-evidence.md 的 Pre-existing failures。排到 polish 窗口,或干脆不做。 |

省下的时间全部投入下面的高杠杆项。

---

## 诊断:最弱的一环是"session-conditioned"本身

这是核心研究主张,但当前实现里它最薄:

| 声称 | 实际读到的 | 差距 |
|---|---|---|
| "系统以当前创作状态为条件" | tempo、轨道数/类型、playhead、用户输入的 intent | **完全没有读到工程里实际的声音** |
| `mean-session-v1` 基线 | 代码就绪,但 `region_audio_embeddings` 永远为空 → 永远降级 | 六基线里有一个从来跑不起来 |
| SessionGraph(架构文档) | 只实现了扁平的 SessionFingerprint | region/role/时间位置的结构化表示未落地 |

审稿人会直接问:"你说 session-conditioned,那你的 session 表示里有音乐内容吗?"目前的诚实回答是**没有**。这是 P0。

好消息:技术路径已核实可行——`audioRegion.fields.sample` → sample 实体的 `sampleName` → `at.samples.download(name, {format:"wav"})` 返回 Blob → CLAP 编码。

---

## P0-1:Session 音频条件化(最高优先级)

**证据依据**:核心研究主张的兑现;`mean-session-v1` 是预注册协议里列明的六基线之一。

**实现路径**:
```text
1. frontend/src/lib/audiotool/session-audio.ts
   查询 audioRegion → 解析 sample 指针 → samples.download() → 去重(按 sampleName)
   → 上传到后端 /api/ranking/session-embed(受保护路由)
2. backend: 复用 EmbeddingCache(按 sha256 幂等),CLAP 编码 → region_audio_embeddings
3. SessionFingerprint 填充该字段 → mean-session-v1 首次真正可运行
4. 缓存:同一 sample 在 session 内只编码一次;跨请求按 sampleName + revision 命中
```

**关键设计约束**(不能违背既有纪律):
- 音频只在用户**显式同意**后拉取(Nexus scope 已含 project:write,但读 sample 音频要单独告知)
- 编码失败 → 该 region 进 mask,**不伪造 embedding**(现有 mask 纪律)
- 编码是异步的:UI 显示 "reading your session…" 的 pending 态,rules-v1 在此期间照常工作

**工作量**:前端 ~1 天,后端 ~0.5 天(编码链路已存在)。

**服务受众**:全部五个。这是把"session-conditioned"从口号变成事实的唯一途径。

---

## P0-1b:OAuth 改用整页跳转,弃用弹窗流程

**证据依据**:2026-08-01 实测。在真实点击下做了对照实验:

| 测试 | 结果 |
|---|---|
| 复刻本项目完整异步调用链 → `window.open` | BLOCKED |
| onClick 内**完全同步**直接 `window.open` | **BLOCKED** |

第二项证明拦截是浏览器环境行为,与代码无关。用户需手动在
`chrome://settings/content/popups` 放行才能继续。

**这对比赛是不可接受的风险**:17+ 位评委第一次点 Connect 时会有相当比例
撞上弹窗拦截,而他们不会去改浏览器设置——直接判定"这东西跑不起来"。

**Nexus SDK 提供两条授权流程,我们一开始选错了:**

| 流程 | 官方定位 |
|---|---|
| `audiotoolPopup()` | 弹窗 + postMessage,**文档明说是给 iframe 内运行的应用用的** |
| `audiotool()` | 整页跳转,**不需要弹窗** |

Pocket Producer 是顶层页面、不在 iframe 里,本就该用后者。

**实现路径**:

```text
1. Audiotool 后台补注册 redirect URI:
     http://127.0.0.1:3000/audiotool
     https://<生产域名>/audiotool
2. client.ts 新增 createRedirectAuthorize()
     调 audiotool({clientId, redirectUrl, scope})
     未授权 → 调用 result.login() 触发整页跳转
3. /audiotool 页挂载时自动尝试一次授权
     回跳后 SDK 从 URL 参数完成流程 → 直接进 connected
4. 保留 createPopupAuthorize 作为 iframe 场景的备选,不删
5. 控制器契约不变 → 现有 11 个 client 测试全部继续适用
```

**注意**:`redirectUrl` 需与注册值精确匹配,所以要按页面路径注册,
不能只注册源。

**工作量**:约 0.5 天(含真实账号回归验证)。

**服务受众**:比赛(消除评委第一步就卡住的风险)、全部(演示稳定性)。

**排期**:read gate 用弹窗流程打通后立刻做,不晚于 08-10。

---

## P0-2:可调节的介入程度(evidence-driven)

**证据依据**[一手未核验但引用明确]:音乐人访谈研究直接表达要 **可滑动的 AI 介入连续谱**——"slide from AI takes over... versus AI takes little bits of it"。当前固定 Top-3 被该研究判定为**有证据支持但不完整**的设计。

**实现路径**(最小可行版本,不是做一堆滑块):
```text
三档介入强度,一个分段控件:
  Nudge    → Top-1,只推最保守的一个(高 tempo/key 契合度)
  Suggest  → Top-3(当前默认)
  Explore  → Top-6,MMR 多样性权重调高
```
后端只需把 `limit` 和 MMR 的 `lambda_similarity` 做成请求参数;前端一个三段控件。

**为什么这个版本够**:它把"连续谱"落成用户能理解的三个词,而不是暴露超参数。写进论文时是"我们把文献指出的 agency continuum 需求实现为三档离散强度,并在 limitation 里说明未验证连续控制是否更优"。

**工作量**:~0.5 天。

**服务受众**:LBD(直接回应文献缺口)、MIT/CCRMA(交互设计判断)、比赛(用户可控性)。

---

## P0-3:Top-3 slate 分化 + MMR

**证据依据**:架构文档已设计但未实现;AI Song Contest 研究显示团队"生成海量候选后事后策展",说明**候选间的差异化**比单纯排序更有用。

**实现路径**:
```text
backend/ranking/slate.py
  utility 排序 → constrained MMR 选 3 个
  三张卡贴固定标签:
    Best fit         最高 utility
    Useful contrast  在 role/spectral 上与 best fit 差异最大且 utility 仍在阈值内
    From your memory 来自最久未被使用的项目,带 provenance 证据
```
标签由**可计算规则**决定,不由 LLM 美化(既有纪律)。

**工作量**:~1 天(含测试)。

**服务受众**:比赛(demo 里三张卡各有性格,视觉说服力强)、LBD(diversity 是 slate 评估的既有维度)。

---

## P1-1:人工标注微调 + gate 判定

**证据依据**:预注册协议的核心;ICCC 2018 综述指出"提供人类判定的效用标签"正是共创评估的空缺。

**路径**:20 对 pilot → `export_pairs.py` → 在 FSLD 预训练的 L2 checkpoint 上 BPR 微调 → 按预注册 gate 判定 L2 是否上线。

**这一步不做,LBD 的第一条贡献就只能写成"我们提出协议"而非"我们执行了协议"。**

**依赖**:你标那 20 对(~15 分钟)。这是唯一无法工程化替代的一步。

---

## P1-2:steerability 控件

**证据依据**:AI Song Contest 论文给出的界面设计处方是 **decomposable / steerable / interpretable / adaptive** 四维度,这是可引用的自评 rubric。

**当前自评**:

| 维度 | 现状 | 缺口 |
|---|---|---|
| decomposable | 内部分解充分(检索/重排分离、容量梯子)但**对用户不可见** | 让用户看到"为什么进入候选池"和"为什么排第一"是两件事 |
| steerable | 只有自由文本 intent | **缺结构化约束**:role(我要 bass)、tempo 容差、排除某项目 |
| interpretable | 结构化证据码 ✅ 已达标 | — |
| adaptive | **完全没有** | 无个性化(设计上刻意,但要在论文里说明) |

**最小实现**:候选面板加两个 chip 过滤器——role(drums/bass/harmony/melody/fx)和"排除当前项目"。这两个都是硬过滤,不碰模型。

**工作量**:~0.5 天。

---

## P1-3:模型切换 + 证据展示

把 `audio-cosine-v1` 暴露到 UI(现在只有后端注册),卡片上显示 CLAP zero-shot 风格标签作为额外证据。demo 时可以现场切模型对比——这是"模型不是装饰"的最直观证明。

**工作量**:~0.5 天。

---

## P2:不在八月做,但要在论文里写清楚

- **adaptive/个性化**:预注册协议要求 temporal held-out learning curve 支持才启用,数据量远不够 → 写进 future work
- **连续 agency 控制**:三档是离散近似 → limitation
- **SessionGraph 完整形态**(role_source/confidence、onset grid、pitch class histogram)→ 当前扁平表示够用,完整版是正式论文的增量
- **Qwen-Omni captioner 对比**:post-LBD 的离线消融

---

## 排期(倒排三个死线)

| 日期 | 事项 | 门槛 |
|---|---|---|
| **08-02~03** | P0-1 session 音频条件化 | `mean-session-v1` 首次真跑通 |
| **08-02** | **P0-1b OAuth 改整页跳转** | 无需用户改浏览器设置即可授权 |
| 08-03 | P0-2 三档介入强度 | Nexus write gate 仍须先稳 |
| 08-04 | P0-3 slate 分化 + MMR | |
| 08-05 | P1-1 你标 20 对 → 微调 → gate 判定 | **决定 LBD 主张强度** |
| 08-06 | 论文初稿(含真实评估数字) | |
| **08-07** | manuscript freeze | |
| 08-08 | 内部审阅 + references 逐条核验 | |
| **08-09** | **ISMIR LBD 投稿** | |
| 08-10~15 | P1-2/P1-3 + 真实账号录屏 | |
| 08-16~21 | demo 成片、README、部署演练 | |
| **08-22** | **Let's Build 提交** | |
| 9~11 月 | 第二个作品集项目、音乐侧材料、教授对接 | MIT/CCRMA |
| **12-01** | **CMU 全部材料截止** | |

---

## 每项升级对五个受众的价值

| 升级 | Let's Build | ISMIR | MIT | CCRMA | CMU |
|---|:-:|:-:|:-:|:-:|:-:|
| P0-1 session 音频条件化 | ◎ | ◎ 兑现核心主张 | ◎ | ◎ | ◎ |
| P0-1b OAuth 整页跳转 | ◎ 评委不卡在第一步 | ○ 演示可复现 | ○ | ○ | ○ |
| P0-2 三档介入强度 | ◎ 用户可控 | ◎ 回应文献缺口 | ◎ 交互设计 | ◎ agency | ○ |
| P0-3 slate 分化 | ◎ demo 说服力 | ○ diversity | ○ | ◎ 设计判断 | ○ |
| P1-1 标注微调 + gate | ○ | ◎ 主张强度 | ◎ 科研成熟度 | ◎ project report | ◎ |
| P1-2 steerability | ○ | ◎ rubric 自评 | ◎ | ◎ | ○ |
| P1-3 模型切换 | ◎ 现场对比 | ○ | ○ | ○ | ◎ 工程深度 |

---

## 三条不变的纪律

1. **rules-v1 永远是保底**——任何升级都不能让 demo 依赖模型服务存活。
2. **缺数据就 mask,不伪造**——session 音频读不到就走降级,不填零向量。
3. **不宣称提升创造力**——共创评估文献明确指出短期实验无法支撑。

---

## 按性价比排序的最终执行顺序

杠杆 = 受众覆盖数 × 紧迫度 ÷ 工作量

| 序 | 事项 | 谁做 | 工作量 | 受众 | 为什么排这里 |
|---|---|---|---|:-:|---|
| ~~1~~ | ~~注册 Audiotool 应用拿 client ID~~ | 你 | — | 5 | ✅ 08-01 完成 |
| ~~2~~ | ~~README 重写(首屏)~~ | 我 | — | 5 | ✅ 08-01 完成 |
| **3** | **P0-1b OAuth 整页跳转** | 我 + 你补注册 URI | 0.5 天 | 5 | 当前弹窗流程要求用户改浏览器设置;评委不会做 |
| 4 | 标 20 对 pilot | **你** | 15 分钟 | 5 | 解锁 gate 判定,决定 LBD 主张强度 |
| 5 | P0-1 session 音频条件化 | 我 | 1.5 天 | 5 | 兑现核心主张;`mean-session-v1` 首次能跑 |
| 6 | MODEL_CARD.md | 我 | 0.5 天 | 4 | DoD 要求;数字全在 artifact 里,只需汇编 |
| 7 | P0-2 三档介入强度 | 我 | 0.5 天 | 4 | 回应文献指出的设计缺口 |
| 8 | P0-3 slate 分化 + MMR | 我 | 1 天 | 3 | demo 说服力 |
| 9 | demo-script + submission-copy | 我 | 0.5 天 | 2 | 比赛提交必需 |
| 10 | 真实账号连续录屏 | **你** | 30 分钟 | 5 | 依赖 #3 授权流程稳定 |
| — | ~~calibration / model-service / 清理旧债~~ | — | — | — | **已砍** |

**关键观察:#1/#2 已完成。当前最高杠杆是 #3——授权流程若要求评委改浏览器设置,
比赛第一步就会流失评委。**

## 我建议的下一步

先做 **P0-1b(OAuth 整页跳转)**。今天的实测已经证明弹窗流程要求用户手动
放行才能授权,这在评委手里就是"第一步就跑不起来"。

需要你配合的只有一步:在 Audiotool 后台补注册两个 redirect URI
(`http://127.0.0.1:3000/audiotool` 和生产域名对应路径),其余我来改。

之后接 P0-1(session 音频条件化)——那是兑现核心研究主张的那一项。
