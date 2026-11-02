# -*- coding: utf-8 -*-
"""Posture-Grader（姿态-评测错配修正框架）—— 可复用的开源模块。

一句话：工具调用 Agent 评测里，ground truth 只编码一条「标准工具序列」
（correct_tools），而真实模型表现出至少三种工具使用姿态——先追问(under)、
标准执行(exact)、过度探索(over)。过程型 grader 用「精确序列匹配」把偏离
标准但结果正确的姿态一律判 0，导致「姿态不同」被误判成「能力不行」，
把真实的能力差距放大 2~3 倍（gap inflation，见 statistical_significance.py）。

本模块提供四件事（均与具体场景无关，可直接套用到任意工具 benchmark）：
  1. classify_posture        —— 把一次轨迹相对 expected 序列分类成四种姿态
  2. posture_distribution    —— 聚合一个模型/配置的姿态占比
  3. rescore                 —— 姿态感知评分（A/B/C/D 四档消融，见下）
  4. ANNOTATION_SCHEMA       —— 工具依赖度标注 schema（must/optional/none）

用法示例：
    from posture_grader import classify_posture, rescore, BUCKET_MUST
    p = classify_posture(actual=["query_department"], expected=["query_department"])  # exact
    new_dims = rescore(dims, bucket=BUCKET_MUST, expected_tools=["a","b"],
                       actual_tools=["a","c"], variant="D")

依赖：无（纯标准库）。
"""
from __future__ import annotations

from typing import Iterable, Sequence

# ── 工具依赖度标注 schema（可导出为 JSON）──────────────────────
# 每个任务的正确答案是否「只能通过调用工具获得」：
#   must     —— 答案只存在于工具返回数据，不调工具=虚构 → 该罚过程惩罚
#   optional —— 答案可从模型内部知识推导，工具只是可选通道 → 不该罚
#   none     —— 无需工具（闲聊/拒绝/澄清）→ 不该罚
BUCKET_MUST = "must"
BUCKET_OPTIONAL = "optional"
BUCKET_NONE = "none"
BUCKETS = (BUCKET_MUST, BUCKET_OPTIONAL, BUCKET_NONE)

# 八维评测维度（与论文一致）
DIMS = ["intent_accuracy", "tool_selection", "argument_correctness",
        "task_completion", "groundedness", "safety",
        "trajectory_efficiency", "stop_decision"]
OUTCOME_DIMS = ["intent_accuracy", "argument_correctness",
                "task_completion", "groundedness", "safety"]
PROCESS_DIMS = ["tool_selection", "trajectory_efficiency", "stop_decision"]

# 标注 schema 说明（供下游导出 JSON / 文档用）
ANNOTATION_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Tool-Dependency Annotation (must/optional/none)",
    "description": "对每个任务标注：正确答案是否只能通过调用工具获得。"
                   "must 桶额外标注 necessary_tools（完成任务必须调用的工具集合）。",
    "type": "object",
    "patternProperties": {
        "^.*$": {
            "type": "object",
            "properties": {
                "bucket": {"enum": list(BUCKETS)},
                "necessary_tools": {
                    "type": "array", "items": {"type": "string"},
                    "description": "仅 must 桶需要：完成任务必须调用的工具集合",
                },
            },
            "required": ["bucket"],
        },
    },
}


# ── 1. 姿态分类 ──────────────────────────────────────────────

def classify_posture(actual_tools: Sequence[str], expected_tools: Sequence[str]) -> str:
    """把一次工具调用序列相对 expected 序列分类成四种姿态。

    - exact：实际序列 == 期望序列（标准执行）
    - under：实际零工具（先追问，ask-first）
    - over ：实际工具数 > 期望工具数（过度探索，over-explore）
    - other：长度相同但工具不同（错误工具）

    注意：这是基于「与 expected 序列的长度关系」的粗分法，是姿态的操作化定义，
    不是对「合理探索 vs 乱调」的语义判断。见论文 Limitations。
    """
    a = list(actual_tools)
    e = list(expected_tools)
    if a == e:
        return "exact"
    if len(a) == 0:
        return "under"
    if len(a) > len(e):
        return "over"
    return "other"


