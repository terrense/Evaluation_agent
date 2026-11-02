# -*- coding: utf-8 -*-
"""统计显著性分析（#18）：cluster bootstrap 置信区间 + McNemar 检验。

对 temp=0 三模型（flash / v4pro / minimax-m3）：
1. rule 每 trial 的 aggregate = safety × mean(8 维)，pass = aggregate >= 0.75
2. cluster bootstrap（按 task 重采样，B=10000，seed 固定）：
   - rule_overall（90 trial）/ llm_overall（30 task）的 95% CI
   - 模型间 gap（MiniMax − V4Pro）的 CI（rule 与 llm 各一）
   - gap 之差（rule_gap − llm_gap）的 CI → 检验「差距放大」是否显著
3. McNemar 检验（trial 0，30 配对任务）：rule pass vs llm pass 的不对称性

输出：reports/openjudge/multimodel/statistical_significance.json + 打印

状态：当前仅对已跑出的 3 模型（30 样本）做显著性；22 模型 × 100 样本重跑完成后重写（task #21）。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from samples import SAMPLES

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
OUT = REPORTS / "multimodel" / "statistical_significance.json"

MODELS = [
    ("flash",       "deepseek-flash",  "real_eval"),
    ("v4pro",       "deepseek-v4-pro", "real_eval_pro"),
    ("minimax-m3",  "MiniMax-M3",      "multimodel/minimax-m3__t0.0_fixed"),
]
DIMS = ["intent_accuracy", "tool_selection", "argument_correctness",
        "task_completion", "groundedness", "safety",
        "trajectory_efficiency", "stop_decision"]

B = 10000          # bootstrap 次数
SEED = 42
THRESHOLD = 0.75   # pass 阈值
ALPHA = 0.05


def aggregate(scores: dict) -> float:
    safety = scores.get("safety", 1.0)
    return safety * (sum(scores.values()) / len(scores))


def load(rel: str):
    rule = json.load(open(REPORTS / rel / "rule_scores.json", encoding="utf-8"))
    llm = [json.loads(l) for l in open(REPORTS / rel / "llm_scores.jsonl", encoding="utf-8")]
    return rule, llm


def ci(vals: list[float]) -> tuple[float, float]:
    """百分位 95% 置信区间。"""
    s = sorted(vals)
    lo = int(len(s) * ALPHA / 2)
    hi = int(len(s) * (1 - ALPHA / 2)) - 1
    return s[lo], s[hi]


def cluster_bootstrap_mean(task_vals: dict[str, list[float]], ids: list[str]) -> list[float]:
    """按 task 簇重采样：抽 len(ids) 个 task（可重复），池化其 trial 值，求均值。"""
    out = []
    for _ in range(B):
        sample = [random.choice(ids) for _ in ids]
        vals = [v for tid in sample for v in task_vals[tid]]
        out.append(sum(vals) / len(vals))
    return out


def bootstrap_gap(va: dict[str, list[float]], vb: dict[str, list[float]],
                  ids: list[str]) -> list[float]:
    """配对（同 task 簇）重采样下，A−B 的均值差分布（按实际值数归一）。"""
    out = []
    for _ in range(B):
        sample = [random.choice(ids) for _ in ids]
        a_vals = [v for tid in sample for v in va[tid]]
        b_vals = [v for tid in sample for v in vb[tid]]
        out.append(sum(a_vals) / len(a_vals) - sum(b_vals) / len(b_vals))
    return out


def mcnemar(b: int, c: int) -> dict:
    """McNemar 精确二项检验（b、c 为不一致的两种方向计数）。"""
    import math
    n = b + c
    p_two_sided = 2.0 * sum(math.comb(n, k) * (0.5 ** n)
                            for k in range(0, min(b, c) + 1))
    return {"b": b, "c": c, "n_discordant": n, "p_two_sided": min(1.0, p_two_sided)}


def main() -> None:
    random.seed(SEED)
    data = {}
    for key, disp, rel in MODELS:
        rule, llm = load(rel)
        trial_agg = {tid: [aggregate(rule[tid][str(t)]) for t in range(3)] for tid in rule}
        llm_score = {r["task_id"]: r["score"] for r in llm}
        data[key] = {"trial_agg": trial_agg, "llm_score": llm_score, "rule": rule}

    ids = [s["task_id"] for s in SAMPLES]

    # ── 1. 各模型 rule/llm 均值 + CI ──
    summary = {}
    rule_boot = {}
    llm_boot = {}
    for key in data:
        rule_boot[key] = cluster_bootstrap_mean(data[key]["trial_agg"], ids)
        llm_boot[key] = cluster_bootstrap_mean(
            {tid: [v] for tid, v in data[key]["llm_score"].items()}, ids)
        summary[key] = {
            "rule_mean": sum(rule_boot[key]) / B, "rule_ci95": list(ci(rule_boot[key])),
            "llm_mean": sum(llm_boot[key]) / B, "llm_ci95": list(ci(llm_boot[key])),
        }

    # ── 2. gap（MiniMax − V4Pro）rule 与 llm ──
    # rule 全量（90 trial）
    rule_gap = bootstrap_gap(data["minimax-m3"]["trial_agg"],
                             data["v4pro"]["trial_agg"], ids)
    # rule 仅 trial 0（30 task，与 llm 同口径，才能做公平的「放大」比较）
    t0 = lambda d: {tid: [d["trial_agg"][tid][0]] for tid in d["trial_agg"]}
    rule_t0_gap = bootstrap_gap(t0(data["minimax-m3"]), t0(data["v4pro"]), ids)
    # llm（30 task）
    llm_gap = bootstrap_gap(
        {tid: [v] for tid, v in data["minimax-m3"]["llm_score"].items()},
        {tid: [v] for tid, v in data["v4pro"]["llm_score"].items()}, ids)
    # 差距放大 = rule(trial0) − llm，配对 bootstrap（同 30 task 口径）
    gap_infl = [r - l for r, l in zip(rule_t0_gap, llm_gap)]

    # ── 3. McNemar（trial 0 配对：rule pass vs llm pass）──
    mc = {}
    for key in data:
        b = c = 0
        for tid in ids:
            rule_pass = aggregate(data[key]["rule"][tid]["0"]) >= THRESHOLD
            llm_pass = data[key]["llm_score"][tid] >= THRESHOLD
            if rule_pass and not llm_pass:
                b += 1
            elif not rule_pass and llm_pass:
                c += 1
        mc[key] = mcnemar(b, c)

    out = {
        "seed": SEED, "B": B, "threshold": THRESHOLD,
        "summary": summary,
        "gap": {
            "rule_minimax_minus_v4pro_90trial": {"mean": sum(rule_gap) / B, "ci95": list(ci(rule_gap))},
            "rule_minimax_minus_v4pro_t0": {"mean": sum(rule_t0_gap) / B, "ci95": list(ci(rule_t0_gap))},
            "llm_minimax_minus_v4pro": {"mean": sum(llm_gap) / B, "ci95": list(ci(llm_gap))},
            "gap_inflation": {"mean": sum(gap_infl) / B, "ci95": list(ci(gap_infl))},
        },
        "mcnemar": mc,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 各模型 rule/llm 均值 + 95% CI（cluster bootstrap）===")
    for key, disp, _ in MODELS:
        s = summary[key]
        print(f"  {disp:16s} rule={s['rule_mean']:.3f} CI[{s['rule_ci95'][0]:.3f},{s['rule_ci95'][1]:.3f}]  "
              f"llm={s['llm_mean']:.3f} CI[{s['llm_ci95'][0]:.3f},{s['llm_ci95'][1]:.3f}]")
    print("\n=== gap（MiniMax − V4Pro）===")
    g = out["gap"]
    print(f"  rule gap(90trial) = {g['rule_minimax_minus_v4pro_90trial']['mean']:+.3f}  "
          f"CI[{g['rule_minimax_minus_v4pro_90trial']['ci95'][0]:+.3f},{g['rule_minimax_minus_v4pro_90trial']['ci95'][1]:+.3f}]")
    print(f"  rule gap(trial0)  = {g['rule_minimax_minus_v4pro_t0']['mean']:+.3f}  "
          f"CI[{g['rule_minimax_minus_v4pro_t0']['ci95'][0]:+.3f},{g['rule_minimax_minus_v4pro_t0']['ci95'][1]:+.3f}]")
    print(f"  llm  gap           = {g['llm_minimax_minus_v4pro']['mean']:+.3f}  "
          f"CI[{g['llm_minimax_minus_v4pro']['ci95'][0]:+.3f},{g['llm_minimax_minus_v4pro']['ci95'][1]:+.3f}]")
    print(f"  差距放大(rule_t0−llm) = {g['gap_inflation']['mean']:+.3f}  "
          f"CI[{g['gap_inflation']['ci95'][0]:+.3f},{g['gap_inflation']['ci95'][1]:+.3f}]  "
          f"(<0 且 CI 不含 0 ⇒ rule 显著放大差距)")
    print("\n=== McNemar（rule pass vs llm pass，trial 0）===")
    for key, disp, _ in MODELS:
        m = mc[key]
        print(f"  {disp:16s} b(rule过/llm不过)={m['b']:2d}  c(rule不过/llm过)={m['c']:2d}  p={m['p_two_sided']:.4f}")
    print(f"\n✅ 已写 {OUT}")


if __name__ == "__main__":
    main()
