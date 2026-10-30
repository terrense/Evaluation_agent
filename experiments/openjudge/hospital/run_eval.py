# -*- coding: utf-8 -*-
"""主评测：8 个 rule-based grader × 30 条样本，输出 JSONL/CSV/MD/图。

用法：PYTHONIOENCODING=utf-8 python run_eval.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd

from openjudge.graders.function_grader import FunctionGrader
from openjudge.graders.schema import GraderMode
from openjudge.runner.grading_runner import GradingRunner

from samples import SAMPLES
from graders_rule import RULE_GRADERS

REPORT_DIR = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DIMENSION_LABELS = {
    "intent_accuracy": "Intent Accuracy",
    "tool_selection": "Tool Selection",
    "argument_correctness": "Argument Correctness",
    "task_completion": "Task Completion",
    "groundedness": "Groundedness",
    "safety": "Safety",
    "trajectory_efficiency": "Trajectory Efficiency",
    "stop_decision": "Stop Decision",
}


def build_runner() -> GradingRunner:
    configs = {}
    for name, fn in RULE_GRADERS.items():
        configs[name] = FunctionGrader(
            func=fn, name=name, mode=GraderMode.POINTWISE,
            description=DIMENSION_LABELS[name],
        )
    return GradingRunner(grader_configs=configs, max_concurrency=8, show_progress=False)


async def main() -> None:
    runner = build_runner()
    # SAMPLES 每条含 task_id/scenario/input/trajectory/expected，grader 只取 trajectory/expected
    results = await runner.arun(SAMPLES)

    # results: {grader_name: [30 个 GraderScore]}
    rows = []          # CSV 汇总
    jsonl_lines = []   # 逐样本明细

    for i, sample in enumerate(SAMPLES):
        row = {"task_id": sample["task_id"], "scenario": sample["scenario"], "input": sample["input"]}
        detail = {
            "task_id": sample["task_id"], "scenario": sample["scenario"],
            "input": sample["input"], "trajectory": sample["trajectory"],
            "scores": {},
        }
        for dim in RULE_GRADERS:
            r = results[dim][i]
            row[dim] = r.score
            detail["scores"][dim] = {"score": r.score, "reason": r.reason, "metadata": r.metadata}
        rows.append(row)
        jsonl_lines.append(json.dumps(detail, ensure_ascii=False))

    # ── 输出 1：JSONL ──
    jsonl_path = REPORT_DIR / "samples_detail.jsonl"
    jsonl_path.write_text("\n".join(jsonl_lines) + "\n", encoding="utf-8")

    # ── 输出 2：CSV ──
    df = pd.DataFrame(rows)
    df["avg_score"] = df[list(RULE_GRADERS)].mean(axis=1).round(3)
    csv_path = REPORT_DIR / "scores_summary.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # ── 输出 3：Markdown 报告 ──
    md = build_markdown(df)
    md_path = REPORT_DIR / "report.md"
    md_path.write_text(md, encoding="utf-8")

    # ── 输出 4：图表 ──
    plot_path = REPORT_DIR / "metrics.png"
    plot_metrics(df, plot_path)

    # ── 控制台摘要 ──
    print("=== 维度平均分 ===")
    for dim in RULE_GRADERS:
        print(f"  {DIMENSION_LABELS[dim]:<24}: {df[dim].mean():.3f}")
    print(f"\n=== 输出文件 ===")
    for p in [jsonl_path, csv_path, md_path, plot_path]:
        print(f"  {p}")


def build_markdown(df: pd.DataFrame) -> str:
    lines = ["# OpenJudge 医院导诊 Agent 评测报告（rule-based Grader）", ""]
    lines.append(f"- 样本数：{len(df)}，场景 {df['scenario'].nunique()} 类")
    lines.append(f"- 整体平均分：{df['avg_score'].mean():.3f}")
    lines.append("")
    lines.append("## 各维度平均分")
    lines.append("")
    lines.append("| 维度 | 平均分 |")
    lines.append("|---|:--:|")
    for dim, label in DIMENSION_LABELS.items():
        lines.append(f"| {label} | {df[dim].mean():.3f} |")
    lines.append("")
    lines.append("## 失败样本明细（总分 < 0.75）")
    lines.append("")
    lines.append("| task_id | 场景 | 输入 | 失败维度 |")
    lines.append("|---|---|---|---|")
    for _, r in df.iterrows():
        failed = [DIMENSION_LABELS[d] for d in RULE_GRADERS if r[d] < 1.0]
        if r["avg_score"] < 0.75:
            lines.append(f"| {r['task_id']} | {r['scenario']} | {r['input'][:20]} | {', '.join(failed)} |")
    lines.append("")
    return "\n".join(lines)


def plot_metrics(df: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    dims = list(RULE_GRADERS)
    means = [df[d].mean() for d in dims]
    labels = [DIMENSION_LABELS[d] for d in dims]

    axes[0].barh(labels, means, color="#4C78A8")
    axes[0].set_xlim(0, 1)
    axes[0].set_title("Mean score per dimension")
    axes[0].invert_yaxis()
    for i, v in enumerate(means):
        axes[0].text(v + 0.02, i, f"{v:.2f}", va="center")

    # 失败类别分布：每个 scenario 中失败（avg<1）样本数
    fail_counts = df[df["avg_score"] < 1.0]["scenario"].value_counts()
    axes[1].bar(fail_counts.index, fail_counts.values, color="#E45756")
    axes[1].set_title("Non-perfect samples per scenario")
    axes[1].tick_params(axis="x", rotation=45)
    plt.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    asyncio.run(main())
