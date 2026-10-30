# -*- coding: utf-8 -*-
"""模型对比：deepseek-flash vs deepseek-v4-pro 驱动的真实 Agent。

读两个目录的评测结果，对比关键指标，画图，生成对比报告。
用法：python model_compare.py（需先跑完两个模型：real_eval + real_eval_pro）
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from make_report import compute_metrics, DIMS, DIM_LABELS

BASE = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
OUT = BASE / "model_compare"
OUT.mkdir(parents=True, exist_ok=True)
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def load(name: str) -> tuple:
    d = BASE / name
    traces = [json.loads(l) for l in open(d / "real_traces.jsonl", encoding="utf-8")]
    rule = json.load(open(d / "rule_scores.json", encoding="utf-8"))
    llm = [json.loads(l) for l in open(d / "llm_scores.jsonl", encoding="utf-8")]
    return traces, rule, llm


def compare_metrics(a: dict, b: dict) -> dict:
    keys = ["single_pass_rate", "pass_at_3", "pass_hat_3",
            "rule_overall", "llm_overall", "avg_turns",
            "tool_success_rate", "n_tool_calls", "n_tool_errors"]
    out = {}
    for k in keys:
        out[k] = {"flash": a[k], "pro": b[k]}
    return out


def plot_compare(flash: dict, pro: dict) -> None:
    # 图 1：关键指标对比
    keys = [("single_pass_rate", "单次通过率"), ("pass_at_3", "Pass@3"),
            ("pass_hat_3", "Pass^3"), ("rule_overall", "Rule总分"),
            ("llm_overall", "LLM总分"), ("tool_success_rate", "工具成功率")]
    x = range(len(keys))
    fv = [flash[k] for k, _ in keys]
    pv = [pro[k] for k, _ in keys]
    fig, ax = plt.subplots(figsize=(10, 5))
    w = 0.35
    ax.bar([i - w/2 for i in x], fv, w, label="deepseek-flash", color="#4C78A8")
    ax.bar([i + w/2 for i in x], pv, w, label="deepseek-v4-pro", color="#E45756")
    ax.set_xticks(list(x))
    ax.set_xticklabels([lbl for _, lbl in keys])
    ax.set_ylim(0, 1)
    ax.legend()
    ax.set_title("flash vs v4-pro 关键指标对比")
    for i in x:
        ax.text(i - w/2, fv[i] + 0.02, f"{fv[i]:.2f}", ha="center", fontsize=9)
        ax.text(i + w/2, pv[i] + 0.02, f"{pv[i]:.2f}", ha="center", fontsize=9)
    plt.tight_layout()
    fig.savefig(FIG / "key_metrics.png", dpi=120)
    plt.close(fig)

    # 图 2：8 维 LLM 分数雷达图（LLM-as-Judge 独立打分，更能反映 Agent 质量）
    angles = [i / len(DIMS) * 2 * math.pi for i in range(len(DIMS))] + [0]
    fig = plt.figure(figsize=(7, 7))
    ax = fig.add_subplot(111, polar=True)
    fv = [flash["dim_llm_mean"][d] for d in DIMS] + [flash["dim_llm_mean"][DIMS[0]]]
    pv = [pro["dim_llm_mean"][d] for d in DIMS] + [pro["dim_llm_mean"][DIMS[0]]]
    ax.plot(angles, fv, label="flash", color="#4C78A8", linewidth=2)
    ax.fill(angles, fv, alpha=0.15, color="#4C78A8")
    ax.plot(angles, pv, label="v4-pro", color="#E45756", linewidth=2)
    ax.fill(angles, pv, alpha=0.15, color="#E45756")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([DIM_LABELS[d] for d in DIMS])
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    ax.set_title("8 维 LLM-as-Judge 评分对比")
    fig.savefig(FIG / "radar_compare.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def build_report(flash: dict, pro: dict, cmp: dict) -> str:
    L = ["# 模型对比报告：deepseek-flash vs deepseek-v4-pro\n"]
    L.append(f"> 同一 30 样本 × 3 trial，双 Grader 评分。Agent 模型不同，Judge 均为 `deepseek-v4-pro`。\n")
    L.append("## 1. 关键指标\n")
    L.append("| 指标 | flash | v4-pro | 差异 |")
    L.append("|---|:--:|:--:|:--:|")
    for k, v in cmp.items():
        d = v["pro"] - v["flash"]
        arrow = "▲" if d > 0.01 else ("▼" if d < -0.01 else "—")
        L.append(f"| {k} | {v['flash']:.3f} | {v['pro']:.3f} | {arrow} {d:+.3f} |")
    L.append("")
    L.append("## 2. 8 维 LLM-as-Judge 评分对比\n")
    L.append("| 维度 | flash | v4-pro | 差异 |")
    L.append("|---|:--:|:--:|:--:|")
    for d in DIMS:
        f = flash["dim_llm_mean"][d]
        p = pro["dim_llm_mean"][d]
        arrow = "▲" if p > f + 0.01 else ("▼" if p < f - 0.01 else "—")
        L.append(f"| {DIM_LABELS[d]} | {f:.3f} | {p:.3f} | {arrow} {p-f:+.3f} |")
    L.append("")
    L.append("## 3. 结论\n")
    overall_diff = pro["llm_overall"] - flash["llm_overall"]
    if overall_diff > 0.02:
        L.append(f"v4-pro 在 LLM-as-Judge 总分上领先 flash **{overall_diff:+.3f}**，更强的模型在此任务上表现更好。")
    elif overall_diff < -0.02:
        L.append(f"flash 反超 v4-pro **{-overall_diff:+.3f}**，说明此任务不需要更强的推理模型。")
    else:
        L.append(f"两模型 LLM-as-Judge 总分接近（差 {overall_diff:+.3f}），此任务对模型能力不敏感。")
    L.append(f"\nPass@3（flash {flash['pass_at_3']:.3f} vs pro {pro['pass_at_3']:.3f}）"
             f"与 Pass^3（flash {flash['pass_hat_3']:.3f} vs pro {pro['pass_hat_3']:.3f}）"
             f"反映的是「单次能力」与「稳定可靠」两个不同维度。\n")
    L.append("## 4. 图表\n")
    L.append("![关键指标](figures/key_metrics.png)")
    L.append("![8维雷达](figures/radar_compare.png)\n")
    return "\n".join(L)


def main() -> None:
    print("=== 读取 flash 结果 ===")
    ft, fr, fl = load("real_eval")
    flash = compute_metrics(fr, fl, ft)
    print("=== 读取 v4-pro 结果 ===")
    pt, pr, pl = load("real_eval_pro")
    pro = compute_metrics(pr, pl, pt)

    cmp = compare_metrics(flash, pro)
    (OUT / "compare_metrics.json").write_text(json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 关键指标对比 ===")
    for k, v in cmp.items():
        print(f"  {k:<20} flash={v['flash']:.3f}  pro={v['pro']:.3f}  diff={v['pro']-v['flash']:+.3f}")

    plot_compare(flash, pro)
    report = build_report(flash, pro, cmp)
    (OUT / "compare_report.md").write_text(report, encoding="utf-8")
    print(f"\n✅ 对比报告 → {OUT / 'compare_report.md'}")


if __name__ == "__main__":
    main()
