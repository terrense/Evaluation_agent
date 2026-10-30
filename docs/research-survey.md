# 论文调研：Agent 评测与 LLM-as-a-Judge 研究全景（2026）

> 调研方法：arXiv API（export.arxiv.org）按提交时间倒序检索，覆盖 2026 年 6-10 月。
> 检索词：LLM-as-a-Judge / tool-use evaluation / agent benchmark / reward hacking / judge bias。
> 目的：定位我们三个实验发现的学术坐标，找可发表的切入点。

## 1. 四个热点方向

### 1.1 LLM-as-a-Judge 可靠性/偏差（最火，15+ 篇）

| 日期 | 论文 | 核心 |
|---|---|---|
| 2026-10-27 | Prompt Lottery in LLM-as-a-Judge | judge 对语法改写的敏感性 |
| 2026-10-22 | Prompting Strategy Effects Depend on the Judge | judge 依赖 prompt 策略 |
| 2026-10-16 | The Judge Can Debias Itself | judge 自我去偏 |
| 2026-10-13 | A CaLLM Judge is a Better Judge | 缓解 judge 偏差 |
| 2026-10-12 | StableJudge | 轻量对抗防御 |
| 2026-10-05 | JudgeMoE: Distributional Aggregation | 分布聚合 |
| 2026-10-04 | How Much Do LLM-as-a-Judge Design Choices Matter? | 设计选择系统对比 |
| 2026-10-02 | Evaluating LLM-as-a-Judge Beyond Score Alignment | 心理测量学分析 |
| 2026-09-30 | Can We Trust This Evaluation? Instance-Level Reliability | 实例级可靠性 |
| 2026-09-29 | Pair Difficulty Matters | 成对评测一致性 |
| 2026-09-02 | LLM-as-a-Judge Is Not an Oracle: Why Self-Improving Agents Need Deterministic Guardrails | **judge 不是 oracle，需确定性护栏** |

**结论**：LLM-as-a-Judge 的**可靠性、偏差、一致性**是 2026 年最密集的研究方向，且正从「评分对齐」转向「实例级可靠性 / 心理测量 / 去偏」。

### 1.2 工具调用 Agent 评测（8+ 篇，直接关联我们）

| 日期 | 论文 | 核心 |
|---|---|---|
| 2026-10-29 | Prefix Executability: Evaluating Tool-Using Agents Beyond Final Success | 超越最终成功（过程可执行性） |
| 2026-10-25 | Task Success Is Not Enough: Side-effect-Aware Evaluation | **任务成功不够，漏掉「附带损害」** |
| 2026-10-21 | VeriEvolve: Evaluator-First Evolution | 评测器优先进化 |
| 2026-10-10 | What Counts as the Same Task? Executable Contracts | 任务等价性的可执行契约 |
| 2026-10-08 | SSCBench: Fault-Injection Test Validity | 故障注入测试的证据有效性 |
| 2026-09-30 | TauIndianBankBench: Procedure-Aware, Action-Oriented | 过程感知评测 |

**结论**：工具 Agent 评测正从「最终成功」转向「过程 / 副作用 / 契约」——与我们的「outcome-only 高估」「ground truth 粒度」发现同频。

### 1.3 Agent Benchmark 可靠性审计（8+ 篇）

| 日期 | 论文 | 核心 |
|---|---|---|
| 2026-10-22 | What the Specification Did Not Say: Specification-Oracle Gaps | 规格-oracle 差距 |
| 2026-10-12 | When Agent Evaluation Becomes Unreliable: Oracle Failures and Configuration-Dependent Measurement | **把评测 harness 当软件审计 oracle 缺陷** |
| 2026-09-29 | Do Agent Benchmarks Do What They Say? Executable-Contract Audit | **工具契约审计** |
| 2026-09-29 | UserProxyBench: Evaluating LLM User Simulators | 用户模拟器评测 |

**结论**：出现「**评测基础设施自身审计**」的新范式——把 harness 当被测软件，审计 oracle/工具契约的缺陷。

### 1.4 Reward Hacking / 评测博弈（8+ 篇）

| 日期 | 论文 | 核心 |
|---|---|---|
| 2026-10-19 | LeakBench: Auditing Reward Hacking through Prediction-Time Leakage | 奖励黑客审计 |
| 2026-10-14 | Diagnosing and Correcting Reward Hacking in Verifiable Instruction Following | 诊断纠正奖励黑客 |
| 2026-10-14 | RM-OPD: On-Policy Distillation for Generative Reward Models | 生成式 RM 蒸馏 |

## 2. 我们的三个发现的学术坐标

| 我们的发现 | 对应研究 | 覆盖情况 |
|---|---|---|
| ① 更强模型 ≠ 任务得分更高（工具调用保守策略被 judge 误罚） | 无直接对应 | **⚠️ 未覆盖 = 潜在 gap** |
| ② ground truth 粒度（过程正确性 vs 结果正确性） | Task Success Is Not Enough（副作用）、Do Benchmarks Do What They Say（工具契约） | 部分覆盖，角度不同 |
| ③ 双 Grader 系统性分歧（rule 误判合理追问 / LLM 漏判参数虚构） | LLM-as-a-Judge Is Not an Oracle（需确定性护栏） | 部分覆盖 |

## 3. 潜在切入点（发现 ①）

**「能力-评测悖论」（capability-evaluation paradox）**：

更强的基础模型在**工具调用导向**的评测中可能被**系统性低估**，因为：
1. 更强模型倾向「知识内化 + 直接回答」，跳过工具调用；
2. 评测的 judge（规则或 LLM）隐含假设「正确 = 调用工具」；
3. 结果：模型越强 → 工具调用越少 → 「工具选择/过程」维度越低 → 总分反降。

**与现有工作的差异**：
- SABench（副作用）看的是「完成了但做错」，我们看的是「完成方式不同（不调工具）却被罚」；
- Oracle audit 看的是「评测器有 bug」，我们看的是「评测设计有系统性 bias」；
- Judge bias 看的是「judge 的 prompt/尺度偏差」，我们看的是「ground truth 的粒度偏差」。

**验证路径**（要发表需补）：
1. 多模型（至少 5-6 个，含开源/闭源）跑同一工具任务集；
2. 把任务显式分成「工具必须（答案只存在于工具返回）」vs「知识可内化」；
3. 证明：更强模型在「知识可内化」任务上被 judge 低估的程度 > 弱模型；
4. 提出「工具依赖度标注 + 分桶评测」的修正方法。

## 4. 诚实评估

- 我们的实验：30 样本、单场景、合成数据、温度 0、2 模型 —— 规模不足以发表。
- 但发现 ① 现象真实、方向正确、有明确 gap，且与 2026 年「评测可靠性」大趋势吻合。
- 要走向发表：需 (a) 规模扩大到多模型/多场景，(b) 与 SABench / oracle-audit 等方法做严谨对比，(c) 提出可被他人复用的修正框架。
