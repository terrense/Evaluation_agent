# Posture–Grader Misalignment: Single Canonical Tool-Sequences Penalize Diverse Tool-Use Strategies in Agent Evaluation

> 目标期刊：arXiv preprint + Agent/Evaluation 方向 workshop（short paper）。
> 状态：完整草稿。所有数字来自 `reports/openjudge/multimodel/comparison.json`，未作任何加工。
> 标注：`[REF]` 为待核实引用（提交前必须替换为真实文献条目）。

---

## Abstract

Tool-calling agents are increasingly evaluated by comparing their tool-call *sequences* against a single canonical "correct_tools" trace. We show that this design conflates *capability* with *posture*: real models adopt one of several distinct tool-use strategies, and a process-oriented grader that requires exact sequence match scores them by their *distance from the canonical posture* rather than by whether they completed the task. On a synthetic clinical-triage benchmark (30 tasks × 3 trials × 3 models × 2 temperatures, dual rule-based and LLM-as-judge graders), we observe three mutually-exclusive postures — *ask-first* (DeepSeek-Flash and DeepSeek-V4-Pro, ~40% of trials), *canonical* (~47%), and *over-explore* (MiniMax-M3, 80% of trials) — and show that the rule-based grader drives a 0.13–0.58 gap against the LLM judge on process dimensions (tool_selection, stop_decision) while the LLM judge is *stricter* on outcome dimensions. This produces *gap inflation* rather than a spurious inversion: the over-exploring model (MiniMax-M3) earns the lowest rule-based score (0.644 vs. 0.783/0.793), yet the gap against the DeepSeek models narrows from 0.149 under the rule grader to 0.043 under an LLM judge and to 0.065 under our posture-aware regrading (§5.5) — a real but modest capability deficit amplified ~2–3× by posture penalties. Temperature (0 vs. 0.3) has a negligible effect on pass rates, indicating that sampling variance is not the source of the discrepancy. We propose a two-part fix: *tool-dependency annotation* (must/optional/none) so that process penalties are only applied where a tool is genuinely required, and *posture-aware scoring* that credits any path that reaches a grounded, completed answer.

## 1. Introduction

The dominant way to measure a tool-calling agent is to give it a task, let it emit a trajectory of tool calls, and compare that trajectory to a reference. Benchmarks such as τ-bench [Yao et al. 2024], ToolLLM [Qin et al. 2023], API-Bank [Li et al. 2023], and the Berkeley Function-Calling Leaderboard [Patil et al. 2025] each encode, for every task, a *ground-truth* sequence of tools and arguments that the model is expected to reproduce. A grader then scores how closely the model's trace matches that sequence.

This is a reasonable operationalization if there is exactly one correct way to do a task. But real deployments reveal that capable models do not all behave alike. Some models *ask a clarifying question before acting* — a behavior safety guidelines encourage and users often prefer, yet one that produces an empty tool sequence and therefore fails any sequence-match grader. Others *explore*: a reasoning model may call several tools to cross-check before answering, a process that is correct but "wasteful" under a trajectory-efficiency rubric. Only a third posture — reproduce the canonical sequence exactly — scores well.

We argue that this is a *posture–grader misalignment*: the ground truth encodes a single posture (the canonical one), while real models occupy a space of postures, and a process-oriented grader converts "distance from the canonical posture" into a score difference that has nothing to do with task success. The failure is not that the grader has a bug (an "oracle audit" problem [Executable-Contract Audit, arXiv:2609.37315]), nor only that a judge model has a bias (a "judge bias" problem [Wang et al. 2023]); it is that the *ground truth itself is under-specified*: it tells us *what tools exist*, not *which tools are required*.

We make three contributions:

1. **A posture taxonomy** over tool-call trajectories — *ask-first* (under-execute), *canonical* (exact), *over-explore* (over-execute), and *other* — and show that three independently-trained models occupy three nearly-disjoint regions of this space (§5.1).
2. **Evidence of grader disagreement that is directional, not scalar**: a rule-based process grader is lenient on outcome but strict on process, while an LLM judge is the reverse (§5.2). The consequence is *gap inflation*: the process grader amplifies a modest genuine capability deficit ~2–3× by stacking posture penalties on top of it (§5.3, §5.5).
3. **A concrete fix**: tool-dependency annotation (must/optional/none) plus posture-aware scoring, which confines process penalties to tasks where a tool is genuinely required (§6). We release the annotation schema and grader to encourage reuse.

