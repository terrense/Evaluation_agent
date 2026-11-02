# Posture–Grader Misalignment: Single Canonical Tool-Sequences Penalize Diverse Tool-Use Strategies in Agent Evaluation

> 目标期刊：arXiv preprint + Agent/Evaluation 方向 workshop（short paper）。
> 状态：完整草稿。所有数字来自 `reports/openjudge/multimodel/comparison.json`，未作任何加工。
> 标注：`[REF]` 为待核实引用（提交前必须替换为真实文献条目）。

---

## Abstract

Tool-calling agents are increasingly evaluated by comparing their tool-call *sequences* against a single canonical "correct_tools" trace. We show that this design conflates *capability* with *posture*: real models adopt one of several distinct tool-use strategies, and a process-oriented grader that requires exact sequence match scores them by their *distance from the canonical posture* rather than by whether they completed the task. On a synthetic clinical-triage benchmark (30 tasks × 3 trials × 3 models × 2 temperatures, dual rule-based and LLM-as-judge graders), we observe three mutually-exclusive postures — *ask-first* (DeepSeek-Flash and DeepSeek-V4-Pro, ~40% of trials), *canonical* (~47%), and *over-explore* (MiniMax-M3, 78% of trials) — and show that the rule-based grader drives a 0.12–0.61 gap against the LLM judge on process dimensions (tool_selection, stop_decision) while the graders also disagree on outcome dimensions in a posture-dependent way. This produces *gap inflation* rather than a spurious inversion: the over-exploring model (MiniMax-M3) earns the lowest rule-based score (0.605 vs. 0.783/0.793), yet an LLM judge finds no significant difference (0.828 vs. 0.794; gap +0.03, n.s.) and our posture-aware regrading narrows the rule gap to 0.110 (§5.5) — a modest, genuine outcome-dimension deficit that posture penalties inflate into a large, statistically significant rule gap (0.19; cluster-bootstrap 95% CI [−0.26, −0.12]; McNemar p<0.001). Temperature (0 vs. 0.3) has a negligible effect on pass rates, indicating that sampling variance is not the source of the discrepancy. We propose a two-part fix: *tool-dependency annotation* (must/optional/none) so that process penalties are only applied where a tool is genuinely required, and *posture-aware scoring* that credits any path that reaches a grounded, completed answer.

## 1. Introduction

The dominant way to measure a tool-calling agent is to give it a task, let it emit a trajectory of tool calls, and compare that trajectory to a reference. Benchmarks such as τ-bench [Yao et al. 2024], ToolLLM [Qin et al. 2023], API-Bank [Li et al. 2023], and the Berkeley Function-Calling Leaderboard [Patil et al. 2025] each encode, for every task, a *ground-truth* sequence of tools and arguments that the model is expected to reproduce. A grader then scores how closely the model's trace matches that sequence.

This is a reasonable operationalization if there is exactly one correct way to do a task. But real deployments reveal that capable models do not all behave alike. Some models *ask a clarifying question before acting* — a behavior safety guidelines encourage and users often prefer, yet one that produces an empty tool sequence and therefore fails any sequence-match grader. Others *explore*: a reasoning model may call several tools to cross-check before answering, a process that is correct but "wasteful" under a trajectory-efficiency rubric. Only a third posture — reproduce the canonical sequence exactly — scores well.

We argue that this is a *posture–grader misalignment*: the ground truth encodes a single posture (the canonical one), while real models occupy a space of postures, and a process-oriented grader converts "distance from the canonical posture" into a score difference that has nothing to do with task success. The failure is not that the grader has a bug (an "oracle audit" problem [Executable-Contract Audit, arXiv:2609.37315]), nor only that a judge model has a bias (a "judge bias" problem [Wang et al. 2023]); it is that the *ground truth itself is under-specified*: it tells us *what tools exist*, not *which tools are required*.

We make three contributions:

1. **A posture taxonomy** over tool-call trajectories — *ask-first* (under-execute), *canonical* (exact), *over-explore* (over-execute), and *other* — and show that three independently-trained models occupy three nearly-disjoint regions of this space (§5.1).
2. **Evidence of grader disagreement that is directional, not scalar**: a rule-based process grader is lenient on outcome but strict on process, while an LLM judge is the reverse (§5.2). The consequence is *gap inflation*: the process grader turns a modest, genuine outcome-dimension deficit into a large, statistically significant rule gap that an LLM judge does not corroborate (§5.3, §5.5).
3. **A concrete fix**: tool-dependency annotation (must/optional/none) plus posture-aware scoring, which confines process penalties to tasks where a tool is genuinely required (§6). We release the annotation schema and grader to encourage reuse.

