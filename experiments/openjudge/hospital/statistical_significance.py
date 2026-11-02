# -*- coding: utf-8 -*-
"""统计显著性分析（#18，21 模型 × 100 样本版）：三个统计声明 + bootstrap CI。

对全部 temp=0 模型（21 个）：
1. 排序一致性：Spearman rank corr(rule 总分, LLM 总分)
2. 差距放大：rule 的跨模型 spread（std）vs LLM 的跨模型 spread（std）→ bootstrap CI
3. 姿态驱动分歧：Pearson corr(over 占比, rule−LLM gap) → cluster bootstrap CI（按模型重采样）

输出：reports/openjudge/multimodel/statistical_significance.json + 打印
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from samples import SAMPLES
from posture_grader import classify_posture

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

EXPECTED = {s["task_id"]: s["expected"]["correct_tools"] for s in SAMPLES}


def aggregate(scores: dict) -> float:
    safety = scores.get("safety", 1.0)
    return safety * (sum(scores.values()) / len(scores))


def load_model(name: str, rel: str) -> dict:
    md = REPORTS / rel
    traces = [json.loads(l) for l in open(md / "real_traces.jsonl", encoding="utf-8")]
    rule = json.load(open(md / "rule_scores.json", encoding="utf-8"))
    llm = [json.loads(l) for l in open(md / "llm_scores.jsonl", encoding="utf-8")]
    rule_overall = sum(aggregate(rule[tid][str(t)]) for tid in rule for t in range(3)) / (len(rule) * 3)
    llm_overall = sum(r["score"] for r in llm) / len(llm)
    # over 占比（trial 0）
    t0 = [t for t in traces if t["trial"] == 0]
    over = sum(1 for t in t0 if classify_posture(
        [s["tool"] for s in t["trajectory"] if s.get("type") == "tool_call"],
        EXPECTED[t["task_id"]]) == "over")
    return {
        "name": name, "rule": rule_overall, "llm": llm_overall,
        "gap": rule_overall - llm_overall, "over_rate": over / len(t0),
    }


def spearman(a, b):
    def _rank(x):
        o = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for i, idx in enumerate(o):
            r[idx] = i + 1
        return r
    ra, rb = _rank(a), _rank(b)
    n = len(a)
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))


def pearson(a, b):
    a = np.array(a, float); b = np.array(b, float)
    return float(np.corrcoef(a, b)[0, 1])


def _ci(samples: np.ndarray, alpha: float = 0.05):
    lo, hi = np.percentile(samples, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def main() -> None:
    rows = [load_model(n, rel) for n, rel in MODELS]
    rules = [r["rule"] for r in rows]
    llms = [r["llm"] for r in rows]
    gaps = [r["gap"] for r in rows]
    overs = [r["over_rate"] for r in rows]

    sp = spearman(rules, llms)
    corr = pearson(overs, gaps)

    rng = np.random.default_rng(42)
    B = 10000
    n = len(rows)
    idx = np.arange(n)

    # 3. over% vs gap 的 cluster bootstrap（按模型重采样）
    boot_corr = np.empty(B)
    for b in range(B):
        s = rng.choice(idx, size=n, replace=True)
        boot_corr[b] = pearson([overs[i] for i in s], [gaps[i] for i in s])
    corr_ci = _ci(boot_corr)

    # 2. 跨模型 spread 比较：rule std vs llm std，bootstrap CI of (rule_std - llm_std)
    boot_dstd = np.empty(B)
    for b in range(B):
        s = rng.choice(idx, size=n, replace=True)
        boot_dstd[b] = np.std([rules[i] for i in s]) - np.std([llms[i] for i in s])
    dstd_ci = _ci(boot_dstd)

    result = {
        "n_models": n,
        "spearman_rule_llm": sp,
        "corr_over_gap": corr,
        "corr_over_gap_ci": list(corr_ci),
        "rule_std": float(np.std(rules)), "llm_std": float(np.std(llms)),
        "rule_std_minus_llm_std": float(np.std(rules) - np.std(llms)),
        "dstd_ci": list(dstd_ci),
        "rule_range": [min(rules), max(rules)],
        "llm_range": [min(llms), max(llms)],
        "models": {r["name"]: {"rule": r["rule"], "llm": r["llm"], "gap": r["gap"],
                               "over_rate": r["over_rate"]} for r in rows},
    }
    (OUT_DIR / "statistical_significance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "n_models": n,
        "spearman_rule_llm": round(sp, 3),
        "corr_over_gap": round(corr, 3),
        "corr_over_gap_ci": [round(x, 3) for x in corr_ci],
        "rule_std": round(float(np.std(rules)), 4),
        "llm_std": round(float(np.std(llms)), 4),
        "rule_std_minus_llm_std": round(float(np.std(rules) - np.std(llms)), 4),
        "dstd_ci": [round(x, 4) for x in dstd_ci],
        "rule_range": [round(min(rules), 3), round(max(rules), 3)],
        "llm_range": [round(min(llms), 3), round(max(llms), 3)],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
