# -*- coding: utf-8 -*-
"""量化 mock 日期修复对 over-explore 姿态的影响（#20 核心）。

读旧 mock（minimax-m3__t0.0）与新 mock（minimax-m3__t0.0_fixed）的 real_traces.jsonl，
比较：
  1. 四姿态分布（exact/under/over/other）——用与 report_multimodel_html.posture 一致的分类
  2. over-explore 率的变化（预期 80% → ~53%）
  3. 旧 run 的 over-explore trial 里，有多少是「脆性日期」驱动的（传了非规范日期）

结论锚点：修复日期后 over-explore 即便从 80% 降到 ~53%，仍远高于 DeepSeek 的 3-10%，
所以「姿态多样性」的论点不变、反而更可信（排除了 mock 假阳性）。
"""
from __future__ import annotations

import json
from pathlib import Path

from posture_grader import classify_posture
from samples import SAMPLES

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge" / "multimodel"
OLD = REPORTS / "minimax-m3__t0.0" / "real_traces.jsonl"
NEW = REPORTS / "minimax-m3__t0.0_fixed" / "real_traces.jsonl"

EXPECTED = {s["task_id"]: s["expected"]["correct_tools"] for s in SAMPLES}

# 非规范日期（旧 mock 会误报「停诊」的日期表达）
BRITTLE_DATE_HINTS = ("-", "/", ".", "年", "今天", "明天", "后天", "本周", "下周", "星期")


def _has_brittle_date(trace: dict) -> bool:
    for s in trace["trajectory"]:
        if s.get("type") == "tool_call" and s.get("tool") in ("query_doctor_schedule",
                                                               "create_mock_appointment"):
            d = str(s.get("args", {}).get("date", ""))
            if d and any(h in d for h in BRITTLE_DATE_HINTS):
                return True
    return False


def distribution(path: Path) -> tuple[dict, list[dict]]:
    traces = [json.loads(l) for l in open(path, encoding="utf-8")]
    st = {"exact": 0, "under": 0, "over": 0, "other": 0, "total": 0}
    over_traces = []
    for t in traces:
        actual = [s["tool"] for s in t["trajectory"] if s.get("type") == "tool_call"]
        want = EXPECTED[t["task_id"]]
        p = classify_posture(actual, want)
        st[p] += 1
        st["total"] += 1
        if p == "over":
            over_traces.append(t)
    return st, over_traces


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:.1f}%"


def main() -> None:
    old_st, old_over = distribution(OLD)
    new_st, new_over = distribution(NEW)

    def row(label, st):
        t = st["total"]
        print(f"  {label:16s} exact={st['exact']:2d}({pct(st['exact'],t)})  "
              f"under={st['under']:2d}({pct(st['under'],t)})  "
              f"over={st['over']:2d}({pct(st['over'],t)})  "
              f"other={st['other']:2d}({pct(st['other'],t)})  total={t}")

    print("=== MiniMax-M3 temp=0 姿态分布（旧 mock vs 新 mock）===")
    row("旧 mock", old_st)
    row("新 mock", new_st)

    # over-explore 率变化
    old_over_rate = old_st["over"] / old_st["total"]
    new_over_rate = new_st["over"] / new_st["total"]
    print(f"\nover-explore 率：旧 {old_over_rate:.1%} → 新 {new_over_rate:.1%} "
          f"（Δ {new_over_rate - old_over_rate:+.1%}）")

    # 旧 run 的 over 里，多少是脆性日期驱动
    brittle = sum(1 for t in old_over if _has_brittle_date(t))
    print(f"旧 run 的 {len(old_over)} 个 over-explore trial 中，"
          f"{brittle} 个（{pct(brittle, len(old_over))}）含非规范日期参数（脆性日期）")
    nb = len(old_over) - brittle
    print(f"  → 非脆性日期驱动的 over 有 {nb} 个（{pct(nb, len(old_over))}）")

    out = {
        "old": old_st, "new": new_st,
        "old_over_rate": old_over_rate, "new_over_rate": new_over_rate,
        "delta_over_rate": new_over_rate - old_over_rate,
        "old_over_brittle_date": brittle, "old_over_nonbrittle": nb,
    }
    (REPORTS / "overexplore_quantify.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 已写 {REPORTS / 'overexplore_quantify.json'}")


if __name__ == "__main__":
    main()
