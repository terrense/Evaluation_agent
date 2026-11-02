# -*- coding: utf-8 -*-
"""把工具依赖度标注导出为 JSON（posture_grader.ANNOTATION_SCHEMA 的实例）。

合并两处来源：
  tool_requirement.py  → 每个 task_id 的桶（must/optional/none）
  samples.py           → must 桶的 necessary_tools = expected.correct_tools

输出：experiments/openjudge/hospital/annotation.json（可随 posture_grader 一起发布）
"""
from __future__ import annotations

import json
from pathlib import Path

from samples import SAMPLES
from tool_requirement import TOOL_REQUIREMENT

HERE = Path(__file__).resolve().parent
OUT = HERE / "annotation.json"

CORRECT_TOOLS = {s["task_id"]: s["expected"]["correct_tools"] for s in SAMPLES}

annotation = {}
counts = {"must": 0, "optional": 0, "none": 0}
for tid, bucket in sorted(TOOL_REQUIREMENT.items()):
    entry: dict = {"bucket": bucket}
    if bucket == "must":
        entry["necessary_tools"] = CORRECT_TOOLS.get(tid, [])
    annotation[tid] = entry
    counts[bucket] += 1

# 顶层加统计，便于评审者一眼看清桶分布
payload = {
    "_description": "Tool-dependency annotation for the hospital triage benchmark "
                    "(see posture_grader.ANNOTATION_SCHEMA). must 桶附带 necessary_tools。",
    "_counts": counts,
    "tasks": annotation,
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"✅ 已导出 {len(annotation)} 个任务的标注 → {OUT}")
print(f"   桶分布: must={counts['must']}  optional={counts['optional']}  none={counts['none']}")
