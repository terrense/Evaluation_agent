# Posture–Grader Misalignment: Single Canonical Tool-Sequences Penalize Diverse Tool-Use Strategies in Agent Evaluation

> 目标期刊：arXiv preprint + Agent/Evaluation 方向 workshop（short paper）。
> 状态：**草稿基于 21 模型 × 5 家族 × 100 样本 × 3 trial 真实结果**（2026-11-02 跑完）。
>       所有数字与 `comparison.json` / `statistical_significance.json` / `ablation.json` 一致。
>       温度 0.3 一致性实验仅在早期 30 样本上做过（§5.4 注明「遗留」），未在 21 模型批次重跑。
> 标注：`[REF]` 为待核实引用（提交前必须替换为真实文献条目）。

---

## Abstract

Tool-calling agents are increasingly evaluated by comparing their tool-call *sequences* against a single canonical "correct_tools" trace. We show that this design conflates *capability* with *posture*: real models adopt one of several distinct tool-use strategies, and a process-oriented grader that requires exact sequence match scores them by their *distance from the canonical posture* rather than by whether they completed the task. On a synthetic clinical-triage benchmark (100 tasks × 3 trials × 21 models across 5 families, dual rule-based and LLM-as-judge graders), we find that posture is a model-level property — one model (MiniMax-M3) over-explores in 73% of trials while no other exceeds 20%, and two others ask-first in ~30% — and that the two graders agree only moderately on model ranking (Spearman ρ = 0.63). The disagreement is directional and cross-model: the rule grader is stricter on process dimensions (tool_selection −0.26, stop_decision −0.20) but more lenient on outcome (task_completion +0.24). Concretely, over-exploration share is strongly anti-correlated with the rule-minus-LLM gap (Pearson r = −0.79, 95% bootstrap CI [−0.93, −0.02]): the rule grader stretches a 0.08-point spread of LLM scores into a 0.20-point spread of rule scores, concentrating the inflation on the over-exploring model (rule 0.713 vs. LLM 0.844). Posture-aware regrading narrows the inflated gap from 0.145 to 0.075 (−48%), while temperature (0 vs. 0.3) leaves pass rates essentially unchanged — sampling variance is not the source. We propose *tool-dependency annotation* (must/optional/none) plus *posture-aware scoring*, which confine process penalties to tasks where a tool is genuinely required, and we release the annotation schema and grader.

## 1. Introduction

The dominant way to measure a tool-calling agent is to give it a task, let it emit a trajectory of tool calls, and compare that trajectory to a reference. Benchmarks such as τ-bench [Yao et al. 2024], ToolLLM [Qin et al. 2023], API-Bank [Li et al. 2023], and the Berkeley Function-Calling Leaderboard [Patil et al. 2025] each encode, for every task, a *ground-truth* sequence of tools and arguments that the model is expected to reproduce. A grader then scores how closely the model's trace matches that sequence.

This is a reasonable operationalization if there is exactly one correct way to do a task. But real deployments reveal that capable models do not all behave alike. Some models *ask a clarifying question before acting* — a behavior safety guidelines encourage and users often prefer, yet one that produces an empty tool sequence and therefore fails any sequence-match grader. Others *explore*: a reasoning model may call several tools to cross-check before answering, a process that is correct but "wasteful" under a trajectory-efficiency rubric. Only a third posture — reproduce the canonical sequence exactly — scores well.

We argue that this is a *posture–grader misalignment*: the ground truth encodes a single posture (the canonical one), while real models occupy a space of postures, and a process-oriented grader converts "distance from the canonical posture" into a score difference that has nothing to do with task success. The failure is not that the grader has a bug (an "oracle audit" problem [Executable-Contract Audit, arXiv:2609.37315]), nor only that a judge model has a bias (a "judge bias" problem [Wang et al. 2023]); it is that the *ground truth itself is under-specified*: it tells us *what tools exist*, not *which tools are required*.

We make three contributions:

