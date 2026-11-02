# 论文骨架：工具调用 Agent 评测中的「姿态-评测错配」

> 目标：Workshop / Short Paper（先投 arXiv + 评测/Agent 方向 workshop，再图正会）。
> 现状：**100 样本已设计**（optional 20 / must 53 / none 27，见 samples.py + tool_requirement.py + annotation.json），
> 但仅前 30 条有三模型真实分数（flash、v4-pro、MiniMax-M3 × 温度 0/0.3）。
> 模型注册已扩到 **5 家族 22 模型**（DeepSeek / MiniMax / Qwen / Kimi / GLM，见 providers.py），
> **已充值，2026-11-02 起正在重跑 22 模型 × 100 样本**；重跑完成后本节数字整体更新。
> 现有分数足以支撑 workshop paper；正会需重跑 100 样本 + 多模型 × 2-3 场景。

## 1. 候选标题（按锋芒排序）

1. **Posture–Grader Misalignment: Single Canonical Tool-Sequences Penalize Diverse Tool-Use Strategies in Agent Evaluation**
2. One Ground Truth, Three Strategies: How Process-Oriented Graders Underscore Capable Tool-Using Agents
3. 分桶 + 姿态感知：工具调用 Agent 评测中「标准动作」与「合理偏离」的错配（中文投稿备选）

## 2. 一句话贡献

> 现有工具调用 Agent 评测的 ground truth 只编码**一种标准工具序列**（correct_tools），
> 而真实模型表现出至少**三种工具使用姿态**：先追问（under-execute）、标准执行（exact）、过度探索（over-execute）。
> 过程型 Grader（精确序列匹配）把偏离标准的前者与后者一律打低分，导致「模型得分被离标准姿态的距离系统性扭曲」。
> 我们提出**工具依赖度标注（must/optional/none）+ 姿态感知评分**的修正框架；消融显示它能把被放大的差距收窄 ~56%。

## 3. 核心发现（已用三模型 × 90 trial 验证）

| 发现 | 证据 |
|---|---|
| F1 三种工具姿态并存 | flash/v4-pro「先追问」占主导（must 桶零工具追问普遍），MiniMax-M3「过度探索」（极端 13 工具/无结论） |
| F2 双 Grader 系统性分歧 | rule vs LLM 在「工具选择」0.47 vs 0.85、「停止决策」0.57 vs 0.94（flash） |
| F3 差距放大（gap inflation） | MiniMax-M3 有真实结果短板（intent .37 / grounded .60）；rule 造出显著差 −0.19，而 LLM 判定无显著差（+0.03），全修复后回落 0.110 |
| F4 温度是烟雾弹 | 0→0.3 时 Pass@3 纹丝不动（0.533）、Pass^3 只挪 ≤0.01；姿态差（0.13 vs 0.47）远大于采样方差 |

## 4. 方法（可复现）

1. **合成医院导诊 Agent**：5 工具，30 样本 × 3 trial，温度 0/0.3。
2. **双 Grader**：rule-based 8 维（确定性，pytest 校验）+ LLM-as-Judge（交叉 provider）。
3. **姿态分类**：每 trial 相对 expected 序列分为 exact / under（零工具追问）/ over（多余工具）/ other。
4. **工具依赖度标注**：must（答案只在工具）/ optional（知识可内化）/ none（无需工具）。
5. **修正框架**：optional/none 桶关闭「工具选择/停止决策」的过程惩罚；must 桶保留但改为「结果正确性 + 是否调用必要工具」而非「精确序列」。

## 5. 实验设计

- 实验 A（一致性）：温度 0 vs 0.3，单次/Pass@3/Pass^3。
- 实验 B（分桶）：must/optional/none 三桶 × 关键维度。
- 姿态分析：under/over/exact 分布 + 极端案例（MiniMax 13 工具）。

## 6. 相关工作的差异定位

| 已有工作 | 关注点 | 我们的差异 |
|---|---|---|
| SABench（副作用） | 完成了但做错 | 我们看「合理偏离标准序列却被罚」 |
| Oracle audit | 评测器有 bug | 我们看「评测设计有系统性 bias（单一 ground truth）」 |
| Judge bias | judge 的 prompt/尺度偏差 | 我们看「ground truth 的粒度 + 姿态多样性」 |
| Pass@k / Pass^k（claw-eval） | 采样方差 | 我们证明「姿态 bias >> 采样方差」 |

## 7. 待补（正会门槛）

- [ ] 模型数 5-6 → **代码已登记 5 家族 22 模型**（DeepSeek / MiniMax / Qwen / Kimi / GLM；qwen3-max 已下线改 qwen3.8-max），真实分数正在重跑（2026-11-02）
- [ ] 场景 2-3（医院 + 金融/客服 + 编码）
- [x] 样本 ≥100，optional 桶 20+（**设计完成**：100 样本，optional 20 / must 53 / none 27，2026-11-02）
- [ ] 重跑 100 样本得新分数（2026-11-02 已启动，与 #17 扩模型一并跑）
- [ ] 与 SABench / oracle-audit 的 head-to-head
- [ ] 开源评测集 + 姿态标注工具（可被他人复用，novelty 关键）
- [ ] 统计显著性（bootstrap / McNemar）

## 8. 诚实边界

- optional 桶已扩到 20 样本（H001-H003 + H031-H047），后 70 条的新分数正在重跑（2026-11-02）——现有分桶结论仍基于前 30 条。
- v4-pro 同时当 Agent 和 Judge，存在自偏好偏差。
- 单场景合成数据，外部效度有限；mock 工具的日期参数脆弱性已修复并量化（over-explore 率 80%→78%，仅 −2pp，非 artifact）。

---

*下一阶段：填数字 → 写 Intro/Related Work 全文 → 扩到 5 模型 → arXiv 草稿。*
