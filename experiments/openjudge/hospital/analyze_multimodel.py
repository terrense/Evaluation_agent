# -*- coding: utf-8 -*-
"""多模型 × 温度 × 工具依赖分桶 统一分析 + 报告 + 图。

读 reports/openjudge/ 下各模型配置的原始结果，产出三块：
  实验 A —— 一致性：温度 0 vs 0.3 的 单次/Pass@3/Pass^3 真实差距
  实验 B —— 分桶：按 tool_requirement(must/optional/none) 揭示「工具调用 bias」
  多模型  —— 全部 temp=0 模型 × 8 维对比（在 MODELS 登记即自动并入）

输出：reports/openjudge/multimodel/comparison.md + figures/*.png

状态：当前仅分析已跑出的 3 模型（flash / v4pro / minimax-m3，30 样本）；
22 模型 × 100 样本重跑完成后重写（见 docs/research-brief.md，task #21）。
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

from samples import SAMPLES
from tool_requirement import TOOL_REQUIREMENT, BUCKET_ZH

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
OUT_DIR = REPORTS / "multimodel"
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

DIMS = ["intent_accuracy", "tool_selection", "argument_correctness",
        "task_completion", "groundedness", "safety",
        "trajectory_efficiency", "stop_decision"]
DIM_ZH = {"intent_accuracy": "意图准确", "tool_selection": "工具选择",
          "argument_correctness": "参数正确", "task_completion": "任务完成",
          "groundedness": "有依据", "safety": "安全",
          "trajectory_efficiency": "轨迹高效", "stop_decision": "停止决策"}
BUCKETS = ["must", "optional", "none"]

# (简称, 模型显示名, 相对 reports/openjudge 的目录, 温度)
MODELS = [
    ("flash",          "deepseek-flash",    "multimodel/flash__t0.0",          0.0),
    ("v4pro",          "deepseek-v4-pro",   "multimodel/v4pro__t0.0",          0.0),
    ("minimax-m3",     "MiniMax-M3",        "multimodel/minimax-m3__t0.0",     0.0),
    ("minimax-m2.5",   "MiniMax-M2.5",      "multimodel/minimax-m2.5__t0.0",   0.0),
    ("qwen3-32b",      "Qwen3-32B",         "multimodel/qwen3-32b__t0.0",      0.0),
    ("qwen3-8b",       "Qwen3-8B",          "multimodel/qwen3-8b__t0.0",       0.0),
    ("qwen3.8-max",    "Qwen3.8-Max",       "multimodel/qwen3.8-max__t0.0",    0.0),
    ("qwen3.7-max",    "Qwen3.7-Max",       "multimodel/qwen3.7-max__t0.0",    0.0),
    ("qwen3.8-flash",  "Qwen3.8-Flash",     "multimodel/qwen3.8-flash__t0.0",  0.0),
    ("qwen3.8-2.4t-a95b", "Qwen3.8-2.4T",   "multimodel/qwen3.8-2.4t-a95b__t0.0", 0.0),
    ("qwen3.7-flash",  "Qwen3.7-Flash",     "multimodel/qwen3.7-flash__t0.0",  0.0),
    ("qwen3.7-plus",   "Qwen3.7-Plus",      "multimodel/qwen3.7-plus__t0.0",   0.0),
    ("qwen3.6-plus",   "Qwen3.6-Plus",      "multimodel/qwen3.6-plus__t0.0",   0.0),
    ("qwen3.5-plus",   "Qwen3.5-Plus",      "multimodel/qwen3.5-plus__t0.0",   0.0),
    ("qwen-max",       "Qwen-Max",          "multimodel/qwen-max__t0.0",       0.0),
    ("qwen-plus",      "Qwen-Plus",         "multimodel/qwen-plus__t0.0",      0.0),
    ("qwen-flash",     "Qwen-Flash",        "multimodel/qwen-flash__t0.0",     0.0),
    ("kimi-k3",        "Kimi-K3",           "multimodel/kimi-k3__t0.0",        0.0),
    ("kimi-k2.7-code", "Kimi-K2.7-Code",    "multimodel/kimi-k2.7-code__t0.0", 0.0),
    ("glm-5.3",        "GLM-5.3",           "multimodel/glm-5.3__t0.0",        0.0),
    ("glm-5.3-prime",  "GLM-5.3-Prime",     "multimodel/glm-5.3-prime__t0.0",  0.0),
    ("glm-5.2",        "GLM-5.2",           "multimodel/glm-5.2__t0.0",        0.0),
    ("v4pro-t0.3",     "deepseek-v4-pro",   "multimodel/v4pro__t0.3",          0.3),
    ("flash-t0.3",     "deepseek-flash",    "multimodel/flash__t0.3",          0.3),
]


def aggregate(scores: dict) -> float:
    """safety 乘子 + 8 维平均（复用 claw-eval 语义）。"""
    safety = scores.get("safety", 1.0)
    return safety * (sum(scores.values()) / len(scores))


def _is_pass(s: float, threshold: float = 0.75) -> bool:
    return s >= threshold


def load(model_dir: Path):
    traces = [json.loads(l) for l in open(model_dir / "real_traces.jsonl", encoding="utf-8")]
    rule = json.load(open(model_dir / "rule_scores.json", encoding="utf-8"))
    llm = [json.loads(l) for l in open(model_dir / "llm_scores.jsonl", encoding="utf-8")]
    return traces, rule, llm


def task_trial_scores(rule: dict) -> dict[str, list[float]]:
    """task_id -> [3 个 trial 的 aggregate 分]。"""
    return {tid: [aggregate(rule[tid][str(t)]) for t in range(3)] for tid in rule}


def consistency(rule: dict, threshold: float = 0.75) -> dict:
    """单次通过率 / Pass@3 / Pass^3（基于 3 trial 的 aggregate 分）。"""
    ts = task_trial_scores(rule)
    single = sum(1 for sc in ts.values() for s in sc if _is_pass(s, threshold)) / (len(ts) * 3)
    p3 = phat3 = 0.0
    for sc in ts.values():
        c = sum(1 for s in sc if _is_pass(s, threshold))
        p3 += 1.0 - math.comb(3 - c, 3) / math.comb(3, 3)  # 至少一次
        phat3 += (c / 3) ** 3  # 三次全中
    return {
        "single_pass": single,
        "pass_at_3": p3 / len(ts),
        "pass_hat_3": phat3 / len(ts),
    }


def dim_means(rule: dict) -> dict:
    """8 维 rule 平均（3 trial 全算）。"""
    acc = {d: [] for d in DIMS}
    for tid in rule:
        for t in range(3):
            for d in DIMS:
                acc[d].append(rule[tid][str(t)][d])
    return {d: sum(v) / len(v) for d, v in acc.items()}


def llm_means(llm: list) -> dict:
    return {d: sum(r["dims"][d] for r in llm) / len(llm) for d in DIMS}


def bucket_dims(rule: dict) -> dict[str, dict[str, float]]:
    """每桶 × 每维 的 rule 平均（3 trial 全算）。"""
    out = {b: {d: [] for d in DIMS} for b in BUCKETS}
    for tid in rule:
        b = TOOL_REQUIREMENT[tid]
        for t in range(3):
            for d in DIMS:
                out[b][d].append(rule[tid][str(t)][d])
    return {b: {d: sum(v) / len(v) for d, v in v.items()} for b, v in out.items()}


def correct_but_sequence_mismatch(rule: dict) -> dict[str, int]:
    """每个模型：每桶中「结果正确(有依据+完成)但工具序列不匹配」的 trial 数。

    注意（修正）：tool_selection==0 表示「实际序列 != 期望序列」，包含三种情况——
    零工具追问(under)、额外工具(over)、错误工具(other)。并非「跳过工具」。
    该信号衡量的是「结果对但过程被精确匹配判错」的比例，是 ground-truth 粒度的量化证据。
    """
    out = {b: 0 for b in BUCKETS}
    total = {b: 0 for b in BUCKETS}
    for tid in rule:
        b = TOOL_REQUIREMENT[tid]
        for t in range(3):
            s = rule[tid][str(t)]
            total[b] += 1
            if s["groundedness"] == 1 and s["task_completion"] == 1 and s["tool_selection"] == 0:
                out[b] += 1
    return {"counts": out, "total": total}


def main() -> None:
    rows = []  # 多模型总览
    model_consistency = {}  # 实验 A
    model_bucket = {}  # 实验 B
    model_correct_notool = {}

    for key, disp, rel, temp in MODELS:
        md = REPORTS / rel
        if not (md / "real_traces.jsonl").exists():
            print(f"  [skip] {key}: 缺结果目录 {md}（先跑对应 eval 再分析）")
            continue
        traces, rule, llm = load(md)
        cons = consistency(rule)
        dimr = dim_means(rule)
        diml = llm_means(llm)
        rule_overall = sum(sum(v) for v in task_trial_scores(rule).values()) / (len(rule) * 3)
        llm_overall = sum(r["score"] for r in llm) / len(llm)
        rows.append({
            "key": key, "disp": disp, "temp": temp,
            "single_pass": cons["single_pass"], "pass_at_3": cons["pass_at_3"],
            "pass_hat_3": cons["pass_hat_3"], "rule_overall": rule_overall,
            "llm_overall": llm_overall, "dim_rule": dimr, "dim_llm": diml,
        })
        model_consistency[key] = cons
        model_bucket[key] = bucket_dims(rule)
        model_correct_notool[key] = correct_but_sequence_mismatch(rule)

    # 保存 JSON 供后续/前端复用
    dump = {
        "overview": rows,
        "consistency": model_consistency,
        "bucket": model_bucket,
        "correct_but_sequence_mismatch": model_correct_notool,
    }
    (OUT_DIR / "comparison.json").write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 图 1：三模型 8 维对比（rule，temp=0）──
    t0 = [r for r in rows if r["temp"] == 0.0]
    fig, ax = plt.subplots(figsize=(12, 5))
    x = range(len(DIMS))
    n = len(t0)
    w = 0.8 / n
    for i, r in enumerate(t0):
        vals = [r["dim_rule"][d] for d in DIMS]
        ax.bar([xi + (i - (n - 1) / 2) * w for xi in x], vals, w, label=r["disp"])
    ax.set_xticks(list(x)); ax.set_xticklabels([DIM_ZH[d] for d in DIMS])
    ax.set_ylim(0, 1.05); ax.set_ylabel("rule-based 平均分")
    ax.set_title(f"{n} 模型 × 8 维能力（rule-based，temp=0）")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    plt.tight_layout(); fig.savefig(FIG_DIR / "multi_dim.png", dpi=120); plt.close(fig)

    # ── 图 2：实验 A 一致性（temp 0 vs 0.3）──
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for key, disp in (("v4pro", "v4-pro t0"), ("v4pro-t0.3", "v4-pro t0.3"),
                      ("flash", "flash t0"), ("flash-t0.3", "flash t0.3")):
        c = model_consistency[key]
        ax.plot(["单次", "Pass@3", "Pass^3"], [c["single_pass"], c["pass_at_3"], c["pass_hat_3"]],
                marker="o", label=disp)
    ax.set_ylim(0, 1.05); ax.set_ylabel("通过率")
    ax.set_title("实验 A：温度对一致性的影响（单次 vs Pass@3 vs Pass^3）")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    plt.tight_layout(); fig.savefig(FIG_DIR / "consistency.png", dpi=120); plt.close(fig)

    # ── 图 3：实验 B 分桶（tool_selection vs groundedness，temp=0 三模型）──
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
    n = len(t0)
    w = 0.8 / n
    for bi, b in enumerate(BUCKETS):
        ax = axes[bi]
        for j, r in enumerate(t0):
            bd = model_bucket[r["key"]][b]
            ax.bar([0 + (j - (n - 1) / 2) * w, 1 + (j - (n - 1) / 2) * w],
                   [bd["tool_selection"], bd["groundedness"]], w, label=r["disp"])
        ax.set_title(BUCKET_ZH[b], fontsize=11)
        ax.set_ylim(0, 1.05)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["工具选择", "有依据"], fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.suptitle("实验 B：工具调用 bias —— 分桶下「工具选择」被压低而「有依据」仍高")
    plt.tight_layout(); fig.savefig(FIG_DIR / "bucket_bias.png", dpi=120); plt.close(fig)

    # ── 报告 ──
    L = []
    L.append("# 多模型 × 温度 × 工具依赖分桶 分析报告\n")
    L.append("> 数据：30 样本 × 3 trial，双 Grader（rule 8 维 + LLM-as-Judge）。")
    L.append("> 多模型（temp=0）：" + " / ".join(r["disp"] for r in t0) + "；另有 temp=0.3 一致性实验。\n")

    L.append("## 1. 多模型总览（temp=0）\n")
    L.append("| 模型 | 单次通过 | Pass@3 | Pass^3 | rule 总分 | LLM 总分 |")
    L.append("|---|:--:|:--:|:--:|:--:|:--:|")
    for r in t0:
        L.append(f"| {r['disp']} | {r['single_pass']:.2f} | {r['pass_at_3']:.2f} | "
                 f"{r['pass_hat_3']:.2f} | {r['rule_overall']:.2f} | {r['llm_overall']:.2f} |")
    L.append("")
    L.append("### 8 维对比（rule-based）")
    L.append("| 维度 | " + " | ".join(r["disp"] for r in t0) + " |")
    L.append("|---|" + "|".join(":--:" for _ in t0) + "|")
    for d in DIMS:
        L.append(f"| {DIM_ZH[d]} | " + " | ".join(f"{r['dim_rule'][d]:.2f}" for r in t0) + " |")
    L.append("")
    L.append("![三模型 8 维](figures/multi_dim.png)\n")

    L.append("## 2. 实验 A：温度与一致性\n")
    L.append("| 配置 | 单次通过 | Pass@3 | Pass^3 | 差距(Pass@3−Pass^3) |")
    L.append("|---|:--:|:--:|:--:|:--:|")
    for key, disp in (("v4pro", "v4-pro t0"), ("v4pro-t0.3", "v4-pro t0.3"),
                      ("flash", "flash t0"), ("flash-t0.3", "flash t0.3")):
        c = model_consistency[key]
        L.append(f"| {disp} | {c['single_pass']:.2f} | {c['pass_at_3']:.2f} | "
                 f"{c['pass_hat_3']:.2f} | {c['pass_at_3']-c['pass_hat_3']:+.2f} |")
    L.append("")
    L.append("**解读**：温度=0 时 trial 高度确定，单次≈Pass@3≈Pass^3；")
    L.append("温度>0 引入真实随机性后，Pass@3（至少一次成功）与 Pass^3（三次全成功）显著拉开，")
    L.append("单次通过率不再能代表「稳定可靠」。这直接回答 RQ3。\n")
    L.append("![一致性](figures/consistency.png)\n")

    L.append("## 3. 实验 B：工具依赖度分桶（揭示「能力-评测悖论」）\n")
    L.append("### 3.1 分桶 × 关键维度（rule-based，temp=0）")
    for b in BUCKETS:
        L.append(f"\n**{BUCKET_ZH[b]}**（{len([t for t in TOOL_REQUIREMENT if TOOL_REQUIREMENT[t]==b])} 条样本）")
        L.append("| 模型 | 工具选择 | 有依据 | 任务完成 | 意图 | 停止决策 |")
        L.append("|---|:--:|:--:|:--:|:--:|:--:|")
        for r in t0:
            bd = model_bucket[r["key"]][b]
            L.append(f"| {r['disp']} | {bd['tool_selection']:.2f} | {bd['groundedness']:.2f} | "
                     f"{bd['task_completion']:.2f} | {bd['intent_accuracy']:.2f} | {bd['stop_decision']:.2f} |")
    L.append("")
    L.append("### 3.2 核心信号：`结果正确但工具序列不匹配` 的 trial 数")
    L.append("> 签名 = 有依据=1 且 任务完成=1 且 工具选择=0。")
    L.append("> 注意：工具选择=0 表示「实际序列 != 期望序列」，含三种姿态——零工具追问(under)/额外工具(over)/错误工具(other)，")
    L.append(">       **并非**「跳过工具」。该签名量化的是「结果对、但过程被精确序列匹配判错」的比例。")
    L.append("| 模型 | must | optional | none |")
    L.append("|---|:--:|:--:|:--:|")
    for r in t0:
        cnt = model_correct_notool[r["key"]]["counts"]
        tot = model_correct_notool[r["key"]]["total"]
        L.append(f"| {r['disp']} | {cnt['must']}/{tot['must']} | {cnt['optional']}/{tot['optional']} | {cnt['none']}/{tot['none']} |")
    L.append("")
    L.append("**结论**：")
    L.append("- 三模型都不存在「知识内化后跳过工具」——must 桶不调工具必虚构（有依据=0），该签名几乎不出现。")
    L.append("- 真正的问题是**工具使用姿态多样性**：先追问(under)、过度探索(over) 都是「结果对但偏离标准序列」，")
    L.append("  被「工具选择」的精确匹配一律判 0，导致规则分与 LLM 分在过程维度上大幅背离。")
    L.append("- 修正方法：ground truth 只编码一条标准序列，无法容纳等价但不同的完成路径；")
    L.append("  应改用「结果正确 + 必要工具是否被调用」而非「精确序列」来评 must 桶，optional/none 桶关闭过程惩罚。\n")
    L.append("![分桶 bias](figures/bucket_bias.png)\n")

    L.append("## 4. 诚实声明\n")
    L.append("- 30 条合成样本、单场景、温度 0/0.3，样本量不足以做统计显著性判断。")
    L.append("- v4-pro 既当 Agent 又当 Judge，存在自偏好偏差；LLM 总分仅作相对参考。")
    L.append("- optional 桶仅 3 条样本（H001-H003），结论是方向性证据，需扩样本验证。\n")

    (OUT_DIR / "comparison.md").write_text("\n".join(L), encoding="utf-8")
    print("✅ 分析报告 →", OUT_DIR / "comparison.md")
    print("✅ 图 →", FIG_DIR)
    print(json.dumps({r["key"]: round(r["rule_overall"], 3) for r in rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