def posture_distribution(traces: Iterable[dict],
                         expected_by_task: dict[str, Sequence[str]]) -> dict:
    """聚合一个模型/配置的姿态占比。

    traces 中每条元素需含 task_id 与 trajectory（trajectory 里 type=='tool_call'
    的 step 有 'tool' 字段）。返回 {exact, under, over, other, total} 计数。
    """
    st = {"exact": 0, "under": 0, "over": 0, "other": 0, "total": 0}
    for t in traces:
        actual = [s["tool"] for s in t["trajectory"] if s.get("type") == "tool_call"]
        want = expected_by_task[t["task_id"]]
        st[classify_posture(actual, want)] += 1
        st["total"] += 1
    return st


# ── 2. 姿态感知评分（消融 A/B/C/D）───────────────────────────

def aggregate(scores: dict) -> float:
    """safety 乘子 + 8 维平均（复用 claw-eval 语义）。"""
    safety = scores.get("safety", 1.0)
    return safety * (sum(scores.values()) / len(scores))


def rescore(dims: dict, bucket: str, expected_tools: Sequence[str],
            actual_tools: Sequence[str], variant: str) -> dict:
    """在原始 8 维基础上按 grader 变体改写过程维，返回新的 8 维 dict。

    variant:
      baseline —— 原 rule grader（tool_selection=精确序列匹配），不改动
      A        —— 结果型：丢弃 3 个过程维（置 1）
      B        —— 分桶：optional/none 桶关闭 tool_selection + stop_decision
      C        —— B + 姿态感知 must：tool_selection 改为「必要工具 ⊆ 已调用」
      D        —— C + 放宽效率：结果已 grounded+complete 时不再罚「多调」
    """
    d = dict(dims)
    if variant == "baseline":
        return d
    if variant == "A":
        for k in PROCESS_DIMS:
            d[k] = 1.0
        return d
    if bucket in (BUCKET_OPTIONAL, BUCKET_NONE):
        d["tool_selection"] = 1.0
        d["stop_decision"] = 1.0
    if variant in ("C", "D") and bucket == BUCKET_MUST:
        need = set(expected_tools)
        got = set(actual_tools)
        d["tool_selection"] = 1.0 if need.issubset(got) else 0.0
    if variant == "D" and d.get("groundedness") == 1 and d.get("task_completion") == 1:
        d["trajectory_efficiency"] = 1.0
    return d


# ── 3. 便捷：一次把「姿态 vs 能力」拆开 ───────────────────────

def decompose_gap(rows: dict[str, dict], variants: Sequence[str]) -> dict:
    """给定各模型每 trial 的 8 维分（rows[model][trial] = dims）与 bucket/工具序列，
    返回每个 variant 下各模型的 mean aggregate。用于量化 gap inflation。

    rows 结构：{model: {"dims": [每 trial 的 8 维 dict],
                       "bucket": [每 trial 的桶],
                       "expected": [每 trial 的 expected 工具序列],
                       "actual": [每 trial 的 actual 工具序列]}}
    """
    out = {v: {} for v in variants}
    for model, r in rows.items():
        for v in variants:
            scores = [aggregate(rescore(r["dims"][i], r["bucket"][i],
                                        r["expected"][i], r["actual"][i], v))
                      for i in range(len(r["dims"]))]
            out[v][model] = sum(scores) / len(scores)
    return out


if __name__ == "__main__":
    # ── 最小可运行 demo ──
    print("=== classify_posture demo ===")
    print(classify_posture(["query_department"], ["query_department"]))              # exact
    print(classify_posture([], ["query_department"]))                                # under（先追问）
    print(classify_posture(["a", "b", "c"], ["a", "b"]))                             # over（过度探索）
    print(classify_posture(["query_department"], ["query_doctor_schedule"]))         # other

    print("\n=== rescore demo（must 桶，over 姿态，结果正确但多调）===")
    dims = dict.fromkeys(DIMS, 1.0)
    dims["tool_selection"] = 0.0          # 精确匹配判 0（实际序列 != expected）
    dims["trajectory_efficiency"] = 0.5   # 多调被扣
    for v in ("baseline", "A", "B", "C", "D"):
        nd = rescore(dims, BUCKET_MUST, ["a", "b"], ["a", "b", "c"], v)
        print(f"  {v:<9} aggregate={aggregate(nd):.3f}  tool_selection={nd['tool_selection']} "
              f"efficiency={nd['trajectory_efficiency']}")
    print("\n（baseline 罚了 over 姿态；D 把「结果对但多调」恢复为满分）")
