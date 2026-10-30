# -*- coding: utf-8 -*-
"""诊断：分桶下 tool_selection=0 但 groundedness=1 & completion=1 的 trial 到底发生了什么。"""
import json
from pathlib import Path
from tool_requirement import TOOL_REQUIREMENT

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge"

def load(rel):
    traces = [json.loads(l) for l in open(REPORTS / rel / "real_traces.jsonl", encoding="utf-8")]
    rule = json.load(open(REPORTS / rel / "rule_scores.json", encoding="utf-8"))
    return traces, rule

def show(name, rel, bucket_filter=None, limit=12):
    traces, rule = load(rel)
    print(f"\n{'='*70}\n{name}  [{rel}]")
    n = 0
    for t in traces:
        tid = t["task_id"]
        b = TOOL_REQUIREMENT[tid]
        if bucket_filter and b != bucket_filter:
            continue
        s = rule[tid][str(t["trial"])]
        if s["tool_selection"] == 0 and s["groundedness"] == 1 and s["task_completion"] == 1:
            calls = [(x["tool"], x["args"]) for x in t["trajectory"] if x["type"] == "tool_call"]
            final = [x["text"] for x in t["trajectory"] if x["type"] == "final_answer"]
            final = final[0][:60] if final else "(无)"
            print(f"  [{b}] {tid} trial{t['trial']} tools={calls} final={final}")
            n += 1
            if n >= limit:
                print(f"  ... (截断)")
                return

# 1) MiniMax optional 桶（核心信号）
show("MiniMax-M3", "multimodel/minimax-m3__t0.0", "optional", limit=20)
# 2) v4pro must 桶（看是否跳过工具/调不同工具）
show("v4-pro", "real_eval_pro", "must", limit=8)
# 3) MiniMax must 桶
show("MiniMax-M3", "multimodel/minimax-m3__t0.0", "must", limit=8)