1. **A posture taxonomy** over tool-call trajectories — *ask-first* (under-execute), *canonical* (exact), *over-explore* (over-execute), and *other* — and, across 21 models from 5 families, show that posture is a stable model-level property, not trial noise (§5.1).
2. **Evidence that the graders disagree directionally, and that the disagreement inflates a real-but-modest gap.** A rule-based process grader is lenient on outcome but strict on process, while an LLM judge is the reverse — a directional, cross-model pattern (§5.2). The consequence is *gap inflation* concentrated on over-exploration: over-exploration share is anti-correlated with the rule-minus-LLM gap (r = −0.79), and the rule grader more than doubles the cross-model score spread (§5.3, §5.5).
3. **A concrete fix**: tool-dependency annotation (must/optional/none) plus posture-aware scoring, which confines process penalties to tasks where a tool is genuinely required (§6). An ablation shows it closes ~48% of the inflated gap (§5.5). We release the annotation schema and grader to encourage reuse.

We deliberately scope this study to Chinese model families accessible without US-vendor APIs — DeepSeek, MiniMax, Qwen, Kimi, and GLM — to demonstrate that the phenomenon does not depend on any single vendor, and that the experimental design is reproducible on a domestic budget.

## 2. Related Work

**Tool-use benchmarks and their ground truth.** Tool-calling evaluation has matured rapidly. Toolformer [Schick et al. 2023] established the paradigm; ToolLLM [Qin et al. 2023] and API-Bank [Li et al. 2023] contributed large-scale datasets with reference tool sequences; τ-bench [Yao et al. 2024] added realistic multi-turn user interaction; the Berkeley Function-Calling Leaderboard [Patil et al. 2025] standardized function-calling metrics. Across these, the reference "correct tool sequence" is the backbone of scoring. Our work asks a question these benchmarks assume away: *is there a single correct sequence?*

**Process- vs. outcome-oriented grading.** Process reward models [Lightman et al. 2023; Uesato et al. 2022] score each step of a trajectory, in contrast to outcome reward models that score only the final answer. Our rule-based grader is a deterministic, hand-written process grader (8 dimensions, exact sequence match on tool_selection), and our LLM judge is an outcome-leaning grader. We show the two families disagree *directionally* on process vs. outcome dimensions — a pattern that persists across 21 models and 5 families — which has implications for reward-model design in RL for tool use.

**Judge bias and evaluation audit.** LLM-as-a-judge is known to exhibit position bias, verbosity bias, and self-preference [Wang et al. 2023; Zheng et al. 2023]. A parallel line audits evaluators for correctness [Bellibatlu et al. 2026]. Our contribution is orthogonal: the ground truth, not the judge, is the source of bias. Even a *perfect* sequence-matching grader would penalize a correct-but-non-canonical trajectory.

**Sampling-based metrics.** pass@k [Chen et al. 2021] estimates "at least one success in k samples"; pass^k [Yao et al. 2024] requires all k to succeed. We report both, plus single-pass, and find that the *posture gap* (an over-exploration rate of 73% vs. ≤20% across models) is far larger than the *sampling gap* (temperature 0→0.3 moves pass^3 by ≤0.01). This positions posture, not stochasticity, as the primary confound.

**Side-effect and safety evaluation.** SABench [Huang et al. 2026] evaluates agents on side effects of completed-but-wrong actions. We share its concern that "completed" ≠ "correct", but target a different axis: actions that are *reasonable yet non-canonical* rather than actions that are *wrong*.

## 3. Task and Setup

### 3.1 Clinical-triage benchmark

We build a synthetic hospital-guide agent with five tools: `query_department`, `query_floor`, `query_doctor_schedule`, `query_registration_policy`, and `book_appointment`. One hundred user queries (H001–H100) span three buckets defined by whether the correct answer is *only* obtainable from tools:

- **must (53 tasks)**: the answer lives only in mock tool data (floor numbers, schedules, appointment slots, policy). Not calling the tool ⇒ fabrication.
- **optional (20 tasks)**: the answer is inferable from the system prompt (symptom → department mapping is written into the prompt). Tools are one valid channel, not the only one.
- **none (27 tasks)**: no tool needed — chit-chat, clarification, or refusal of a high-risk request.

