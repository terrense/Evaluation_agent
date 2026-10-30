# -*- coding: utf-8 -*-
"""真实 Agent 全量评测：DeepSeek 驱动 30 样本 × 3 trial + 双 Grader 评分。

流程：
  1. 用 deepseek-flash 驱动真实 Agent 跑 30 条样本 × 3 trial（并发），收集真实轨迹
  2. 对每条轨迹跑 8 维 rule-based grader
  3. 对 30 条样本（trial 0）跑 LLM-as-Judge（deepseek-v4-pro）
  4. 保存原始结果到 reports/openjudge/real_eval/

之后由 make_report.py 读结果 → 算指标 → 画图 → 生成大厂规范报告。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from samples import SAMPLES
from graders_rule import RULE_GRADERS
from real_agent import run_agent
from llm_judge import SYSTEM_PROMPT as JUDGE_SYSTEM, DIMS, _parse_json

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

AGENT_MODEL = "deepseek-flash"
JUDGE_MODEL = "deepseek-v4-pro"
N_TRIALS = 3
CONCURRENCY = 6

OUT_DIR = Path(__file__).resolve().parents[3] / "reports" / "openjudge" / "real_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── 1. 真实 Agent 运行（并发）─────────────────────────────────

async def run_all_agents(client, agent_model: str) -> list[dict]:
    """30 样本 × 3 trial 并发跑真实 Agent，返回 [{task_id, trial, query, trajectory, final}]。"""
    sem = asyncio.Semaphore(CONCURRENCY)
    results: list[dict] = []

    async def _one(sample: dict, trial: int) -> dict:
        async with sem:
            traj, final = await run_agent(client, agent_model, sample["input"])
            return {"task_id": sample["task_id"], "scenario": sample["scenario"],
                    "trial": trial, "query": sample["input"],
                    "trajectory": traj, "final": final}

    tasks = [_one(s, t) for s in SAMPLES for t in range(N_TRIALS)]
    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        results.append(await coro)
        if i % 10 == 0:
            print(f"  agent 运行进度 {i}/{len(tasks)}")
    # 排序：task_id → trial
    results.sort(key=lambda r: (r["task_id"], r["trial"]))
    return results


# ── 2. rule-based 评分 ────────────────────────────────────────

async def score_rule_based(traces: list[dict]) -> dict:
    """对每条轨迹跑 8 维 rule-based grader。"""
    by_id = {s["task_id"]: s["expected"] for s in SAMPLES}
    out: dict[str, dict[int, dict[str, float]]] = {}
    for t in traces:
        expected = by_id[t["task_id"]]
        scores = {}
        for dim, fn in RULE_GRADERS.items():
            r = await fn(trajectory=t["trajectory"], expected=expected)
            scores[dim] = r.score
        out.setdefault(t["task_id"], {})[t["trial"]] = scores
    return out


# ── 3. LLM-as-Judge 评分 ──────────────────────────────────────

async def score_llm(client, traces: list[dict]) -> list[dict]:
    """对 30 条样本（trial 0）跑 LLM-as-Judge。"""
    trial0 = [t for t in traces if t["trial"] == 0]
    out = []
    for t in trial0:
        traj = json.dumps(t["trajectory"], ensure_ascii=False)
        user = f"用户输入：{t['query']}\n\nAgent 轨迹（JSON）：\n{traj}"
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=JUDGE_MODEL,
            messages=[{"role": "system", "content": JUDGE_SYSTEM},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw = resp.choices[0].message.content or "{}"
        try:
            parsed = _parse_json(raw)
        except Exception as e:
            print(f"  [LLM 解析失败 {t['task_id']}] {e}")
            parsed = {}
        dims = {k: float(parsed.get(k, 0.0)) for k in DIMS}
        out.append({"task_id": t["task_id"], "scenario": t["scenario"],
                    "query": t["query"], "score": float(parsed.get("score", 0.0)),
                    "reason": str(parsed.get("reason", ""))[:300], "dims": dims})
    return out


# ── 主流程 ────────────────────────────────────────────────────

async def main(agent_model: str = "deepseek-flash", out_name: str = "real_eval") -> None:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
    out_dir = Path(__file__).resolve().parents[3] / "reports" / "openjudge" / out_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== 真实 Agent 全量评测：30 样本 × {N_TRIALS} trial（Agent={agent_model}）===")
    traces = await run_all_agents(client, agent_model)
    (out_dir / "real_traces.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8")
    print(f"✅ 轨迹保存 → real_traces.jsonl（{len(traces)} 条）")

    print("\n=== rule-based 8 维评分 ===")
    rule = await score_rule_based(traces)
    (out_dir / "rule_scores.json").write_text(json.dumps(rule, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✅ rule-based 评分 → rule_scores.json")

    print(f"\n=== LLM-as-Judge 评分（{JUDGE_MODEL}，30 条 trial 0）===")
    llm = await score_llm(client, traces)
    (out_dir / "llm_scores.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in llm) + "\n", encoding="utf-8")
    print("✅ LLM-as-Judge 评分 → llm_scores.jsonl")

    print("\n=== 完成，运行 make_report.py 生成图表与报告 ===")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="真实 Agent 全量评测")
    p.add_argument("--agent-model", default="deepseek-flash")
    p.add_argument("--out", default="real_eval")
    args = p.parse_args()
    asyncio.run(main(args.agent_model, args.out))
