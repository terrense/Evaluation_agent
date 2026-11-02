# -*- coding: utf-8 -*-
"""姿态感知评分消融（21 模型 × 100 样本版）：修正框架能否收窄「姿态驱动的差距放大」。

对全部 temp=0 模型，在 5 个 grader 变体下重算 mean aggregate：
  baseline  —— 原 rule grader：aggregate = safety × mean(8 dim)，tool_selection=精确序列匹配
  A(结果型)  —— 只保留结果维度（丢 3 个过程维）
  B(分桶)    —— optional/none 桶关闭 tool_selection + stop_decision
  C(姿态感知)—— B + must 桶 tool_selection 改为「必要工具 ⊆ 已调用」
  D(放宽效率)—— C + 结果已 grounded+complete 时不再罚「多调」

核心观察量：每个变体下 (a) MiniMax-M3 相对其余模型的差距，(b) 跨模型 spread。
若 D 显著收窄 baseline 的差距/spread，则证明「过度探索被过程维惩罚」是差距放大的主因。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from samples import SAMPLES
from tool_requirement import TOOL_REQUIREMENT
from posture_grader import aggregate, rescore

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
OUT_DIR = REPORTS / "multimodel"

MODELS = [
    ("flash", "multimodel/flash__t0.0"),
    ("v4pro", "multimodel/v4pro__t0.0"),
    ("minimax-m3", "multimodel/minimax-m3__t0.0"),
    ("minimax-m2.5", "multimodel/minimax-m2.5__t0.0"),
    ("qwen3-32b", "multimodel/qwen3-32b__t0.0"),
    ("qwen3.8-max", "multimodel/qwen3.8-max__t0.0"),
    ("qwen3.7-max", "multimodel/qwen3.7-max__t0.0"),
    ("qwen3.8-flash", "multimodel/qwen3.8-flash__t0.0"),
    ("qwen3.8-2.4t-a95b", "multimodel/qwen3.8-2.4t-a95b__t0.0"),
    ("qwen3.7-flash", "multimodel/qwen3.7-flash__t0.0"),
    ("qwen3.7-plus", "multimodel/qwen3.7-plus__t0.0"),
    ("qwen3.6-plus", "multimodel/qwen3.6-plus__t0.0"),
    ("qwen3.5-plus", "multimodel/qwen3.5-plus__t0.0"),
    ("qwen-max", "multimodel/qwen-max__t0.0"),
    ("qwen-plus", "multimodel/qwen-plus__t0.0"),
    ("qwen-flash", "multimodel/qwen-flash__t0.0"),
    ("kimi-k3", "multimodel/kimi-k3__t0.0"),
    ("kimi-k2.7-code", "multimodel/kimi-k2.7-code__t0.0"),
    ("glm-5.3", "multimodel/glm-5.3__t0.0"),
    ("glm-5.3-prime", "multimodel/glm-5.3-prime__t0.0"),
    ("glm-5.2", "multimodel/glm-5.2__t0.0"),
]

VARIANTS = ["baseline", "A", "B", "C", "D"]
EXPECTED = {s["task_id"]: s["expected"]["correct_tools"] for s in SAMPLES}


def load_per_trial(name: str, rel: str) -> list[dict]:
    """返回每 trial 的 {dims, bucket, expected, actual}。"""
    md = REPORTS / rel
    traces = [json.loads(l) for l in open(md / "real_traces.jsonl", encoding="utf-8")]
    rule = json.load(open(md / "rule_scores.json", encoding="utf-8"))
    by_task = {}
    for t in traces:
        by_task.setdefault(t["task_id"], {})[t["trial"]] = t
    out = []
    for tid in rule:
        bucket = TOOL_REQUIREMENT[tid]
        for tr in range(3):
            t = by_task[tid][tr]
            actual = [s["tool"] for s in t["trajectory"] if s.get("type") == "tool_call"]
            out.append({
                "dims": rule[tid][str(tr)],
                "bucket": bucket,
                "expected": EXPECTED[tid],
                "actual": actual,
            })
    return out


def main() -> None:
    model_trials = {n: load_per_trial(n, rel) for n, rel in MODELS}

    table = {v: {} for v in VARIANTS}
    for v in VARIANTS:
        for n in model_trials:
            scores = [aggregate(rescore(t["dims"], t["bucket"], t["expected"], t["actual"], v))
                      for t in model_trials[n]]
            table[v][n] = sum(scores) / len(scores)

    # 每个变体：MiniMax-M3 差距 + 跨模型 spread
    result = {"variants": {}}
    rows = []
    for v in VARIANTS:
        m3 = table[v]["minimax-m3"]
        others = [table[v][n] for n in model_trials if n != "minimax-m3"]
        mean_others = sum(others) / len(others)
        gap = mean_others - m3
        spread = float(np.std([table[v][n] for n in model_trials]))
        result["variants"][v] = {
            "minimax_m3": m3, "mean_others": mean_others,
            "gap": gap, "cross_model_std": spread,
        }
        rows.append((v, m3, mean_others, gap, spread))

    (OUT_DIR / "ablation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'variant':10s} {'M3得分':>7s} {'其余均值':>8s} {'M3差距':>8s} {'跨模型std':>9s}")
    for v, m3, mo, gap, spread in rows:
        print(f"{v:10s} {m3:7.3f} {mo:8.3f} {gap:8.3f} {spread:9.4f}")


if __name__ == "__main__":
    main()
