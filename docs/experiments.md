# 实验设计

> 每个实验回答 8 个问题：为什么 / 理论预期 / 关键源码 / 怎样运行 / 实际输出 / 如何解释 / 如何证明可信 / 如何改进。

## 实验 E1：OpenJudge 医院导诊评测（Phase 2）

- **为什么**：验证 OpenJudge 核心 API（FunctionGrader→GradingRunner），并搭建 8 维 rule-based grader 评测医院导诊 Agent。
- **理论预期**：FunctionGrader 接受自定义函数返回 GraderScore；GradingRunner 并发跑 grader×sample；8 维 grader 能区分正确/错误轨迹。
- **关键源码**：`openjudge/graders/function_grader.py`、`runner/grading_runner.py`、`graders/schema.py`；我的实现 `experiments/openjudge/hospital/`。
- **运行**：`cd experiments/openjudge/hospital && python run_eval.py`（openjudge venv）。
- **实际输出**：8 维平均分（Safety 0.967、Task Completion 0.700 等），JSONL/CSV/MD/PNG 四类报告。
- **如何解释**：Task Completion 最低（0.700）因为 30 样本里 10 类是错误轨迹；Safety 最高因为只有 H025 一条越权。
- **如何证明可信**：`test_grader.py` 17 个断言校验 grader 判定==ground truth（发现并修复 2 个 grader bug 后全通过）。
- **改进**：LLM-as-Judge 补语义维度（导错科室 H002 这类规则抓不到）。

## 实验 E2：LLMGrader 链路验证（Phase 2）

- **为什么**：无 LLM API 时，验证 LLM-as-Judge 骨架可用（prompt 构造 + structured output 解析）。
- **理论预期**：LLMGrader 用 template 注入 input/trajectory，structured_model 解析 LLM JSON 输出，score/reason 进 GraderScore，其余进 metadata。
- **关键源码**：`openjudge/graders/llm_grader.py`（`_aevaluate` 的 parsed 提取逻辑）。
- **运行**：`python 02_llmgrader_smoke.py`（fake model 替代真实 API）。
- **实际输出**：score=0.85，metadata 含 intent_accuracy=0.9/safety=1.0，prompt 注入验证通过。
- **如何证明可信**：断言 fake model 收到正确 messages + structured_model，解析结果正确。
- **改进**：接入真实 API（`.env`），端到端跑 LLM-as-Judge。

## 实验 E3：claw-eval 轻量实验（Phase 3）

- **为什么**：claw-eval 完整运行需 LLM API + mock services，改用轻量等价物验证评分方法学。
- **理论预期**：safety 乘子清零越权；Pass@3（至少一次）远高于 Pass^3（三次都成功）。
- **关键源码**：`claw_eval/models/scoring.py`（compute_task_score/pass@k/pass^k，真实复用）。
- **运行**：`cd experiments/claweval && python lightweight.py`（claweval venv）。
- **实际输出**：L02 越权 → safety=0 → 总分 0.00；Pass@3=1.0 vs Pass^3=0.296；6 种 failure 全覆盖。
- **如何解释异常**：L03 初版 completion 恒 0.5，因为 expected_state 混入了语义 flag「adapted_to_change」——确定性 completion 只能依赖可观测状态。
- **如何证明可信**：评分公式对已知 DimensionScores 验证数值正确。
- **改进**：接真实 LLM Agent，用真实 mock services（fastapi）。

## 实验 E4：AI-Infra-Guard 静态预扫描（Phase 4）

- **为什么**：验证 skill-scan 静态预扫描（无 LLM 可真实运行），检测 6 类安全用例。
- **理论预期**：明显高危模式（curl|bash、云元数据、提示注入）被正则命中；正常 Skill 被放过。
- **关键源码**：`skill-scan/skill_scan/utils/pre_scan.py`（13 种正则 + 字节码/编码检测）。
- **运行**：`cd experiments/aiginfra && python generate_testcases.py && python run_security_scan.py`（aig venv）。
- **实际输出**：5 TP + 1 TN，recall=1.0 FPR=0.0。
- **如何解释异常**：结果「过于干净」因为用例是教科书式明显模式——真实攻击会混淆绕过正则，故 pre_scan 定位「提示」非「定论」。
- **如何证明可信**：真实调用上游 `pre_scan()` 源码，非自写正则。
- **改进**：加 base64/混淆绕过样本测试漏报边界；接 LLM 完整审计。

## 实验 E5：四方案对比 + RQ（Phase 5/6）

- **为什么**：量化「只看最终文本 vs 轨迹+确定性」的漏判差异，回答 RQ1/RQ3/RQ5。
- **理论预期**：outcome-only 漏判虚构/越权；Pass^3 比 Pass@3 敏感；hard gate 减漏判增误判。
- **关键源码**：`experiments/lab/four_methods.py`、`rq_experiments.py`。
- **运行**：`cd experiments/lab && python four_methods.py && python rq_experiments.py`。
- **实际输出**：方案 A 漏判 0.667 vs 方案 C 0.333；hard gate 漏判 0.167 但误判 0.222。
- **如何解释异常**：H028/H030（虚构）被平均分稀释——单一维度严重错误需 hard gate 而非加权。
- **如何证明可信**：ground truth（BAD_IDS）显式定义，漏判/误判可复算。
- **改进**：接真实 LLM 补语义维度（RQ2/RQ4/RQ6）。
