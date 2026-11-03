# Evaluation_agent research package

建议阅读：`EvaluationAgent_Research_Plan_ZH.pdf` → `EvaluationAgent_Manuscript.pdf` → `CLAUDE_CODE_TASK.md`。同名 DOCX 用于改稿，`Manuscript.md` 与 `Research_Plan_ZH.md` 适合 Claude Code 与版本管理。正式两领域实验尚未执行，正文区分已完成与计划。

包含四张审计/协议图、机器可读复核结果、35 条完整反例、离线复现脚本、契约/标注示例。示例 schema 是设计，不是已实现功能。没有新付费模型调用，没有全新模型训练。

## 在包根目录复现

需要 Python 3、NumPy、SciPy、Matplotlib。获得固定版本的隔离 checkout：

```bash
git clone https://github.com/terrense/Evaluation_agent.git Evaluation_agent_audit
git -C Evaluation_agent_audit checkout 1422f412f25fd55a282e4551739a24e7deb3649f
python repro/audit_repo.py --repo Evaluation_agent_audit --out analysis_reproduced
python repro/run_diagnostics.py --repo Evaluation_agent_audit --out analysis_reproduced
python repro/make_figures.py --analysis analysis_reproduced --out figures_reproduced
```

不需要模型密钥。纯评分函数使用 GraderScore 替身，不等于框架集成测试。原数据缺少生成指纹，不能保证重新调用端点精确恢复原模型输出。构造反例不是部署错误率估计。

不重新分发第三方论文全文或整个上游仓库；请遵守各原始许可证。新契约、独立人工标签、强基线和跨域实验仍需按方案实施。