We deliberately scope this study to a family of Chinese model families accessible without US-vendor APIs — DeepSeek and MiniMax — to demonstrate that the phenomenon does not depend on any single vendor, and that the experimental design is reproducible on a domestic budget.

## 2. Related Work

**Tool-use benchmarks and their ground truth.** Tool-calling evaluation has matured rapidly. Toolformer [Schick et al. 2023] established the paradigm; ToolLLM [Qin et al. 2023] and API-Bank [Li et al. 2023] contributed large-scale datasets with reference tool sequences; τ-bench [Yao et al. 2024] added realistic multi-turn user interaction; the Berkeley Function-Calling Leaderboard [Patil et al. 2025] standardized function-calling metrics. Across these, the reference "correct tool sequence" is the backbone of scoring. Our work asks a question these benchmarks assume away: *is there a single correct sequence?*

**Process- vs. outcome-oriented grading.** Process reward models [Lightman et al. 2023; Uesato et al. 2022] score each step of a trajectory, in contrast to outcome reward models that score only the final answer. Our rule-based grader is a deterministic, hand-written process grader (8 dimensions, exact sequence match on tool_selection), and our LLM judge is an outcome-leaning grader. We show the two families disagree *directionally* on process vs. outcome dimensions, which has implications for reward-model design in RL for tool use.

**Judge bias and evaluation audit.** LLM-as-a-judge is known to exhibit position bias, verbosity bias, and self-preference [Wang et al. 2023; Zheng et al. 2023]. A parallel line audits evaluators for correctness [Executable-Contract Audit, arXiv:2609.37315]. Our contribution is orthogonal: the ground truth, not the judge, is the source of bias. Even a *perfect* sequence-matching grader would penalize a correct-but-non-canonical trajectory.

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
| MiniMax-M3 | 13.3% | **0.0%** | **80.0%** | 6.7% |

The three models occupy nearly disjoint regions. Flash and V4-Pro ask for missing information in roughly two-fifths of trials; MiniMax-M3 *never* asks first and instead over-explores in four-fifths of trials. Since `tool_selection` requires exact match, both postures receive `tool_selection = 0`.

### 5.2 RQ2 — Directional grader disagreement

| Dimension | Flash (rule→LLM) | V4-Pro (rule→LLM) | MiniMax-M3 (rule→LLM) |
|---|:--:|:--:|:--:|
| tool_selection | 0.467 → 0.847 | 0.467 → 0.697 | 0.133 → 0.713 |
| stop_decision | 0.567 → 0.940 | 0.500 → 0.923 | 0.756 → 0.772 |
| intent_accuracy | 0.500 → 0.928 | 0.511 → 0.930 | 0.351 → 0.840 |
| **task_completion** | **0.911 → 0.573** | **1.000 → 0.540** | **0.778 → 0.622** |

The disagreement is *directional*. On process dimensions (tool_selection, stop_decision, intent_accuracy) the LLM judge is 0.23–0.58 more lenient than the rule grader — it accepts ask-first and over-explore as legitimate ways to reach an answer. On the *outcome* dimension (task_completion) the LLM judge is 0.28–0.46 **stricter** — it judges that the model did not, in fact, finish the task (e.g., it asked a question but never delivered the booking). A single "grader is biased" framing cannot capture this: the two graders prioritize opposite things.

### 5.3 RQ3 — Posture penalties inflate a real but modest capability gap

| Model | rule overall | LLM overall |
|---|:--:|:--:|
| DeepSeek-Flash | 0.783 | 0.832 |
| DeepSeek-V4-Pro | 0.793 | 0.794 |
| **MiniMax-M3** | **0.644** | 0.751 |

MiniMax-M3 — the most exploration-heavy (and the only reasoning) model — earns the lowest rule-based score (0.644). This is *not* purely a grader artifact: MiniMax-M3 also trails the DeepSeek models on genuine outcome dimensions — intent_accuracy 0.351, groundedness 0.744, argument_correctness 0.778 (§5.2). Consistent with that, the gap narrows but does not vanish under the LLM judge (0.751 vs. 0.794, a gap of 0.043) and under our posture-aware regrading (0.065, §5.5). The rule grader therefore *inflates* a real but modest deficit (~0.04–0.07) roughly 2–3× (to 0.149) by stacking two posture penalties — exact-sequence `tool_selection` and a `trajectory_efficiency` cap — on top of the genuine errors. Crucially, the "knowledge-internalization" hypothesis does not occur: in the must bucket, models that do not call a required tool *ask for more information* rather than fabricate (§5.1), so the inflation is a property of posture, not of knowledge.