Each query specifies `expected.correct_tools` (the canonical sequence). Every task is run at 3 trials × temp = 0 across the 21-model set (an earlier exploratory 30-sample run also varied temperature, reported in §5.4).

### 3.2 Models

21 models from five independently-trained families, all accessible in mainland China via OpenAI-compatible endpoints:

| Family | Models | # |
|---|---|---|
| DeepSeek | Flash, V4-Pro | 2 |
| MiniMax | M3 (reasoning), M2.5 | 2 |
| Qwen | 32B (self-hosted vLLM on H20) + 3.5/3.6/3.7/3.8 Max·Plus·Flash cloud line (Max/Plus/Flash tiers via DashScope) | 12 |
| Kimi | K3, K2.7-Code | 2 |
| GLM | 5.3, 5.3-Prime, 5.2 | 3 |

MiniMax-M3 is a reasoning model that emits `<think>…</think>` blocks inside `content`; we strip these before grading final answers (§A.1).

### 3.3 Graders

**Rule-based grader (deterministic).** Eight dimensions — intent_accuracy, tool_selection, argument_correctness, task_completion, groundedness, safety, trajectory_efficiency, stop_decision — each in {0,1}. `tool_selection = 1` **iff the called-tool sequence exactly equals `expected.correct_tools`**. The aggregate score is `safety × mean(8 dims)`; a trial "passes" at threshold 0.75 (this mirrors the multiplicative safety gate in claw-eval, the harness this study builds on).

**LLM-as-judge.** DeepSeek-V4-Pro scores the same 8 dimensions on a 0–1 scale, given the query, the expected tools, and the trajectory. We cross providers (the judge is a DeepSeek model scoring MiniMax/Qwen/Kimi/GLM agents) to limit, though not eliminate, self-preference (§7).

**Posture classification.** For each trial we compare the model's called-tool list against `expected.correct_tools`: *exact* (equal), *under* (empty — ask-first), *over* (more tools than expected), *other* (different, non-empty, same length).

## 4. Experimental Questions

- **RQ1 (posture)**: do models differ in tool-use posture, and is the difference model-level rather than trial-level?
- **RQ2 (grader agreement)**: do rule-based and LLM graders agree on model ranking, and where do they diverge?
- **RQ3 (gap)**: does the rule grader inflate cross-model gaps, and is the inflation driven by posture?
- **RQ4 (sampling)**: how much does temperature contribute, relative to posture?

## 5. Results

### 5.1 RQ1 — Posture is a model-level property (temp = 0, 300 trials each)

| Model | Family | exact% | under (ask-first)% | over (explore)% | other% |
|---|:--:|:--:|:--:|:--:|:--:|
| **MiniMax-M3** | MiniMax | 25.7 | **0.0** | **73.3** | 1.0 |
| Qwen3.8-Max | Qwen | 46.7 | 25.7 | 20.0 | 7.7 |
| DeepSeek-V4-Pro | DeepSeek | 57.0 | 32.0 | 5.3 | 5.7 |
| DeepSeek-Flash | DeepSeek | 54.3 | 27.0 | 12.3 | 6.3 |
| Qwen-Max | Qwen | 85.0 | 1.7 | 8.3 | 5.0 |

Across all 21 models, the over-exploration rate ranges from 1.3% (Qwen-Plus) to 73.3% (MiniMax-M3), with the *second*-highest over-explorer at 20% (Qwen3.8-Max) — MiniMax-M3 is a >3.5× outlier, and it is the only model that *never* asks first (under = 0%). The ask-first rate ranges from 0% to 32.0% (V4-Pro), with Flash (27.0%) and Qwen3.8-Max (25.7%) close behind. Because `tool_selection` requires exact match, *both* postures receive `tool_selection = 0`. The three postures are not noise: at 300 trials per model, these proportions are stable, and the outliers are consistently the same models.

### 5.2 RQ2 — Directional, cross-model grader disagreement

The two graders agree only moderately on model ranking: **Spearman ρ = 0.63** over 21 models. The disagreement is *directional* and holds across families — the rule grader is systematically stricter on process dimensions and more lenient on the outcome dimension:

| Dimension (cross-model mean) | rule | LLM | rule − LLM |
|---|:--:|:--:|:--:|
| intent_accuracy | 0.689 | 0.953 | −0.264 |
| tool_selection | 0.627 | 0.887 | −0.260 |
| stop_decision | 0.747 | 0.951 | −0.204 |
| groundedness | 0.821 | 0.945 | −0.124 |
| argument_correctness | 0.983 | 0.905 | +0.078 |
| trajectory_efficiency | 0.974 | 0.934 | +0.040 |
| **task_completion** | **0.972** | **0.730** | **+0.242** |

The rule grader is strict where the process diverges from the canonical sequence (tool_selection, stop_decision, intent_accuracy), but near-saturated and *more lenient than the LLM* on task_completion and argument_correctness. The LLM judge is the mirror image: it accepts non-canonical paths (high tool_selection) but is far more skeptical about whether the agent actually delivered the answer (task_completion 0.73). A single scalar "grader bias" term cannot capture this — the two graders prioritize opposite axes, and the pattern is consistent across all five families.

### 5.3 RQ3 — Over-exploration drives gap inflation

| Model | rule overall | LLM overall | gap (rule − LLM) | over% |
|---|:--:|:--:|:--:|:--:|
| **MiniMax-M3** | **0.713** | 0.844 | **−0.131** | 73.3 |
| GLM-5.3-Prime | 0.860 | 0.924 | −0.064 | 13.7 |
| Qwen-Max | 0.916 | 0.901 | +0.016 | 8.3 |
| DeepSeek-Flash | 0.838 | 0.853 | −0.015 | 12.3 |

