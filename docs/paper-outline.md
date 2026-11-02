# 论文骨架：工具调用 Agent 评测中的「姿态-评测错配」

> 目标：Workshop / Short Paper（先投 arXiv + 评测/Agent 方向 workshop，再图正会）。
> 现状：**100 样本已设计并跑完**（optional 20 / must 53 / none 27，见 samples.py + tool_requirement.py + annotation.json）。
> **已跑 5 家族 21 模型 × 100 样本 × 3 trial（temp=0，2026-11-02）**，本节数字为真实值。
> （早期 30 样本三模型实验作为探索性先导，结果见 findings.md；温度 0.3 一致性实验仅在 30 样本上做过，未在 21 模型批次重跑。）

## 1. 候选标题（按锋芒排序）

1. **Posture–Grader Misalignment: Single Canonical Tool-Sequences Penalize Diverse Tool-Use Strategies in Agent Evaluation**
2. One Ground Truth, Three Strategies: How Process-Oriented Graders Underscore Capable Tool-Using Agents
3. 分桶 + 姿态感知：工具调用 Agent 评测中「标准动作」与「合理偏离」的错配（中文投稿备选）

## 2. 一句话贡献

> 现有工具调用 Agent 评测的 ground truth 只编码**一种标准工具序列**（correct_tools），
> 而真实模型表现出至少**三种工具使用姿态**：先追问（under-execute）、标准执行（exact）、过度探索（over-execute）。
> 21 模型 × 100 样本显示：过程型 Grader 对「多调工具的过度探索」系统性打低分——over 占比与
> (rule−LLM) 分差强负相关（r=−0.79），而「先追问」几乎不产生分差。
> 我们提出**工具依赖度标注（must/optional/none）+ 姿态感知评分**的修正框架；消融把 MiniMax-M3 的被放大差距从 0.145 收窄到 0.075（~48%）。

## 3. 核心发现（21 模型 × 100 样本 × 3 trial 验证）

| 发现 | 证据 |
|---|---|
| F1 姿态是模型级特征 | MiniMax-M3「过度探索」73%（其余 ≤20%）；Flash/Qwen3.8-Max「先追问」~27%；Qwen-Max/Qwen-Flash「标准执行」75-85% |
| F2 双 Grader 只中等一致 | rule 与 LLM 对 21 模型排序 Spearman=0.63；分歧集中在过度探索模型 |
| F3 差距放大由 over 驱动 | over% 与 (rule−LLM) 差 r=−0.79（bootstrap CI [−0.93, −0.02]）；rule 拉开 0.71–0.92（全距 0.20），LLM 挤在 0.84–0.92（全距 0.08）；消融把 MiniMax 差距 0.145→0.075 |
| F4 温度是烟雾弹 | （30 样本遗留）0→0.3 时 Pass@3 纹丝不动（0.533）、Pass^3 只挪 ≤0.01；姿态差远大于采样方差 |

## 4. 方法（可复现）

1. **合成医院导诊 Agent**：5 工具，100 样本 × 3 trial，温度 0（21 模型批次）。
2. **双 Grader**：rule-based 8 维（确定性，pytest 校验）+ LLM-as-Judge（交叉 provider）。
3. **姿态分类**：每 trial 相对 expected 序列分为 exact / under（零工具追问）/ over（多余工具）/ other。
4. **工具依赖度标注**：must（答案只在工具）/ optional（知识可内化）/ none（无需工具）。
5. **修正框架**：optional/none 桶关闭「工具选择/停止决策」的过程惩罚；must 桶保留但改为「结果正确性 + 是否调用必要工具」而非「精确序列」。

## 5. 实验设计

- 多模型对比：21 模型 × 8 维（rule vs LLM）+ 姿态分布 + over% 与 gap 的相关。
- 分桶（实验 B）：must/optional/none 三桶 × 关键维度。
- 消融：5 个 grader 变体（baseline / A结果型 / B分桶 / C姿态感知 / D放宽效率）收窄差距。
- （实验 A 一致性：温度 0 vs 0.3，仅 30 样本上做过，未在 21 模型批次重跑。）

## 6. 相关工作的差异定位

| 已有工作 | 关注点 | 我们的差异 |
|---|---|---|
| SABench（副作用） | 完成了但做错 | 我们看「合理偏离标准序列却被罚」 |
| Oracle audit | 评测器有 bug | 我们看「评测设计有系统性 bias（单一 ground truth）」 |
| Judge bias | judge 的 prompt/尺度偏差 | 我们看「ground truth 的粒度 + 姿态多样性」 |
| Pass@k / Pass^k（claw-eval） | 采样方差 | 我们证明「姿态 bias >> 采样方差」 |

## 7. 待补（正会门槛）

- [x] 模型数 5-6 → **已跑 5 家族 21 模型**（DeepSeek / MiniMax / Qwen / Kimi / GLM；qwen3-max 已下线改 qwen3.8-max），真实分数已完成（2026-11-02）
- [ ] 场景 2-3（医院 + 金融/客服 + 编码）
- [x] 样本 ≥100，optional 桶 20+（**已跑完**：100 样本，optional 20 / must 53 / none 27，2026-11-02）
- [x] 重跑 100 样本得新分数（2026-11-02 完成，21 模型 × 100 样本）
- [ ] 与 SABench / oracle-audit 的 head-to-head
- [ ] 开源评测集 + 姿态标注工具（可被他人复用，novelty 关键）
- [x] 统计显著性（Spearman 0.63 + over%-gap r=−0.79 bootstrap CI）

## 8. 诚实边界

- optional 桶已扩到 20 样本（H001-H003 + H031-H047），100 样本分数已重跑完成（2026-11-02）。
- v4-pro 同时当 Agent 和 Judge，存在自偏好偏差。
- 单场景合成数据，外部效度有限；mock 工具的日期参数脆弱性已修复并量化（over-explore 率 80%→78%，仅 −2pp，非 artifact）。

---

*下一阶段：填数字 → 写 Intro/Related Work 全文 → 扩到 5 模型 → arXiv 草稿。*