We deliberately scope this study to Chinese model families accessible without US-vendor APIs — DeepSeek and MiniMax in the reported results, with Qwen, Kimi, and GLM registered for the expanded study (§7) — to demonstrate that the phenomenon does not depend on any single vendor, and that the experimental design is reproducible on a domestic budget.

## 2. Related Work

**Tool-use benchmarks and their ground truth.** Tool-calling evaluation has matured rapidly. Toolformer [Schick et al. 2023] established the paradigm; ToolLLM [Qin et al. 2023] and API-Bank [Li et al. 2023] contributed large-scale datasets with reference tool sequences; τ-bench [Yao et al. 2024] added realistic multi-turn user interaction; the Berkeley Function-Calling Leaderboard [Patil et al. 2025] standardized function-calling metrics. Across these, the reference "correct tool sequence" is the backbone of scoring. Our work asks a question these benchmarks assume away: *is there a single correct sequence?*

**Process- vs. outcome-oriented grading.** Process reward models [Lightman et al. 2023; Uesato et al. 2022] score each step of a trajectory, in contrast to outcome reward models that score only the final answer. Our rule-based grader is a deterministic, hand-written process grader (8 dimensions, exact sequence match on tool_selection), and our LLM judge is an outcome-leaning grader. We show the two families disagree *directionally* on process vs. outcome dimensions, which has implications for reward-model design in RL for tool use.

**Judge bias and evaluation audit.** LLM-as-a-judge is known to exhibit position bias, verbosity bias, and self-preference [Wang et al. 2023; Zheng et al. 2023]. A parallel line audits evaluators for correctness [Bellibatlu et al. 2026]. Our contribution is orthogonal: the ground truth, not the judge, is the source of bias. Even a *perfect* sequence-matching grader would penalize a correct-but-non-canonical trajectory.

**Sampling-based metrics.** pass@k [Chen et al. 2021] estimates "at least one success in k samples"; pass^k [Yao et al. 2024] requires all k to succeed. We report both, plus single-pass, and find that the *posture gap* (0.13–0.47 in exact-match rate across models) is an order of magnitude larger than the *sampling gap* (temperature 0→0.3 moves pass^3 by ≤0.01). This positions posture, not stochasticity, as the primary confound.

**Side-effect and safety evaluation.** SABench [Huang et al. 2026] evaluates agents on side effects of completed-but-wrong actions. We share its concern that "completed" ≠ "correct", but target a different axis: actions that are *reasonable yet non-canonical* rather than actions that are *wrong*.

## 3. Task and Setup

### 3.1 Clinical-triage benchmark

We build a synthetic hospital-guide agent with five tools: `query_department`, `query_floor`, `query_doctor_schedule`, `query_registration_policy`, and `book_appointment`. Thirty user queries (H001–H030) span three buckets defined by whether the correct answer is *only* obtainable from tools:

- **must (18 tasks)**: the answer lives only in mock tool data (floor numbers, schedules, appointment slots, policy). Not calling the tool ⇒ fabrication.
- **optional (3 tasks)**: the answer is inferable from the system prompt (symptom → department mapping is written into the prompt). Tools are one valid channel, not the only one.
- **none (9 tasks)**: no tool needed — chit-chat, clarification, or refusal of a high-risk request.

Each query specifies `expected.correct_tools` (the canonical sequence). Every task is run at 3 trials × 2 temperatures (0 and 0.3) × 3 models.

### 3.2 Models

Three models from two independently-trained families, all accessible in mainland China via OpenAI-compatible endpoints:

| Model | Family | Posture (observed) |
|---|---|---|
| DeepSeek-Flash | DeepSeek | ask-first |
| DeepSeek-V4-Pro | DeepSeek | ask-first |
| MiniMax-M3 | MiniMax (reasoning) | over-explore |

MiniMax-M3 is a reasoning model that emits `<think>…</think>` blocks inside `content`; we strip these before grading final answers (§A.1).

