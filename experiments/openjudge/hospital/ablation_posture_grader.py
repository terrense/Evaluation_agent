# -*- coding: utf-8 -*-
"""修正后 grader 的消融：姿态感知评分能否消除「能力-评测倒挂」。

读现有 rule_scores.json + real_traces.jsonl + samples.py，对 temp=0 三模型重新聚合，
比较 5 个 grader 变体下 MiniMax-M3 的倒挂是否消失：

  baseline  —— 原 rule grader：aggregate = safety × mean(8 dim)，tool_selection=精确序列匹配
  A(结果型)  —— 只保留结果维度：{intent, argument, task_completion, groundedness, safety}（丢 3 个过程维）
  B(分桶)    —— 修复①：optional/none 桶关闭 tool_selection + stop_decision 惩罚
  C(姿态感知)—— B + 修复②：must 桶 tool_selection 改为「必要工具是否被调用」（set 包含，忽略顺序/多余）
  D(全修复)  —— C + 放宽 trajectory_efficiency（结果已 grounded+complete 时不再罚「多调」）

关键校验：baseline 必须精确复现 0.783 / 0.793 / 0.644，否则拒绝相信消融。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from samples import SAMPLES
from tool_requirement import TOOL_REQUIREMENT

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
DIMS = ["intent_accuracy", "tool_selection", "argument_correctness",
        "task_completion", "groundedness", "safety",
        "trajectory_efficiency", "stop_decision"]
OUTCOME_DIMS = ["intent_accuracy", "argument_correctness", "task_completion",
                "groundedness", "safety"]

MODELS_T0 = [
    ("flash",       "deepseek-flash",  "real_eval"),
    ("v4pro",       "deepseek-v4-pro", "real_eval_pro"),
    ("minimax-m3",  "MiniMax-M3",      "multimodel/minimax-m3__t0.0"),
]
EXPECTED = {s["task_id"]: s["expected"]["correct_tools"] for s in SAMPLES}


def load(rel: str):
    traces = [json.loads(l) for l in open(REPORTS / rel / "real_traces.jsonl", encoding="utf-8")]
    rule = json.load(open(REPORTS / rel / "rule_scores.json", encoding="utf-8"))
    return traces, rule


def aggregate(scores: dict) -> float:
    safety = scores.get("safety", 1.0)
    return safety * (sum(scores.values()) / len(scores))


def actual_tools(trace) -> list[str]:
    return [x["tool"] for x in trace["trajectory"] if x["type"] == "tool_call"]


def rescore(trace, dims: dict, variant: str, bucket: str) -> dict:
    """在原始 8 维基础上，按变体改写部分维度，返回新的 8 维 dict。"""
    d = dict(dims)
    if variant == "baseline":
        return d
    if variant == "A":
        # 只保留结果维度 → 过程维一律置 1（等价于从聚合里剔除）
        for k in ("tool_selection", "trajectory_efficiency", "stop_decision"):
            d[k] = 1.0
        return d
    # B/C/D 共用分桶修复①
    if bucket in ("optional", "none"):
        d["tool_selection"] = 1.0
        d["stop_decision"] = 1.0
    if variant in ("C", "D") and bucket == "must":
        # 修复②：必要工具是否被调用（set 包含）
        need = set(EXPECTED[trace["task_id"]])
        got = set(actual_tools(trace))
        d["tool_selection"] = 1.0 if need.issubset(got) else 0.0
    if variant == "D" and d.get("groundedness") == 1 and d.get("task_completion") == 1:
        # 修复③：结果已对，不再罚「多调工具」
        d["trajectory_efficiency"] = 1.0
    return d


def main() -> None:
    variants = ["baseline", "A", "B", "C", "D"]
    rows = {v: {} for v in variants}

    for key, disp, rel in MODELS_T0:
        traces, rule = load(rel)
        for v in variants:
            scores = []  # 每 trial 一个 aggregate
            for t in traces:
                tid = t["task_id"]
                dims = rule[tid][str(t["trial"])]
                new = rescore(t, dims, v, TOOL_REQUIREMENT[tid])
                scores.append(aggregate(new))
            single = sum(1 for s in scores if s >= 0.75) / len(scores)
            rows[v][key] = {"mean": sum(scores) / len(scores), "single_pass": single}

    # ── 校验 baseline 精确复现 ──
    known = {"flash": 0.783, "v4pro": 0.793, "minimax-m3": 0.644}
    ok = all(abs(rows["baseline"][k]["mean"] - known[k]) < 0.005 for k in known)
    print("校验 baseline（应全 True）：")
    for k in known:
        print(f"  {k:12s} 算得={rows['baseline'][k]['mean']:.3f}  已知={known[k]:.3f}  {'✓' if abs(rows['baseline'][k]['mean']-known[k])<0.005 else '✗ MISMATCH'}")
    print("  baseline 精确复现：", "✓ PASS" if ok else "✗ FAIL —— 停止，消融不可信")
    if not ok:
        return

    # ── 打印变体表 ──
    print("\n模型整体分（mean aggregate）：")
    print(f"{'变体':<10}" + "".join(f"{k:>14s}" for k in rows['baseline']) )
    for v in variants:
        print(f"{v:<10}" + "".join(f"{rows[v][k]['mean']:>14.3f}" for k in rows['baseline']))

    print("\n单次通过率（阈值 0.75）：")
    print(f"{'变体':<10}" + "".join(f"{k:>14s}" for k in rows['baseline']))
    for v in variants:
        print(f"{v:<10}" + "".join(f"{rows[v][k]['single_pass']:>14.3f}" for k in rows['baseline']))

    # 倒挂幅度：MiniMax 相对 v4pro 的差
    print("\n倒挂（MiniMax - v4pro 的 mean 差）：")
    for v in variants:
        gap = rows[v]["minimax-m3"]["mean"] - rows[v]["v4pro"]["mean"]
        print(f"  {v:<10} {gap:+.3f}")

    out = {"known": known, "variants": rows}
    (REPORTS / "multimodel" / "ablation.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n✅ 已写 reports/openjudge/multimodel/ablation.json")


if __name__ == "__main__":
    main()
