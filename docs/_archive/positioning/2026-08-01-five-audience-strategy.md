# Pocket Producer:一个项目,五个受众

生成于 2026-08-01,基于 deep-research 工作流(22 个一手来源,105 条抽取主张)。

## 证据分级(重要)

本次研究的对抗核验因会话额度中断,只有 25/105 条主张走完三票流程。所有条目按下列标签使用:

| 标签 | 含义 | 使用方式 |
|---|---|---|
| **[已核验]** | 三票对抗核验通过(3-0 或 2-1) | 可直接作为决策依据 |
| **[一手未核验]** | 从官方页面抽取并附原文引用,但核验票因限额未跑完 | 高度可信,**写进申请材料前请自己打开链接确认** |
| **[有争议]** | 核验票判定与抽取内容冲突 | 必须人工裁决,不得直接使用 |

---

## 一、MIT Music Technology and Computation (MASc)

### 硬性要求 [已核验]

- **作品集恰好两个项目**,至少一个是技术项目;技术项目的说明限 **500 字或 3 分钟视频**。
  来源:[musictech.mit.edu/mt_masc_degree](https://musictech.mit.edu/mt_masc_degree)
- **双重能力权重**:必须同时展示音乐与计算背景,并在其一有突出实力。原文:"Applicants need to have a firm background in both music and computation while also showing particular strength in one of these areas."
- **要求提出 2–3 个到 MIT 后想做的独立项目构想**——这意味着 Pocket Producer 的研究议程(continuation utility 评估、人工标注研究)可以作为**未来提案**呈现,而不只是过去的工作。

### 教授方向 [已核验]

- **Anna Huang**:音乐系与 EECS 联合聘任 → 该方向在制度上位于 music/CS 交叉处,而非纯工程或纯作曲。其研究议程为 "Human-AI partnerships in music-making through interaction-driven design"(2-1 票通过)——**以交互设计为核心的人机音乐协作**,而非最大化生成模型质量。Pocket Producer 的 session 条件化交互闭环(预听/插入/精确撤销)直接落在这条线上。
- **Eran Egozy**:方向明确包含 "interactive music systems, music information retrieval, and multimodal musical expression and engagement"——正好是本项目的两个类别。

### [有争议] 需你自己确认

- "Egozy 是 MTC 项目创始主任、Professor of the Practice" 这条被核验票 0-3 否掉,但抓取时附有 mta.mit.edu 的直接引用。**写进申请信前请自己打开 [mta.mit.edu/person/eran-egozy](https://mta.mit.edu/person/eran-egozy) 核实头衔**,不要用我这份材料的转述。
- "Huang 明确以'让音乐人引导和纠正生成系统的界面'为目标"也被 0-3 否掉——她的公开表述是更宽的 "interaction-driven design",不要替她加戏。

### [一手未核验]

- Egozy 自己的作品是**部署级、面向真实听众的交互系统**(12、Tutti、ConcertCue),而非只跑 benchmark 的研究;ConcertCue 拿过 Knight Foundation 资助。
- MTC 是 2024 秋启动的一年制 SHASS×工程学院联合学位,2026-27 一届据报道 100+ 申请录 10 人。
- 学生论文项目是"有音乐使用理由的可运行技术系统"(EEG 转音符辅助残障音乐人、实时音乐可视化、动作转音乐、印度斯坦即兴生成),不是纯 ML benchmark 论文。

### 本项目已具备 vs 欠缺

| 已具备 | 欠缺 |
|---|---|
| 真实 DAW 集成的可运行系统(Nexus SDK) | **第二个作品集项目**——MIT 要恰好两个,目前只有一个 |
| 计算侧证据充分(表示层、容量梯子、评估协议) | **音乐侧证据薄弱**——需要你自己的音乐实践材料(作品、演奏、制作) |
| 可作为"独立项目构想"的清晰研究议程 | 外部验证(资助/奖项/录用),Egozy 的 ConcertCue 有 Knight 资助作对照 |
| 500 字压缩:诚实的负结果反而好写 | |

---

## 二、Stanford CCRMA (MA/MST)

### [一手未核验] 全部需自行确认,但含直接引用

- **明确邀请提交 project reports 或 published papers 作为作品集材料**:"All applicants to the MA/MST program are encouraged to submit project reports or published papers demonstrating their commitment to and achievements in the domains spanned by CCRMA courses."
  → **这是本次研究最重要的发现之一:ISMIR LBD 论文和预注册评估协议直接就是 CCRMA 的申请材料,不是副产品。**
- 评价标准是"在 CCRMA 课程涵盖领域的持续投入与成就"——**倾向一以贯之的作品线,而非单个精致 demo**。
- 领域跨度明确包含 **human-computer interaction、music perception、psychoacoustics**,不只是 ML/IR → 用人类 pairwise 判断评估的检索系统正落在多个领域内。
- **GRE 可选** → 作品集与陈述的相对权重上升。
- 两年 45 学分课程型学位;**CCRMA 与音乐系对 MA/MST 无常规资助**(这是与 MIT/CMU 的实质差异,影响你三校排序)。
- 官方要求申请者主动联系兴趣匹配的教授。

### Ge Wang 这条线 [一手未核验]

- 现在开设课程 **"Music and AI"** → CCRMA 有具体的对接点。
- 作品线极度 artifact-centered:ChucK 语言、Stanford Laptop Orchestra、Smule 联合创始、Ocarina/Magic Piano,CCRMA VR Design Lab 创始主任。
- 《Artful Design》核心命题:**"What we make, makes us"**——工具反过来塑造使用者;设计应由价值驱动而非仅由实用需求驱动。
  → 对 Pocket Producer 是天然钩子:一个决定"下一步给你看什么"的系统,就是在塑造创作路径。这正是 agency/reversibility 设计该被讲述的语言。
- 那本书本身做成全彩摄影漫画 → **交付物的形式本身就是论证**。CCRMA 作品集的呈现媒介需要被认真设计,不能只是 GitHub 链接。

### 本项目已具备 vs 欠缺

| 已具备 | 欠缺 |
|---|---|
| 可直接提交的 project report(预注册协议 + 评估 artifact) | 呈现媒介的设计(CCRMA 尤其吃这一套) |
| HCI + 音频表示 + 人类判断评估的组合正中领域跨度 | 教授对接邮件(官方明确要求) |
| 可逆性/agency 的设计判断,可用 Artful Design 的语言表述 | "持续作品线"叙事——需要把 6 月版本→审计→7 月重构讲成一条演进线 |

---

## 三、CMU Music and Technology (MS)

### [一手未核验]

- 作品集**接受软件清单、软件截图、网页**作为提交материал(与音频/视频并列)→ Pocket Producer 的代码、UI 截图、demo 网页直接可用。
- 格式要求:音频 .wav/.aiff/.mp3、视频 .mov/.mp4、文档 .pdf/.htm、图像 .jpg/.tif/.png,合集用 ZIP;**必须是原创作品**。
- 要求一份**简短摘要声明主攻方向**(工程 / 计算机科学 / 音乐表演三选一),外加所学编程语言与所奏乐器清单 → 需要一个明确的自我定位,不能三头下注。
- **650 字个人陈述**,涵盖音乐训练、为何申请 CMU、学术与音乐目标。
- 作品集面试**不需要准备材料**,谈的是创作过程、背景与未来目标 → 奖励的是能把设计推理讲清楚的排练过的叙事,而非幻灯片。
- **时间线最紧:12 月 1 日所有材料截止**,推荐信至 1 月 5 日,1 月教授评审,3 月 15 日出结果。

### 本项目已具备 vs 欠缺

| 已具备 | 欠缺 |
|---|---|
| 软件/截图/网页三种形态全都现成 | 12/1 硬截止——比多数人以为的早,作品集冻结日要倒排 |
| 设计推理链条完整(适合无材料面试) | 主攻方向的单一声明(建议:计算机科学,音乐为应用领域) |
| | 乐器/音乐训练清单 |

---

## 四、ISMIR 2026 Late-Breaking/Demo

### 筛选机制 [一手未核验,多来源交叉一致]

- **只筛三项:suitability(与 ISMIR 社区的契合)、originality、formatting**——**不筛结果完整性**。
- 明确欢迎未成熟工作:"prototype systems, initial concepts, and early results which have not yet fully matured"。
- **非存档**,不进正式论文集 → 不影响日后把同一工作扩成正式论文投稿。
- 2 页正文 + 1 页纯参考文献;可选 demo 视频 ≤5 分钟、mp4/H.264、≤100MB、带字幕。

### 关键先例:负结果是资产,不是负担 [一手未核验]

- **ISMIR 2019 有已录用 LBD 摘要报告了"更简单的基线在某个 regime 下打败了所提出的模型"**:"Interestingly, we also find that the time-based approach TIME_u provides even better accuracy results than BLL_u when..."
  → 我们的"2 参数 cosine 在弱标签上胜过 400K 模型"完全有先例,而且它恰好论证了核心主张:**相似 ≠ 有用,必须靠人工标注检验**。
- ISMIR 2022 约 50 篇 LBD 中大量是交互工具与创作支持系统,而非刷榜模型:Midi-Draw、Calliope(生成音乐共创在线界面)、Song Describer(文本描述采集平台)。
  → **human-AI co-creation 已是 ISMIR LBD 的成熟体裁**,不需要额外论证其正当性。
- **数据集与标注平台本身就是被认可的 LBD 贡献** → 你的 9,493 条逐条许可核验的 FSLD manifest + 盲选标注协议,可以独立成为贡献点。
- ISMIR 2025 的已录用例子里,有摘要**主动声明自身范围有限**("This is by no means a sustainable attempt...")——诚实框定不仅被容忍,而且被奖励。

### 写作定位建议

三条贡献,按可辩护性排序:

1. **任务定义**:把个人碎片检索重构为 continuation utility ranking(而非通用相似度搜索)。
2. **系统**:真实 DAW 内的 session 条件化检索 + 可逆写回(预听/插入/精确撤销)。
3. **协议与语料**:预注册评估协议 + 逐条许可核验的弱监督语料 + 盲选标注流程。

**模型结果放在"初步发现"位置**,用 ISMIR 2019 的先例语气写负结果:弱标签上简单基线胜出,恰恰说明弱标签测的是相似而非效用。

---

## 五、Audiotool Let's Build 2026

### 赛制事实 [一手未核验]

- 截止 **2026-08-23**,全球开放、免费参赛,**$70,000+ 总奖池**(含 $6,000 现金池),合作方包括 OpenAI、ElevenLabs 等。
- 必须基于 **Audiotool Nexus** 构建(官方定位:"the open source multiplayer music protocol connecting apps, AI and creators")→ 用官方 SDK 读实时工程状态正中靶心。
- 四个类别:**Creation / Games / Listening / Education**,可投多个 → Creation 为主,Listening 为辅。
- **评委学术权重高:17+ 位评委来自 Berklee、NYU、Munich Music Labs、BBC R&D**,外加艺术家与制作人。
  → **这条推翻了"比赛只看炫酷 demo"的默认假设**:研究严谨性对这个评审团是可读的、加分的。你的评估表和诚实负结果不用藏起来。
- 官方落地页**没有公开评分细则**,完整规则在独立的 Notion FAQ → **待办:找到并逐条核对该 FAQ**。

### 来自 HCI 研究的叙事校准 [一手未核验]

- 从业音乐人明确希望共创 AI **嵌入现有 DAW 而非独立应用** → 直接验证本项目的架构选择。
- 音乐人**拒绝"AI 作为协作者"的框架**,更接受"AI 是我控制下的工具":"AI shouldn't be a collaborator…it's more of a tool."
  → **叙事修正:不要说"AI 协作者",要说"你控制的检索乐器"。**
- 音乐人重视产出**可继续加工的片段而非完整成品**("moments instead of the whole")→ continuation utility 比"生成完整段落"更贴合真实需求。
- 音乐人想要**可调节的 AI 介入程度连续谱**("slide from AI takes over... versus AI takes little bits of it")→ 固定的 Top-3 是有证据支持但不完整的设计,**这是一个可写进 limitation 与 future work 的真实缺口**。
- AI Song Contest 研究(13 队 61 人):团队普遍**生成海量候选再事后筛选** → post-hoc 策展/排序是有文献记录的真实工作流,本项目直击该痛点;该文给出的界面设计处方是 **decomposable、steerable、interpretable、adaptive**——可作为自评 rubric。
- 共创系统评估综述(Karimi, Grace, Maher & Davis, ICCC 2018)明确把 **"utility"(系统贡献有用内容的能力)列为标准共创指标**,并批评现有共创系统"压倒性地只评估用户体验而非创造力"。
  → **"continuation utility" 不是自造词,它接的是共创评估文献的正统术语。** 而"提供人类判定的效用标签"正是该综述指出的空缺。

---

## 六、统一策略:一个内核,五种呈现

### 复用矩阵

| 已有产出 | Let's Build | ISMIR LBD | MIT | CCRMA | CMU |
|---|:-:|:-:|:-:|:-:|:-:|
| Nexus 实时读写 + 可逆插入(录屏) | ◎ 核心 | ◎ 系统贡献 | ◎ 技术项目 | ◎ artifact | ◎ 软件+视频 |
| 评估 artifact(evaluation.json + 图表) | ○ 证明非装饰 | ◎ 初步发现 | ○ | ◎ project report | ○ |
| 容量梯子 + 400K 参数实测 | — | ◎ 方法 | ◎ 计算实力 | ○ | ◎ 工程深度 |
| FSLD 逐条许可 manifest(9,493) | ○ 负责任 AI | ◎ 可独立成贡献 | ○ | ◎ 持续投入证据 | ○ |
| 预注册协议 + 盲选标注 | — | ◎ 协议贡献 | ◎ 独立项目提案 | ◎ 直接提交 | ○ |
| 诚实负结果 | ○ 可信度 | ◎ 有先例 | ◎ 科研成熟度 | ◎ | ◎ 面试素材 |
| ≤5 分钟 demo 视频 | ◎ 2:30 版 | ◎ 5:00 版 | ◎ 3:00 版 | ◎ | ◎ |

◎ 直接复用为核心材料 ○ 作为支撑 — 不适用

### 一句话内核(五个受众共用)

> Pocket Producer 把音乐人自己的未完成碎片,按"对下一步创作是否有用"排序,推到他们正在编辑的真实工程里——可预听、可解释、可撤销。

五种口径的差异只在**强调什么**:

- **Let's Build**:平台原生 + 完整可撤销动作 + 稳定性("模型服务挂了也能演示")
- **ISMIR**:任务定义 + 评估协议 + 诚实的初步发现
- **MIT**:双重能力(音乐判断驱动的计算选择)+ 未来独立项目提案
- **CCRMA**:价值驱动的设计判断(agency/reversibility)+ 持续作品线 + 呈现媒介本身的设计
- **CMU**:工程深度 + 能讲清楚的设计推理(为无材料面试准备)

### 必须补做的(按截止日倒排)

| 何时 | 事项 | 服务对象 |
|---|---|---|
| 即刻 | 找到并核对 Let's Build 的 Notion FAQ 完整规则 | 比赛 |
| 8/09 前 | pilot 20 对标注 → P3/P4 终裁 | LBD、全部 |
| 8/09 前 | references.bib 逐条人工核验(现全为 PENDING) | LBD |
| 8/22 前 | 真实账号 read/write 连续录屏 | 比赛、全部 |
| 8/22 前 | 把"可调节 AI 介入程度"写进 limitation/future work | LBD、MIT |
| 9 月 | **第二个作品集项目**(MIT 要恰好两个) | MIT |
| 9 月 | 音乐侧材料(作品/演奏/制作证据) | MIT、CMU |
| 10 月 | 教授对接邮件(CCRMA 官方要求;MIT 可选) | CCRMA |
| 11 月 | 呈现媒介设计(不只是 GitHub 链接) | CCRMA |
| **12/01** | **CMU 全部材料截止(最早的硬门)** | CMU |

### 三条叙事纪律

1. **说"工具"不说"协作者"**——有音乐人访谈证据支持。
2. **负结果照实写**——ISMIR 有先例,而且它论证了核心主张。
3. **不宣称提升创造力**——共创评估文献明确指出短期实验无法支撑该结论。

---

## 本文档的局限

- 25/105 条主张完成对抗核验,其余为一手来源抽取但未核验。
- ISMIR/比赛/HCI 三块**全部未走核验流程**——虽然来源是官方页面与同行评审论文且附原文引用,写进正式材料前应自行打开链接确认。
- 两条关于 MIT 教授的主张被核验票否决,已标为有争议,**必须人工裁决**。
- 额度恢复后可续跑:`Workflow({scriptPath: ".../deep-research-wf_08f5b3ed-068.js", resumeFromRunId: "wf_08f5b3ed-068"})`,已完成部分从缓存回放。