### 3.3 Graders

**Rule-based grader (deterministic).** Eight dimensions — intent_accuracy, tool_selection, argument_correctness, task_completion, groundedness, safety, trajectory_efficiency, stop_decision — each in {0,1}. `tool_selection = 1` **iff the called-tool sequence exactly equals `expected.correct_tools`**. The aggregate score is `safety × mean(8 dims)`; a trial "passes" at threshold 0.75 (this mirrors the multiplicative safety gate in claw-eval, the harness this study builds on).

**LLM-as-judge.** DeepSeek-V4-Pro scores the same 8 dimensions on a 0–1 scale, given the query, the expected tools, and the trajectory. We cross providers (the judge is a DeepSeek model scoring a MiniMax agent) to limit, though not eliminate, self-preference (§7).

**Posture classification.** For each trial we compare the model's called-tool list against `expected.correct_tools`: *exact* (equal), *under* (empty — ask-first), *over* (more tools than expected), *other* (different, non-empty, same length).

## 4. Experimental Questions

- **RQ1 (posture)**: do models differ in tool-use posture? 
- **RQ2 (grader agreement)**: do rule-based and LLM graders agree, and where do they diverge?
- **RQ3 (gap)**: does the ranking match capability, and how much of any gap is posture vs. genuine deficit?
- **RQ4 (sampling)**: how much does temperature contribute, relative to posture?

## 5. Results

### 5.1 RQ1 — Three models, three postures (temp = 0, 90 trials each)

| Model | exact | under (ask-first) | over (explore) | other |
|---|:--:|:--:|:--:|:--:|
| DeepSeek-Flash | 46.7% | 36.7% | 10.0% | 6.7% |
| DeepSeek-V4-Pro | 46.7% | 40.0% | 3.3% | 10.0% |
| MiniMax-M3 | 17.8% | **0.0%** | **77.8%** | 4.4% |

The three models occupy nearly disjoint regions. Flash and V4-Pro ask for missing information in roughly two-fifths of trials; MiniMax-M3 *never* asks first and instead over-explores in over three-quarters of trials. Since `tool_selection` requires exact match, both postures receive `tool_selection = 0`.

### 5.2 RQ2 — Directional grader disagreement

| Dimension | Flash (rule→LLM) | V4-Pro (rule→LLM) | MiniMax-M3 (rule→LLM) |
|---|:--:|:--:|:--:|
| tool_selection | 0.467 → 0.847 | 0.467 → 0.697 | 0.178 → 0.790 |
| stop_decision | 0.567 → 0.940 | 0.500 → 0.923 | 0.778 → 0.902 |
| intent_accuracy | 0.500 → 0.928 | 0.511 → 0.930 | 0.373 → 0.922 |
| **task_completion** | **0.911 → 0.573** | **1.000 → 0.540** | **0.678 → 0.738** |

The disagreement is *directional but posture-dependent*. On process dimensions (tool_selection, stop_decision, intent_accuracy) the LLM judge is 0.12–0.61 more lenient than the rule grader for all three models — it accepts ask-first and over-explore as legitimate ways to reach an answer. On the *outcome* dimension (task_completion) the direction flips with posture: the LLM judge is 0.34–0.46 **stricter** for the ask-first DeepSeek models — it judges that they asked a question but never delivered the booking — yet 0.06 more *lenient* for the over-exploring MiniMax-M3, whose extra queries do reach a grounded answer. A single "grader is biased" framing cannot capture this: the two graders prioritize opposite things, and the direction of their outcome disagreement depends on posture.

### 5.3 RQ3 — Posture penalties inflate a real but modest capability gap

| Model | rule overall | LLM overall |
|---|:--:|:--:|
| DeepSeek-Flash | 0.783 | 0.832 |
| DeepSeek-V4-Pro | 0.793 | 0.794 |
| **MiniMax-M3** | **0.605** | 0.828 |

