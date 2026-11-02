# 研究简报：姿态-评测错配（Posture–Grader Misalignment）

> 协作研究者的入口文档（含 ChatGPT）。这篇论文在做什么、三个上游开源项目起了什么作用、
> 现在体量够不够、创新点在哪、下一步怎么补。详细证据与数字见文末「文件索引」。

---

## 1. 一句话论点

现有工具调用 Agent 评测，把模型「调用的工具序列」拿去和一条写死的「标准序列」（`correct_tools`）
做精确匹配；但真实模型至少有三种**工具使用姿态**，而评分器只认其中一种，于是把「姿态不同」
误判成「能力不行」——把本来温和的真实结果差距（~0.11）放大成显著差距（~0.19）。
核心结论是 **gap inflation（差距放大）**，而不是 spurious inversion（假倒挂）。

四层展开：
1. ground truth 只编码一种标准工具序列；
2. 真实模型有三种姿态：**先追问（ask-first / under-execute）**、**标准执行（canonical / exact）**、
   **过度探索（over-explore / over-execute）**；
3. 评分器只奖励「标准执行」，对另外两种系统性打低分（尽管它们在真实场景常是合理甚至被鼓励的）；
4. 结果：模型得分被「离标准姿态的距离」系统性扭曲。

---

## 2. 三个上游开源项目怎么起作用（不是空借鉴，各有具体分工）

| 项目 | 定位 | 在我们 harness 里实际承担的角色 |
|---|---|---|
| **OpenJudge** | 通用评测框架 + 质量奖励 | 提供**评分器抽象**：三种 Grader（Function/LLM/Agentic）+ Rubric/Checkpoint + EvalFeedback。启发「确定性 rule grader + LLM judge 双轨」设计，以及「失败样本显式列出、不静默丢弃」的 coverage 原则 |
| **claw-eval** | 300 任务 benchmark + 轨迹审计 | 是**地基**。我们直接搭在它上面：`safety × mean(8维)` 聚合公式、`pass@k`/`pass^k` 无偏估计、「轨迹/audit/snapshot 三证据通道」→ 变成我们的 `trajectory` 字段。论文里「outcome-only 漏判 0.667 vs 轨迹 0.333」直接复现它「trajectory-opaque 漏 44%」的结论 |
| **AI-Infra-Guard** | AI 红队平台（静态正则 + LLM 审计 + 三阶段） | 提供**安全层**：静态预扫描「定位提示」、LLM 审计「下结论」的分层 → 变成 8 维里的 `safety` 维 + `groundedness` 硬门（实测硬门把漏判 0.333 → 0.167） |

一句话：三个项目给的是「评测机器」（公式、grader 抽象、安全检测）；本论文的贡献不是从它们抄来的，
而是在它们之上问了一个**新问题**——「标准答案序列」这个前提本身是不是就错了。

---

## 3. 核心发现（真实数据，21 模型 × 100 样本 × 3 trial 已验证）

| # | 发现 | 证据 |
|---|---|---|
| F1 | 姿态是模型级特征 | MiniMax-M3「过度探索」73%（其余 ≤20%）；Flash/Qwen3.8-Max「先追问」~27%；Qwen-Max/Qwen-Flash「标准执行」75-85% |
| F2 | 双 Grader 只中等一致 | rule 与 LLM 对 21 模型排序 Spearman=0.63；分歧集中在过度探索模型 |
| F3 | 差距放大由 over 驱动 | over% 与 (rule−LLM) 差 r=−0.79（bootstrap CI [−0.93,−0.02]）；rule 拉开 0.71–0.92（全距 0.20），LLM 挤在 0.84–0.92（全距 0.08）；消融把 MiniMax 差距 0.145→0.075 |
| F4 | 温度是烟雾弹 | （30 样本遗留）0→0.3 时 Pass@3 纹丝不动（0.533）、Pass^3 只挪 ≤0.01；姿态差远大于采样方差 |

其他支持性发现（Phase 2-6）：outcome-only 漏判 0.667；hard gate 减漏判增误判；静态正则 recall=1.0
但仅因用例教科书式明显；rule grader 的两个经典 bug 靠 pytest 校验兜底。

---

## 4. 创新点（3 个，按含金量排序）