The rule grader's cross-model spread is **0.203** (0.713–0.916), while the LLM judge's is **0.079** (0.844–0.923). The inflation is concentrated on the over-exploring model: MiniMax-M3 is bottom by the rule grader (0.713) yet near the middle by the LLM judge (0.844), for a gap of −0.131 — by far the largest. Across all 21 models, **over-exploration share is strongly anti-correlated with the rule-minus-LLM gap (Pearson r = −0.79, 95% bootstrap CI [−0.93, −0.02])**; ask-first share is not (Flash's gap is −0.015, essentially zero). The "knowledge-internalization" hypothesis does not occur: in the must bucket, models that do not call a required tool *ask for more information* rather than fabricate, so the inflation is a property of posture, not of knowledge.

### 5.4 RQ4 — Sampling is a red herring (30-sample legacy)

| Configuration | single-pass | Pass@3 | Pass^3 |
|---|:--:|:--:|:--:|
| Flash t0 / t0.3 | 0.478 / 0.478 | 0.533 / 0.533 | 0.446 / 0.446 |
| V4-Pro t0 / t0.3 | 0.500 / 0.511 | 0.533 / 0.533 | 0.478 / 0.486 |
| MiniMax-M3 t0 | 0.311 | 0.400 | 0.242 |

Temperature 0 → 0.3 moves nothing of consequence (Pass@3 is flat at 0.533; Pass^3 shifts by ≤0.01). The sampling gap is real but dwarfed by the posture gap (an over-exploration rate of 73% vs. ≤20%). Reporting temperature or sampling as the primary source of variance would mislocate the phenomenon. (This experiment was run on the early 30-sample subset and is not re-run on the 100-sample 21-model batch.)

### 5.5 Ablation — decomposing posture vs. capability

We re-score the same trajectories under progressively fairer graders (§6) to bound how much of MiniMax-M3's deficit is posture vs. genuine error. The baseline column reproduces the rule scores exactly (a sanity check).

| Grader variant | MiniMax-M3 | mean of other 20 | gap (others − M3) | cross-model std |
|---|:--:|:--:|:--:|:--:|
| baseline — exact sequence match | 0.713 | 0.858 | 0.145 | 0.0366 |
| A — outcome-only (drop 3 process dims) | 0.857 | 0.936 | 0.079 | 0.0180 |
| B — bucket-aware (drop process penalties in optional/none) | 0.760 | 0.873 | 0.113 | 0.0293 |
| C — B + posture-aware must (necessary-tool ⊆ called) | 0.792 | 0.874 | 0.082 | 0.0245 |
| D — C + relax efficiency (full fix) | 0.799 | 0.874 | 0.075 | 0.0235 |

The full fix (D) closes ~48% of MiniMax-M3's gap (0.145 → 0.075) and shrinks the cross-model std from 0.0366 to 0.0235. It does not eliminate the gap: the residual reflects MiniMax-M3's genuine outcome deficits, which even the outcome-only variant (A) still surfaces (gap 0.079). The components contribute differently: bucket-awareness alone (B) barely helps, because MiniMax-M3's failures concentrate in the must bucket where the process penalty remains; the posture-aware must step (C) and the efficiency relaxation (D) do most of the work. This decomposition is the quantitative evidence that process grading *inflates* a modest outcome deficit into a large rule gap — and it cleanly separates the two quantities (posture vs. capability) that a single scalar score otherwise confounds.

### 5.6 Statistical significance

We bound the uncertainty of the headline correlations with cluster-bootstrap resampling (10,000 draws, resampling whole models, fixed seed 42).

| Quantity | estimate | 95% CI |
|---|:--:|:--:|
| Spearman ρ (rule ranking, LLM ranking) | 0.631 | — |
| Pearson r (over%, rule−LLM gap) | −0.789 | [−0.934, −0.024] |
| rule cross-model std | 0.0366 | — |
| LLM cross-model std | 0.0225 | — |
| rule_std − llm_std | +0.014 | [−0.009, +0.033] |

The over%-gap correlation is significantly negative (CI excludes 0) — the quantitative backbone of the gap-inflation claim. The std difference, however, brackets 0: "the rule grader is more spread out" is a *directional* observation, not yet a statistically significant one at n = 21 models. (An earlier 30-sample run additionally reported a paired McNemar test on trial-0 pass rates — MiniMax-M3 vs. V4-Pro: c = 15 vs. b = 1, p = 0.0005 — confirming the graders disagree asymmetrically in exactly the direction that punishes over-exploration.)

## 6. Proposed Fix

**Tool-dependency annotation.** We annotate each task must/optional/none (§3.1). The rule grader then applies the `tool_selection` and `stop_decision` penalties only in the **must** bucket — where a missing tool call *is* a failure — and drops them in optional/none, where a direct answer or a clarification is a legitimate path.

**Posture-aware scoring.** In the must bucket, replace exact-sequence match with two outcome-oriented checks: (i) was the *necessary* tool called at least once (not the *exact* sequence), and (ii) is the final answer grounded (sourced from a tool return) and complete. This credits a MiniMax-style cross-checking trace and a Flash-style clarifying trace, as long as the required tool was eventually called with correct arguments.

We release the annotation schema (JSON) and the modified grader so the community can apply it to existing tool benchmarks without re-annotating from scratch.

## 7. Limitations and Honest Boundaries

- **Single-domain synthetic benchmark.** One hospital scenario; external validity to finance/coding is untested. This is the largest remaining gap to a full conference/SCI submission.
- **Self-preference.** DeepSeek-V4-Pro is both an agent and the judge. We cross providers for the MiniMax/Qwen/Kimi/GLM agents but not for the DeepSeek agents; LLM scores are a *relative* reference, not ground truth.
- **"Rule is more spread" is not yet significant.** The rule/LLM cross-model std difference (+0.014) has a 95% CI that brackets 0; the significant result is the over%-gap *correlation*, not the spread difference itself.
- **Mock date brittleness does not explain over-explore.** Our mock `query_doctor_schedule` originally matched only a literal "周四", not "本周四"/full dates. We fixed this via date normalization and re-ran MiniMax-M3 (90 trials): its over-explore rate moved only 80.0% → 77.8% (−2.2 pp), with just ~2 of 72 over-exploring trials converting. Over-exploration is therefore genuine model behavior (extra location queries; repeatedly retrying "today" instead of clarifying once), not a mock artifact — which strengthens rather than undermines our thesis.
- **Posture taxonomy is coarse.** exact/under/over/other is a length-based heuristic against the expected sequence; it does not yet distinguish "reasonable cross-checking" from "genuinely wasteful exploration." Formalizing this boundary (§2) is left to future work and is a likely reviewer question.

## 8. Conclusion

We show that tool-calling evaluation with a single canonical tool-sequence systematically mis-scores capable agents: it rewards reproducing one posture and punishes others that are equally valid, producing a rule score spread (0.20) that more than doubles the LLM judge's spread (0.08) and concentrating the inflation on the over-exploring model. The disagreement between graders is *directional* — process-strict/outcome-lenient versus the reverse — so no single scalar "bias" term captures it. Our fix, tool-dependency annotation plus posture-aware scoring, confines process penalties to where they are justified, and an ablation shows it recovers about half of the inflated gap. We hope this motivates a shift in tool-agent evaluation from "match the canonical trace" to "reach a grounded, completed answer."

---

## Appendix A. Implementation notes

- **A.1** MiniMax-M3 emits `<think>…</think>` inside `content` (its `reasoning_content` field is None). We strip the block with a regex before grading final answers.
- **A.2** Determinism: the rule grader is pure Python and validated by pytest; all numbers above are reproducible from `run_multimodel.py` + `analyze_multimodel.py` + `statistical_significance.py` + `ablation_posture_grader.py`.
- **A.3** Metrics: aggregate = `safety × mean(8 dims)`; pass@k uses the unbiased estimator `1 − C(n−c,k)/C(n,k)` [Chen et al. 2021]; pass^k = `(c/n)^k` [Yao et al. 2024], implemented following the claw-eval harness we build on.

## References

> 提交前必须逐条核实作者全名/页码；`[verify]` 为待二次核对，`[REF]` 为待补。

- Chen, M., et al. (2021). *Evaluating Large Language Models Trained on Code.* arXiv:2107.03374. (pass@k)
- Schick, T., et al. (2023). *Toolformer: Language Models Can Teach Themselves to Use Tools.* arXiv:2302.04761.
- Qin, Y., Liang, S., Ye, Y., Zhu, K., Yan, L., Lu, Y., Lin, Y., Cong, X., Tang, X., Qian, B., Zhao, S., Hong, L., Tian, R., Xie, R., Zhou, J., Gerstein, M., Li, D., Liu, Z., Sun, M. (2023). *ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs.* arXiv:2307.16789.
- Li, M., Zhao, Y., Yu, B., Song, F., Li, H., Yu, H., Li, Z., Huang, F., Li, Y. (2023). *API-Bank: A Comprehensive Benchmark for Tool-Augmented LLMs.* arXiv:2304.08244.
- Yao, S., Shinn, N., Razavi, P., Narasimhan, K. (2024). *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.* arXiv:2406.12045. (introduces pass^k)
- Patil, S. G., Mao, R., Yan, F., Ji, C., Suresh, S., Stoica, I., Gonzalez, J. E. (2025). *The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large Language Models.* ICML 2025.
- Huang, J., Chen, S., Liang, X., Ma, X., Yang, H., Ke, W., Tan, T., Sun, Y. (2026). *Task Success Is Not Enough: Side-effect-Aware Evaluation of Tool-Using Language Model Agents (SABench).* arXiv:2610.34167, NeurIPS 2026 E&D Track.
- Zheng, L., et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* arXiv:2306.05685.
- Wang, P., Li, L., Chen, L., Cai, Z., Zhu, D., Lin, B., Cao, Y., Liu, Q., Liu, T., Sui, Z. (2023). *Large Language Models Are Not Fair Evaluators.* arXiv:2305.17926.
- Bellibatlu, R. R., Wang, Z., Zhang, W. (2026). *Do Agent Benchmarks Do What They Say? An Executable-Contract Audit of Tool-Using Agent Environments.* arXiv:2609.37315.
- Lightman, H., et al. (2023). *Let's Verify Step by Step.* arXiv:2305.20050.
- Uesato, J., et al. (2022). *Solving Math Word Problems with Process- and Outcome-Based Feedback.* arXiv:2211.14275.
- claw-eval — the evaluation harness this study builds on (multiplicative safety gate, pass@k/pass^k implementation); cite release repo.
