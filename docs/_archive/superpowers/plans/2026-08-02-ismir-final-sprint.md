# ISMIR LBD 冲刺执行方案（8/3 – 8/9）

> 目标：8/9 投出 ISMIR 2026 LBD。在此之前完成审查修复 + 两个 MIR 元素（role-gap、和声兼容），
> 让论文从"检索系统 + 空协议"升级为"带 MIR 证据空间 + 初步人类数据"的 demo 论文。
> 节拍对齐插入（MIR-3）已裁掉。录屏/素材制作按惯例放到最后，不进本冲刺。
> Vercel 部署修复属于 8/22 Let's Build 轨道，不进本冲刺。

## 硬约束

- **8/9 = 提交日**。8/8 晚必须冻结 PDF。
- 预注册协议（frozen 2026-07-30）只约束人类评估的指标与分析，不禁止新增系统功能；
  role/harmony 作为**系统证据空间**加入合法，但**不得**进入已冻结的 primary metric 定义。
- 作者 pilot 标注必须与正式评估集隔离（论文已有此措辞，保持）。
- 论文中每个新数字必须由 render_lbd_assets.py 单向生成，禁止手填。

## 三条工作流

### A. 审查修复（论文可信度）
| ID | 任务 | 验收标准 | 估时 |
|----|------|---------|------|
| A1 | 2 秒 fallback 落地：`routes/ranking.py` 用线程池 + `asyncio.wait_for(2.0)`，超时降级 rules-v1；新增超时测试 | 测试证明慢 adapter 2s 内返回 rules 结果；论文句子从"假"变"真" | 3h |
| A2 | 多 seed + 置信区间：5 seeds × 3 模型重训；519 val pairs bootstrap 95% CI；weak-results 表改为 mean±sd | 表格含 CI；结论对 seed 稳健 | 4h（大半是等训练） |
| A3 | 优化混淆排除：DeepSets/PocketRank 上 lr ∈ {1e-3, 3e-4, 1e-4} × wd ∈ {0, 1e-4} + val early stopping | 网格内最优仍输 2 参数基线 → "benchmark rewards proximity" 成立；否则改写论文结论（也是有效结果） | 5h |
| A4 | 训练 provenance：metrics.json 记录完整 argv + git SHA + env | 重跑可精确复现 epochs=15 | 1h |
| A5 | 数字对齐：MODEL_CARD 0.880 vs 论文 0.879，统一由渲染脚本输出 | 全仓库同一数字 | 15m |
| A6 | `LadderRankerAdapter.__init__` 断言 `structured_dim == 0` | 未来 checkpoint 不会静默零填充 | 30m |

### B. MIR 元素（创新点 + 可展示性）
| ID | 任务 | 验收标准 | 估时 |
|----|------|---------|------|
| B1 | Role probe 接入 serving：复用 bake-off 的 instrument-role linear probe，对 session regions 和候选打 role 标签；新增证据码 `role_gap_fill`（"session 缺 bass，此候选是 bass，conf 0.87"） | 后端测试 + 真 checkpoint E2E；证据码带置信度 | 1.5d |
| B2 | 和声兼容打分：session 混音 vs 候选各算 chroma（librosa CQT-chroma），移调不变 cross-correlation；输出 fit 分数 + 最佳移调半音数；新增证据码 `harmonic_fit` | 单元测试（已知移调对照）；分数进 evidence | 1.5d |
| B3 | 前端证据 chips 渲染 role/harmony 两类新证据（含移调建议展示） | vitest 通过；截图可用于论文 fig | 0.5d |
| B4 | 论文 System 节改写：检索空间从 2 个（structured/CLAP）扩为 4 个（+role +harmony），RRF 融合不变；强调 role-gap 是 cosine 原理上无法捕捉的信号 → 与负结果叙事咬合 | lbd.tex 更新 + 重新编译 | 2h |

### C. 人类数据（命题成立性）
| ID | 任务 | 验收标准 | 估时 |
|----|------|---------|------|
| C1 | 【你】今天就发招募消息给 3–5 个音乐人（招募延迟是最长的杆，先启动） | ≥3 人答应 8/7 前完成 | 0.5h |
| C2 | 【你】/annotate 完成 ≥20 对作者 pilot 标注并导出 | export 文件存在 | 2-3h |
| C3 | 用 pilot 标注跑 `evaluate.py --ladder-dir`：全部预注册对比模型在真实人类标签上首次出分 | evaluation.json + 论文表格 | 2h |
| C4 | 关键图：人类偏好 vs CLAP-cosine 一致率（回答"这不就是 compatibility 吗"） | 一张图进论文或 supplementary | 2h |
| C5 | 若音乐人数据 8/7 前到：作为 formative 结果并入；否则论文仅报作者 pilot（已有隔离措辞） | — | 2h |

## 日程（假设高强度工作）

| 日期 | Claude 侧 | 你侧 |
|------|----------|------|
| **8/3 日** | A1 A4 A5 A6 完成并提交；A2/A3 训练脚本写好、网格挂机跑 | C1 发招募；C2 开始标注 |
| **8/4 一** | B1 role probe 后端接入 + 测试；A2/A3 结果收表 | C2 标注完成、导出 |
| **8/5 二** | B2 和声兼容模块 + 测试；C3 用你的标注跑真实评估 | 检查 C3 结果是否符合直觉 |
| **8/6 三** | B3 前端 chips；C4 一致率图；B4 论文 System 节改写 | 通读论文改写部分 |
| **8/7 四** | A2/A3 结果写进论文（CI 表 + 混淆排除段）；C5 并入音乐人数据（如有） | 通读全文 |
| **8/8 五** | 全文终审：资产再生、ledger 更新、确定性 PDF、提交材料核对 | 最终批准 |
| **8/9 六** | **提交** + 缓冲 | 提交确认 |

## 裁减线（如果落后）

1. 先砍 **B2 和声兼容**（降级为 8/22 demo 功能，论文不提）
2. 再砍 **A3** 网格到仅 lr 扫描（保留 early stopping）
3. **绝不砍**：A1（假声明必须消除）、A2（CI）、C2/C3（首个人类数据）、B1（核心创新叙事）

## 风险

- 音乐人招募不及 → 论文按现有措辞只报作者 pilot，不影响提交（C5 是加分项非阻塞项）
- 多 seed 后 headline 数字变化 → 表格自动再生，负结果叙事对两种走向都成立
- B1 的 role probe 在 session 混音（非孤立 loop）上精度下降 → 证据码带置信度阈值，低于阈值不出示；论文如实报告 probe 的训练域
- 测试全绿（后端 1 fail 1 error、前端 eslint）不在本冲刺内，8/10–8/22 处理；
  但 B1/B3 新增代码自身必须带测试且通过

## 8/9 之后的队列（不要提前做）

eslint 4 个真 bug → 测试全绿 → Vercel/OAuth 回调 → 节拍对齐插入（可选）→ demo 录屏 → Let's Build 提交（8/22）→ pilot 扩大 + 自己的音乐作品 + 项目页（12 月前）