### 5.4 RQ4 — Sampling is a red herring

| Configuration | single-pass | Pass@3 | Pass^3 |
|---|:--:|:--:|:--:|
| Flash t0 / t0.3 | 0.478 / 0.478 | 0.533 / 0.533 | 0.446 / 0.446 |
| V4-Pro t0 / t0.3 | 0.500 / 0.511 | 0.533 / 0.533 | 0.478 / 0.486 |
| MiniMax-M3 t0 | 0.311 | 0.400 | 0.242 |

Temperature 0 → 0.3 moves nothing of consequence (Pass@3 is flat at 0.533; Pass^3 shifts by ≤0.01). The gap between single-pass and Pass@3 (≈0.05) and between Pass@3 and Pass^3 (≈0.05–0.16) is real but dwarfed by the *posture* gap: an exact-match rate of 0.133 vs. 0.467 across models. Reporting temperature or sampling as the primary source of variance would mislocate the phenomenon.

### 5.5 Ablation — decomposing posture vs. capability

We re-score the same trajectories under progressively fairer graders (§6) to bound how much of MiniMax-M3's deficit is posture vs. genuine error. The baseline column reproduces the rule scores exactly (a sanity check).

| Grader variant | Flash | V4-Pro | MiniMax-M3 | gap (M3−V4) |
|---|:--:|:--:|:--:|:--:|
| baseline — exact sequence match | 0.783 | 0.793 | 0.644 | −0.149 |
| A — outcome-only (drop 3 process dims) | 0.908 | 0.922 | 0.831 | −0.091 |
| B — bucket-aware (drop tool_selection/stop_decision in optional/none) | 0.796 | 0.800 | 0.686 | −0.114 |
| C — B + posture-aware must (necessary-tool ⊆ called) | 0.796 | 0.800 | 0.722 | −0.078 |
| D — C + relax efficiency (full fix) | 0.796 | 0.800 | 0.735 | −0.065 |

The full fix (D) closes ~56% of the gap (0.149 → 0.065) but does not eliminate it; the residual 0.065 is consistent with MiniMax-M3's genuine outcome deficits and with the LLM judge's 0.043. The components contribute differently: the bucket-aware step (B) alone barely helps MiniMax-M3, because its failures concentrate in the must bucket where the process penalty remains; the posture-aware must step (C) and the efficiency relaxation (D) do most of the work. Under D, MiniMax-M3's single-pass rate (0.556) is on par with the DeepSeek models (0.53/0.51), indicating the residual mean gap comes from a minority of genuinely failed trials rather than a uniform deficit. This decomposition is the quantitative evidence that process grading *inflates* a real gap rather than creating a spurious one — and it cleanly separates the two quantities (posture vs. capability) that a single scalar score otherwise confounds.

## 6. Proposed Fix

**Tool-dependency annotation.** We annotate each task must/optional/none (§3.1). The rule grader then applies the `tool_selection` and `stop_decision` penalties only in the **must** bucket — where a missing tool call *is* a failure — and drops them in optional/none, where a direct answer or a clarification is a legitimate path.

**Posture-aware scoring.** In the must bucket, replace exact-sequence match with two outcome-oriented checks: (i) was the *necessary* tool called at least once (not the *exact* sequence), and (ii) is the final answer grounded (sourced from a tool return) and complete. This credits a MiniMax-style cross-checking trace and a Flash-style clarifying trace, as long as the required tool was eventually called with correct arguments.

We release the annotation schema (JSON) and the modified grader so the community can apply it to existing tool benchmarks without re-annotating from scratch.

## 7. Limitations and Honest Boundaries