MiniMax-M3 — the most exploration-heavy (and the only reasoning) model — earns the lowest rule-based score (0.605). This is *not* purely a grader artifact: MiniMax-M3 also trails the DeepSeek models on genuine outcome dimensions — intent_accuracy 0.373, groundedness 0.600, argument_correctness 0.689, task_completion 0.678 (§5.2). Yet an LLM judge finds no significant difference (0.828 vs. 0.794, a gap of +0.03, 95% CI [−0.03, +0.10]): it accepts MiniMax-M3's over-explore posture as a legitimate path to a grounded answer. Our posture-aware regrading narrows the rule gap from 0.189 to 0.110 (§5.5), with the residual reflecting the genuine outcome deficits. The rule grader therefore *inflates* a modest genuine deficit into a large, statistically significant gap (0.19, CI [−0.26, −0.12]) by stacking two posture penalties — exact-sequence `tool_selection` and a `trajectory_efficiency` cap — on top of the genuine errors. Crucially, the "knowledge-internalization" hypothesis does not occur: in the must bucket, models that do not call a required tool *ask for more information* rather than fabricate (§5.1), so the inflation is a property of posture, not of knowledge.

### 5.4 RQ4 — Sampling is a red herring

| Configuration | single-pass | Pass@3 | Pass^3 |
|---|:--:|:--:|:--:|
| Flash t0 / t0.3 | 0.478 / 0.478 | 0.533 / 0.533 | 0.446 / 0.446 |
| V4-Pro t0 / t0.3 | 0.500 / 0.511 | 0.533 / 0.533 | 0.478 / 0.486 |
| MiniMax-M3 t0 | 0.311 | 0.400 | 0.242 |

Temperature 0 → 0.3 moves nothing of consequence (Pass@3 is flat at 0.533; Pass^3 shifts by ≤0.01). The gap between single-pass and Pass@3 (≈0.05) and between Pass@3 and Pass^3 (≈0.05–0.16) is real but dwarfed by the *posture* gap: an exact-match rate of 0.178 vs. 0.467 across models. Reporting temperature or sampling as the primary source of variance would mislocate the phenomenon.

### 5.5 Ablation — decomposing posture vs. capability

We re-score the same trajectories under progressively fairer graders (§6) to bound how much of MiniMax-M3's deficit is posture vs. genuine error. The baseline column reproduces the rule scores exactly (a sanity check).

| Grader variant | Flash | V4-Pro | MiniMax-M3 | gap (M3−V4) |
|---|:--:|:--:|:--:|:--:|
| baseline — exact sequence match | 0.783 | 0.793 | 0.605 | −0.188 |
| A — outcome-only (drop 3 process dims) | 0.908 | 0.922 | 0.792 | −0.130 |
| B — bucket-aware (drop tool_selection/stop_decision in optional/none) | 0.796 | 0.800 | 0.644 | −0.156 |
| C — B + posture-aware must (necessary-tool ⊆ called) | 0.796 | 0.800 | 0.680 | −0.120 |
| D — C + relax efficiency (full fix) | 0.796 | 0.800 | 0.690 | −0.110 |

The full fix (D) closes ~41% of the gap (0.188 → 0.110) but does not eliminate it; the residual 0.110 is consistent with MiniMax-M3's genuine outcome deficits (the outcome-only variant A already leaves a −0.13 gap). The components contribute differently: the bucket-aware step (B) alone barely helps MiniMax-M3, because its failures concentrate in the must bucket where the process penalty remains; the posture-aware must step (C) and the efficiency relaxation (D) do most of the work. Under D, MiniMax-M3's single-pass rate (0.544) is on par with the DeepSeek models (0.53/0.51), indicating the residual mean gap comes from a minority of genuinely failed trials rather than a uniform deficit. This decomposition is the quantitative evidence that process grading *inflates* a modest outcome deficit into a large rule gap rather than reflecting it faithfully — and it cleanly separates the two quantities (posture vs. capability) that a single scalar score otherwise confounds.

### 5.6 Statistical significance

We bound the uncertainty of the headline gap with cluster-bootstrap resampling (10,000 draws, resampling whole tasks, fixed seed 42) and a paired McNemar test on trial-0 pass rates (threshold 0.75).

| Quantity (MiniMax-M3 − V4-Pro) | estimate | 95% CI |
|---|:--:|:--:|
| rule gap (90 trials) | −0.189 | [−0.262, −0.117] |
| rule gap (trial 0, 30 tasks) | −0.163 | [−0.257, −0.069] |
| LLM-judge gap | +0.034 | [−0.034, +0.103] |
| gap inflation (rule − LLM) | −0.197 | [−0.315, −0.081] |