| # | 创新点 | 含金量 | 会被怎么质疑 |
|---|---|---|---|
| 1 | 姿态分类学（under/exact/over/other） | 中低 | under/over-execute 概念学界早有，是描述性手段不是目的；「这不就是 exploration vs exploitation 换名吗？」 |
| 2 | **方向性分歧 + 差距放大** | **最高，真卖点** | 证明 rule 对「过程」狠对「结果」松、LLM 反过来，是**方向性**分歧；并精确拆开「姿态惩罚 ~0.08」和「结果短板 ~0.11」。「LLM judge 也有自偏好，凭什么拿它当参照？」 |
| 3 | must/optional/none 标注 + 姿态感知评分 + 消融分解 | 中 | 方法实用，但「重新标 ground truth」本身不新；价值是把「发现问题」升级成「给可复用解法」+ 开源交付物 |

**改进点 / 差异定位**：别人在「把 ground truth 标得更全、把 judge 调得更准」，本工作在问更底层的
问题——**「标准答案序列」这个前提本身是不是就错了**。

---

## 5. 完备性现状（诚实评估）

**结论：现在体量只够 workshop / short paper，不够正会或 SCI。**

- **P0 已补（不补发不出去）**：mock 日期脆弱性已修 + 量化（over-explore 80%→77.8%，仅 −2.2pp，
  证明「过度探索不是 artifact」）；全部引用已核实（SABench arXiv:2610.34167、Executable-Contract Audit
  arXiv:2609.37315 均真实）；样本设计扩到 100（optional 20 / must 53 / none 27）；30 样本上已做
  cluster bootstrap + McNemar（rule gap −0.189 显著、LLM gap +0.034 不显著、gap inflation −0.197 显著）。
- **P1 已完成**：模型 2 家族 → 5 家族 21 模型（DeepSeek/MiniMax/Qwen/Kimi/GLM）已重跑；100 样本新分数已出（2026-11-02）。
- **P2 待补（补了才能投会议/SCI）**：**单场景**（只医院导诊，未验证金融/客服/编码）是最大硬伤；
  无 head-to-head（未与 SABench / oracle-audit 同 benchmark 正面比）；开源姿态标注工具未落地；
  v4-pro 既当 agent 又当 judge 的自偏好偏差未消除。

---

## 6. 文件索引（协作入口）

**文档（docs/）**
- `paper-outline.md` —— 论文骨架：标题、贡献、方法、相关工作差异表、待补清单
- `paper-draft.md` —— 英文初稿（含 References，作者全名已补全）
- `论文自查.md` —— 白话自检：创新点含金量、能不能发、审稿人三枪、必须补清单（**先读这篇**）
- `evaluation-design.md` —— 8 维评分规范 + 四方案对比 + 评分公式 + 三项目分工
- `findings.md` —— Phase 2-6 全部真实结论 + 三项目源码分析
- `research-survey.md` —— 2026 Agent 评测/LLM-judge 研究全景 + 发表切入点
- `sample-expansion-spec.md` —— 300 样本扩样规格
- `architecture.md` / `security.md` / `papers.md` / `experiments.md` / `h20-qwen3-deploy.md`

**核心代码（experiments/openjudge/hospital/）**
- `samples.py` —— 100 样本（H001-H100）；`tool_requirement.py` —— must/optional/none 标注
- `graders_rule.py` —— 8 维确定性 grader；`posture_grader.py` —— 姿态重打分（分桶消融 A/B/C/D）
- `providers.py` —— 多 provider 注册（5 家族 21 模型）；`real_agent.py` —— 真实 LLM agent
- `llm_judge.py` —— LLM-as-Judge；`run_multimodel.py` —— 多模型 × 温度 runner
- `tools.py` —— mock 工具（含 `_normalize_date` 日期归一化）；`export_annotation.py` —— 生成 annotation.json
- `test_grader.py` —— grader pytest 校验
- `symptom_expansion.py` + `data/symptom_expansion.json` —— 扩样框架（H101-H172，72 条，待合并）

**结果（reports/openjudge/multimodel/）**
- 每模型目录下：`real_traces.jsonl`（真实轨迹）/ `rule_scores.json`（8 维）/ `llm_scores.jsonl`（judge）

---

## 7. 建议 ChatGPT 协助的方向

1. **补场景**（P2 最大短板）：设计金融客服 / 编码两个场景的样本 + 工具，复用现有 harness 跑一遍，
   验证「差距放大」是否跨场景成立。
2. **形式化「姿态」定义**（审稿人会问）：现在 exact/under/over/other 是「跟 expected 序列比长短」的粗分法，
   需要给出「合理过度探索」与「真乱调」的可判定标准。
3. **润色 Related Work 与 Intro**：把「方向性分歧 + gap inflation」的定位讲清，与 SABench / oracle-audit /
   BFCL / τ-bench 的差异表写实。
4. **统计方法复核**：21 模型跑完后，cluster bootstrap + McNemar 需按多模型重算，确认显著性结论的稳健性。