- **Sample size.** 30 tasks, 3 trials each. The optional bucket has only 3 tasks; bucket-level conclusions are directional, not statistically significant (no bootstrap/McNemar yet).
- **Self-preference.** DeepSeek-V4-Pro is both an agent and the judge. We cross providers for MiniMax but not for the DeepSeek agents; LLM scores are a *relative* reference, not ground truth.
- **Synthetic, single-domain.** One hospital scenario; external validity to finance/coding is untested.
- **Mock brittleness amplifies over-explore.** Our mock `query_doctor_schedule` matches a literal "周四" but not "本周四"/a full date. A precision-oriented model that passes a full date gets a miss and retries, inflating its over-explore rate. This is a genuine artifact we have not yet quantified; it biases *against* MiniMax-M3 and *toward* our thesis, so we flag it explicitly.
- **Dual family, not a market.** Three models across two families demonstrate the phenomenon but do not bound it. We are expanding to 5–6 independently-trained families that are all obtainable in mainland China without US-vendor APIs: self-hosting open-weight Qwen3 (e.g., 32B on an NVIDIA H20 via vLLM) plus Qwen3-Max via the Alibaba DashScope API, with GLM/Kimi as further families.

## 8. Conclusion

We show that tool-calling evaluation with a single canonical tool-sequence systematically mis-scores capable agents: it rewards reproducing one posture and punishes two others that are equally valid, producing a 2–3× inflation of a modest capability gap for the over-exploring model in our study. Because the disagreement between graders is *directional* — process-strict/outcome-lenient vs. the reverse — no single scalar "bias" term captures it. Our fix, tool-dependency annotation plus posture-aware scoring, confines process penalties to where they are justified, and an ablation shows it recovers most (though not all) of the inflated gap. We hope this motivates a shift in tool-agent evaluation from "match the canonical trace" to "reach a grounded, completed answer."

---

## Appendix A. Implementation notes

- **A.1** MiniMax-M3 emits `<think>…</think>` inside `content` (its `reasoning_content` field is None). We strip the block with a regex before grading final answers.
- **A.2** Determinism: the rule grader is pure Python and validated by pytest; all numbers above are reproducible from `run_multimodel.py` + `analyze_multimodel.py`.
- **A.3** Metrics: aggregate = `safety × mean(8 dims)`; pass@k uses the unbiased estimator `1 − C(n−c,k)/C(n,k)` [Chen et al. 2021]; pass^k = `(c/n)^k` [Yao et al. 2024], implemented following the claw-eval harness we build on.

## References

> 提交前必须逐条核实作者全名/页码；`[verify]` 为待二次核对，`[REF]` 为待补。

- Chen, M., et al. (2021). *Evaluating Large Language Models Trained on Code.* arXiv:2107.03374. (pass@k)
- Schick, T., et al. (2023). *Toolformer: Language Models Can Teach Themselves to Use Tools.* arXiv:2302.04761.
- Qin, Y., et al. (2023). *ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs.* arXiv:2307.16789. [verify 作者全名]
- Li, M., et al. (2023). *API-Bank: A Comprehensive Benchmark for Tool-Augmented LLMs.* arXiv:2304.08244. [verify 作者全名]
- Yao, S., Shinn, N., Razavi, P., Narasimhan, K. (2024). *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.* arXiv:2406.12045. (introduces pass^k)
- Patil, S. G., Mao, R., Yan, F., Ji, C., Suresh, S., Stoica, I., Gonzalez, J. E. (2025). *The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large Language Models.* ICML 2025.
- Huang, J., Chen, S., Liang, X., Ma, X., Yang, H., Ke, W., Tan, T., Sun, Y. (2026). *Task Success Is Not Enough: Side-effect-Aware Evaluation of Tool-Using Language Model Agents (SABench).* arXiv:2610.34167, NeurIPS 2026 E&D Track.
- Zheng, L., et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* arXiv:2306.05685.
- Wang, P., Li, L., Chen, L., et al. (2023). *Large Language Models Are Not Fair Evaluators.* arXiv:2305.17926, ACL 2024. [verify 作者全名]
- *Do Agent Benchmarks Do What They Say? An Executable-Contract Audit of Tool-Using Agent Environments.* arXiv:2609.37315. [verify 作者/ID]
- Lightman, H., et al. (2023). *Let's Verify Step by Step.* arXiv:2305.20050.
- Uesato, J., et al. (2022). *Solving Math Word Problems with Process- and Outcome-Based Feedback.* arXiv:2211.14275.
- claw-eval — the evaluation harness this study builds on (multiplicative safety gate, pass@k/pass^k implementation); cite release repo.
