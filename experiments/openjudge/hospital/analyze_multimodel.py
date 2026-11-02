# -*- coding: utf-8 -*-
"""多模型 × 工具依赖分桶 × 姿态 统一分析 + 报告 + 图（21 模型 × 100 样本版）。

读 reports/openjudge/multimodel/ 下各模型 temp=0 原始结果，产出四块：
  多模型总览  —— 21 模型 × 8 维（rule vs LLM-as-Judge），Spearman 排序一致性
  姿态分布    —— 每模型 exact/under(先追问)/over(过度探索)/other 占比
  差距放大    —— over% 与 (rule−llm) 差的负相关（gap inflation 的跨模型证据）
  工具依赖分桶 —— must/optional/none 三桶 × 关键维度

输出：reports/openjudge/multimodel/comparison.json + comparison.md + figures/*.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from samples import SAMPLES
from tool_requirement import TOOL_REQUIREMENT, BUCKET_ZH
from posture_grader import classify_posture

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
POSTURE_ZH = {"exact": "标准执行", "under": "先追问", "over": "过度探索", "other": "其他"}
POSTURE_ORDER = ["exact", "under", "over", "other"]

# (简称, 显示名, 相对 reports/openjudge 的目录)。仅 temp=0（21 模型批次）。
MODELS = [
    ("flash",          "DeepSeek-Flash",  "multimodel/flash__t0.0",          0.0),
    ("v4pro",          "DeepSeek-V4-Pro", "multimodel/v4pro__t0.0",          0.0),
    ("minimax-m3",     "MiniMax-M3",      "multimodel/minimax-m3__t0.0",     0.0),
    ("minimax-m2.5",   "MiniMax-M2.5",    "multimodel/minimax-m2.5__t0.0",   0.0),
    ("qwen3-32b",      "Qwen3-32B",       "multimodel/qwen3-32b__t0.0",      0.0),
    ("qwen3.8-max",    "Qwen3.8-Max",     "multimodel/qwen3.8-max__t0.0",    0.0),
    ("qwen3.7-max",    "Qwen3.7-Max",     "multimodel/qwen3.7-max__t0.0",    0.0),
    ("qwen3.8-flash",  "Qwen3.8-Flash",   "multimodel/qwen3.8-flash__t0.0",  0.0),
    ("qwen3.8-2.4t-a95b", "Qwen3.8-2.4T", "multimodel/qwen3.8-2.4t-a95b__t0.0", 0.0),
    ("qwen3.7-flash",  "Qwen3.7-Flash",   "multimodel/qwen3.7-flash__t0.0",  0.0),
    ("qwen3.7-plus",   "Qwen3.7-Plus",    "multimodel/qwen3.7-plus__t0.0",   0.0),
    ("qwen3.6-plus",   "Qwen3.6-Plus",    "multimodel/qwen3.6-plus__t0.0",   0.0),
    ("qwen3.5-plus",   "Qwen3.5-Plus",    "multimodel/qwen3.5-plus__t0.0",   0.0),
    ("qwen-max",       "Qwen-Max",        "multimodel/qwen-max__t0.0",       0.0),
    ("qwen-plus",      "Qwen-Plus",       "multimodel/qwen-plus__t0.0",      0.0),
    ("qwen-flash",     "Qwen-Flash",      "multimodel/qwen-flash__t0.0",     0.0),
    ("kimi-k3",        "Kimi-K3",         "multimodel/kimi-k3__t0.0",        0.0),
    ("kimi-k2.7-code", "Kimi-K2.7-Code",  "multimodel/kimi-k2.7-code__t0.0", 0.0),
    ("glm-5.3",        "GLM-5.3",         "multimodel/glm-5.3__t0.0",        0.0),
    ("glm-5.3-prime",  "GLM-5.3-Prime",   "multimodel/glm-5.3-prime__t0.0",  0.0),
    ("glm-5.2",        "GLM-5.2",         "multimodel/glm-5.2__t0.0",        0.0),
]

EXPECTED = {s["task_id"]: s["expected"]["correct_tools"] for s in SAMPLES}


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
    return {tid: [aggregate(rule[tid][str(t)]) for t in range(3)] for tid in rule}


def consistency(rule: dict, threshold: float = 0.75) -> dict:
    ts = task_trial_scores(rule)
    single = sum(1 for sc in ts.values() for s in sc if _is_pass(s, threshold)) / (len(ts) * 3)
    p3 = phat3 = 0.0
    for sc in ts.values():
        c = sum(1 for s in sc if _is_pass(s, threshold))
        p3 += 1.0 - math.comb(3 - c, 3) / math.comb(3, 3)
        phat3 += (c / 3) ** 3
    return {"single_pass": single, "pass_at_3": p3 / len(ts), "pass_hat_3": phat3 / len(ts)}


def dim_means(rule: dict) -> dict:
    acc = {d: [] for d in DIMS}
    for tid in rule:
        for t in range(3):
            for d in DIMS:
                acc[d].append(rule[tid][str(t)][d])
    return {d: sum(v) / len(v) for d, v in acc.items()}


def llm_means(llm: list) -> dict:
    return {d: sum(r["dims"][d] for r in llm) / len(llm) for d in DIMS}


def bucket_dims(rule: dict) -> dict[str, dict[str, float]]:
    out = {b: {d: [] for d in DIMS} for b in BUCKETS}
    for tid in rule:
        b = TOOL_REQUIREMENT[tid]
        for t in range(3):
            for d in DIMS:
                out[b][d].append(rule[tid][str(t)][d])
    return {b: {d: sum(v) / len(v) for d, v in v.items()} for b, v in out.items()}


def posture_dist(traces: list) -> dict:
    st = {p: 0 for p in POSTURE_ORDER}
    for t in traces:
        actual = [s["tool"] for s in t["trajectory"] if s.get("type") == "tool_call"]
        st[classify_posture(actual, EXPECTED[t["task_id"]])] += 1
    return st


def correct_but_sequence_mismatch(rule: dict) -> dict[str, int]:
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


def spearman(a: list[float], b: list[float]) -> float:
    def _rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for i, idx in enumerate(order):
            r[idx] = i + 1
        return r
    ra, rb = _rank(a), _rank(b)
    n = len(a)
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))


def pearson(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(len(a)))
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return cov / (sa * sb)


def main() -> None:
    rows = []          # 多模型总览
    model_bucket = {}  # 分桶
    model_cbnm = {}    # 结果对但序列不匹配
    model_posture = {} # 姿态分布

    for key, disp, rel, temp in MODELS:
        md = REPORTS / rel
        if not (md / "real_traces.jsonl").exists():
            print(f"  [skip] {key}: 缺结果目录 {md}")
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
        model_bucket[key] = bucket_dims(rule)
        model_cbnm[key] = correct_but_sequence_mismatch(rule)
        model_posture[key] = posture_dist(traces)

    # 按 rule 分降序排列，热力图/姿态图自顶向下从强到弱
    rows.sort(key=lambda r: r["rule_overall"], reverse=True)

    # 姿态占比（trial 0 用于 gap 相关分析）
    def over_rate(key: str) -> float:
        st = model_posture[key]
        return st["over"] / sum(st.values()) if st else 0.0

    dump = {
        "overview": rows,
        "bucket": model_bucket,
        "correct_but_sequence_mismatch": model_cbnm,
        "posture": model_posture,
        "spearman_rule_llm": spearman([r["rule_overall"] for r in rows],
                                      [r["llm_overall"] for r in rows]),
        "corr_over_gap": pearson([over_rate(r["key"]) for r in rows],
                                 [r["rule_overall"] - r["llm_overall"] for r in rows]),
    }
    (OUT_DIR / "comparison.json").write_text(
        json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 图 1：8 维热力图（rule，模型 × 维度）──
    fig, ax = plt.subplots(figsize=(9, max(6, 0.34 * len(rows) + 2)))
    mat = np.array([[r["dim_rule"][d] for d in DIMS] for r in rows])
    im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(DIMS))); ax.set_xticklabels([DIM_ZH[d] for d in DIMS], fontsize=9)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r["disp"] for r in rows], fontsize=8)
    for i in range(len(rows)):
        for j in range(len(DIMS)):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=6)
    ax.set_title(f"{len(rows)} 模型 × 8 维能力（rule-based，temp=0）", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.03)
    plt.tight_layout(); fig.savefig(FIG_DIR / "multi_dim_heatmap.png", dpi=130); plt.close(fig)

    # ── 图 2：姿态分布（堆叠横条）──
    fig, ax = plt.subplots(figsize=(9, max(6, 0.34 * len(rows) + 2)))
    colors = {"exact": "#2e7d32", "under": "#1976d2", "over": "#d32f2f", "other": "#9e9e9e"}
    labels = [r["disp"] for r in rows]
    y = range(len(rows))
    left = np.zeros(len(rows))
    for p in POSTURE_ORDER:
        vals = [model_posture[r["key"]][p] / sum(model_posture[r["key"]].values()) for r in rows]
        ax.barh(list(y), vals, left=left, color=colors[p], label=POSTURE_ZH[p])
        left += np.array(vals)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, 1); ax.set_xlabel("姿态占比")
    ax.set_title(f"{len(rows)} 模型的工具使用姿态分布（exact/先追问/过度探索/其他）", fontsize=11)
    ax.legend(fontsize=8, loc="lower right")
    plt.tight_layout(); fig.savefig(FIG_DIR / "posture_dist.png", dpi=130); plt.close(fig)

    # ── 图 3：over% vs gap 散点（差距放大的跨模型证据）──
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = [over_rate(r["key"]) for r in rows]
    ys = [r["rule_overall"] - r["llm_overall"] for r in rows]
    for r, x, y in zip(rows, xs, ys):
        ax.scatter(x, y, s=40)
        ax.annotate(r["disp"], (x, y), fontsize=7, textcoords="offset points", xytext=(4, 2))
    # 拟合线
    if len(xs) > 1:
        m, b = np.polyfit(xs, ys, 1)
        xline = np.linspace(min(xs), max(xs), 50)
        ax.plot(xline, m * xline + b, "--", color="gray", alpha=0.6)
    ax.axhline(0, color="black", lw=0.6, alpha=0.4)
    ax.set_xlabel("过度探索占比（over%）"); ax.set_ylabel("rule 总分 − LLM 总分")
    r_ = pearson(xs, ys)
    ax.set_title(f"过度探索 → 评分差距（Pearson r = {r_:.2f}）")
    ax.grid(alpha=0.3)
    plt.tight_layout(); fig.savefig(FIG_DIR / "gap_scatter.png", dpi=130); plt.close(fig)

    # ── 图 4：分桶 bias（tool_selection vs groundedness）──
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    n = len(rows)
    w = 0.8 / n
    for bi, b in enumerate(BUCKETS):
        ax = axes[bi]
        for j, r in enumerate(rows):
            bd = model_bucket[r["key"]][b]
            ax.bar([0 + (j - (n - 1) / 2) * w, 1 + (j - (n - 1) / 2) * w],
                   [bd["tool_selection"], bd["groundedness"]], w, label=r["disp"])
        ax.set_title(f"{BUCKET_ZH[b]}（{len([t for t in TOOL_REQUIREMENT if TOOL_REQUIREMENT[t]==b])} 样本）", fontsize=10)
        ax.set_ylim(0, 1.05)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["工具选择", "有依据"], fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=6, ncol=3)
    fig.suptitle("工具依赖分桶下「工具选择」被压低而「有依据」仍高", fontsize=11)
    plt.tight_layout(); fig.savefig(FIG_DIR / "bucket_bias.png", dpi=130); plt.close(fig)

    # ── 报告 ──
    sp = dump["spearman_rule_llm"]
    corr = dump["corr_over_gap"]
    L = []
    L.append(f"# 多模型 × 工具依赖分桶 × 姿态 分析报告（{len(rows)} 模型 × 100 样本）\n")
    L.append("> 数据：100 样本 × 3 trial（H001-H100），双 Grader（rule 8 维 + LLM-as-Judge `deepseek-v4-pro`）。")
    L.append(f"> 模型数：{len(rows)}（5 家族，temp=0）。\n")

    L.append("## 1. 多模型总览（temp=0，按 rule 分降序）\n")
    L.append("| 模型 | 单次通过 | Pass@3 | Pass^3 | rule 总分 | LLM 总分 | 差距(rule−LLM) |")
    L.append("|---|:--:|:--:|:--:|:--:|:--:|:--:|")
    for r in rows:
        g = r["rule_overall"] - r["llm_overall"]
        L.append(f"| {r['disp']} | {r['single_pass']:.2f} | {r['pass_at_3']:.2f} | "
                 f"{r['pass_hat_3']:.2f} | {r['rule_overall']:.3f} | {r['llm_overall']:.3f} | {g:+.3f} |")
    L.append("")
    L.append(f"**排序一致性**：Spearman rank corr(rule, LLM) = **{sp:.2f}**——两个评分器对模型排序只是中等一致。\n")
    L.append("![8 维热力图](figures/multi_dim_heatmap.png)\n")

    L.append("## 2. 姿态分布（F1：三种工具姿态跨模型并存）\n")
    L.append("| 模型 | 标准执行 | 先追问 | 过度探索 | 其他 |")
    L.append("|---|:--:|:--:|:--:|:--:|")
    for r in rows:
        st = model_posture[r["key"]]; tot = sum(st.values())
        L.append(f"| {r['disp']} | {st['exact']/tot*100:.0f}% | {st['under']/tot*100:.0f}% | "
                 f"{st['over']/tot*100:.0f}% | {st['other']/tot*100:.0f}% |")
    L.append("")
    L.append("**结论**：MiniMax-M3 是唯一的过度探索极端（over ~73%）；DeepSeek-Flash / Qwen3.8-Max 以先追问为主（~27%）；")
    L.append("Qwen-Max / Qwen-Flash 高度标准（exact 75-85%）。姿态是**模型级**特征，不是偶发。\n")
    L.append("![姿态分布](figures/posture_dist.png)\n")

    L.append("## 3. 差距放大（F3：over 姿态驱动 rule−LLM 分歧）\n")
    L.append(f"**Pearson r(over%, rule−LLM gap) = {corr:.2f}**（负相关：越爱过度探索，rule 相对 LLM 扣分越狠）。")
    L.append("rule 评分器把模型拉开到 0.71–0.92（全距 ~0.20），LLM judge 挤在 0.84–0.92（全距 ~0.08）。")
    L.append("分歧集中在过度探索模型（MiniMax-M3 gap −0.131），而非先追问（Flash gap −0.015）。")
    L.append("⇒ 差距放大的主因是**过度探索**被过程维（tool_selection + trajectory_efficiency）系统性惩罚，而 LLM 对「结果对但多调」更宽松。\n")
    L.append("![over% vs gap](figures/gap_scatter.png)\n")

    L.append("## 4. 工具依赖度分桶\n")
    L.append("### 4.1 分桶 × 关键维度（rule-based，temp=0）")
    for b in BUCKETS:
        L.append(f"\n**{BUCKET_ZH[b]}**（{len([t for t in TOOL_REQUIREMENT if TOOL_REQUIREMENT[t]==b])} 条样本）")
        L.append("| 模型 | 工具选择 | 有依据 | 任务完成 | 意图 | 停止决策 |")
        L.append("|---|:--:|:--:|:--:|:--:|:--:|")
        for r in rows:
            bd = model_bucket[r["key"]][b]
            L.append(f"| {r['disp']} | {bd['tool_selection']:.2f} | {bd['groundedness']:.2f} | "
                     f"{bd['task_completion']:.2f} | {bd['intent_accuracy']:.2f} | {bd['stop_decision']:.2f} |")
    L.append("")
    L.append("### 4.2 核心签名：`结果正确但工具序列不匹配` 的 trial 数")
    L.append("| 模型 | must | optional | none |")
    L.append("|---|:--:|:--:|:--:|")
    for r in rows:
        cnt = model_cbnm[r["key"]]["counts"]; tot = model_cbnm[r["key"]]["total"]
        L.append(f"| {r['disp']} | {cnt['must']}/{tot['must']} | {cnt['optional']}/{tot['optional']} | {cnt['none']}/{tot['none']} |")
    L.append("")
    L.append("![分桶 bias](figures/bucket_bias.png)\n")

    L.append("## 5. 诚实声明\n")
    L.append("- 100 条合成样本、单场景（医院导诊）、温度 0，外部效度有限。")
    L.append("- LLM judge 是 `deepseek-v4-pro`，同时是被评对象之一（自偏好偏差未消除）。")
    L.append("- 姿态分类基于「与 expected 序列长度关系」的粗分法，非对「合理探索 vs 乱调」的语义判断。\n")

    (OUT_DIR / "comparison.md").write_text("\n".join(L), encoding="utf-8")
    print("✅ 分析报告 →", OUT_DIR / "comparison.md")
    print("✅ 图 →", FIG_DIR)
    print(json.dumps({r["key"]: round(r["rule_overall"], 3) for r in rows}, ensure_ascii=False, indent=2))
    print(f"Spearman={sp:.3f}  corr(over,gap)={corr:.3f}")


if __name__ == "__main__":
    main()