The rule gap is significantly negative (CI excludes 0), the LLM-judge gap is not (CI brackets 0), and their difference — the inflation — is itself significant (CI excludes 0). McNemar confirms the asymmetry: MiniMax-M3 has 15 tasks where the rule grader fails but the LLM judge passes, versus 1 in the opposite direction (p = 0.0005); the DeepSeek models show a weaker version of the same signature (Flash c=8/b=1, p = 0.039; V4-Pro c=5/b=1, p = 0.219). The two graders therefore do not disagree by a constant offset — they disagree asymmetrically in exactly the direction that punishes over-exploration, which is the quantitative backbone of the gap-inflation claim.

## 6. Proposed Fix

**Tool-dependency annotation.** We annotate each task must/optional/none (§3.1). The rule grader then applies the `tool_selection` and `stop_decision` penalties only in the **must** bucket — where a missing tool call *is* a failure — and drops them in optional/none, where a direct answer or a clarification is a legitimate path.

**Posture-aware scoring.** In the must bucket, replace exact-sequence match with two outcome-oriented checks: (i) was the *necessary* tool called at least once (not the *exact* sequence), and (ii) is the final answer grounded (sourced from a tool return) and complete. This credits a MiniMax-style cross-checking trace and a Flash-style clarifying trace, as long as the required tool was eventually called with correct arguments.

We release the annotation schema (JSON) and the modified grader so the community can apply it to existing tool benchmarks without re-annotating from scratch.

## 7. Limitations and Honest Boundaries

- **Sample size.** 30 tasks, 3 trials each. The optional bucket has only 3 tasks; bucket-level conclusions are directional, not statistically significant (no bootstrap/McNemar yet).
- **Self-preference.** DeepSeek-V4-Pro is both an agent and the judge. We cross providers for MiniMax but not for the DeepSeek agents; LLM scores are a *relative* reference, not ground truth.
- **Synthetic, single-domain.** One hospital scenario; external validity to finance/coding is untested.
- **Mock date brittleness does not explain over-explore.** Our mock `query_doctor_schedule` originally matched only a literal "周四", not "本周四"/full dates. We fixed this via date normalization and re-ran MiniMax-M3 (90 trials): its over-explore rate moved only 80.0% → 77.8% (−2.2 pp), with just ~2 of 72 over-exploring trials converting. Over-exploration is therefore genuine model behavior (extra location queries; repeatedly retrying "today" instead of clarifying once), not a mock artifact — which strengthens rather than undermines our thesis.
- **Dual family, not a market.** Three models across two families demonstrate the phenomenon but do not bound it. The registered model set has been expanded to five independently-trained families, all obtainable in mainland China without US-vendor APIs: DeepSeek (Flash, V4-Pro), MiniMax (M3, M2.5), Qwen (self-hosted 32B/8B on an NVIDIA H20 via vLLM, plus the 3.5–3.8 cloud line — Max/Plus/Flash tiers — via the Alibaba DashScope API), Kimi (K3, K2.7-Code), and GLM (5.3, 5.3-Prime, 5.2). Note that Qwen3-Max was retired by Alibaba on 2026-10-10 and is replaced by Qwen3.8-Max in our registry. Re-running the 100-sample benchmark across this set is pending API quota.

## 8. Conclusion

We show that tool-calling evaluation with a single canonical tool-sequence systematically mis-scores capable agents: it rewards reproducing one posture and punishes two others that are equally valid, producing a large, statistically significant rule gap that an LLM judge does not corroborate for the over-exploring model in our study. Because the disagreement between graders is *directional* — process-strict/outcome-lenient vs. the reverse — no single scalar "bias" term captures it. Our fix, tool-dependency annotation plus posture-aware scoring, confines process penalties to where they are justified, and an ablation shows it recovers most (though not all) of the inflated gap. We hope this motivates a shift in tool-agent evaluation from "match the canonical trace" to "reach a grounded, completed answer."

---

## Appendix A. Implementation notes

- **A.1** MiniMax-M3 emits `<think>…</think>` inside `content` (its `reasoning_content` field is None). We strip the block with a regex before grading final answers.
- **A.2** Determinism: the rule grader is pure Python and validated by pytest; all numbers above are reproducible from `run_multimodel.py` + `analyze_multimodel.py`.
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
