# -*- coding: utf-8 -*-
"""增量补跑新样本（H101-H172）：把 72 条新样本补进 21 模型的现有结果，不重跑已完成的 H001-H100。

run_multimodel.py 的断点续跑是「阶段级」的：real_traces.jsonl 存在就整份复用，不会补新增样本。
本脚本按 (task_id, trial) 粒度补缺：
  对每个 temp=0 模型：找出 real_traces.jsonl 里缺失的 (task_id, trial) → 只跑这些 →
  追加 traces / 合并 rule_scores.json / 追加 llm_scores.jsonl。
跑完后再跑 analyze_multimodel.py / statistical_significance.py / ablation_posture_grader.py
即得 172 样本口径。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from samples import SAMPLES
from providers import get_client
from run_multimodel import (
    BASE, CONFIGS, N_TRIALS, CONCURRENCY, JUDGE_PROVIDER,
    run_agent, rule_score, llm_score,
)


async def run_missing_agents(client, model: str, temperature: float, existing: set) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def _one(sample: dict, trial: int) -> dict:
        async with sem:
            last_err = None
            for _ in range(2):  # 容忍瞬时限流/超时，重试一次
                try:
                    traj, final = await run_agent(client, model, sample["input"], temperature=temperature)
                    return {"task_id": sample["task_id"], "scenario": sample["scenario"],
                            "trial": trial, "query": sample["input"],
                            "trajectory": traj, "final": final}
                except Exception as e:
                    last_err = e
                    await asyncio.sleep(3)
            traj = [{"type": "final_answer", "text": f"(运行异常：{type(last_err).__name__})"}]
            return {"task_id": sample["task_id"], "scenario": sample["scenario"],
                    "trial": trial, "query": sample["input"],
                    "trajectory": traj, "final": traj[-1]["text"]}

    missing = [(s, t) for s in SAMPLES for t in range(N_TRIALS)
               if (s["task_id"], t) not in existing]
    if not missing:
        return []
    results = []
    coros = [_one(s, t) for s, t in missing]
    for i, coro in enumerate(asyncio.as_completed(coros), 1):
        results.append(await coro)
        if i % 30 == 0:
            print(f"    agent {i}/{len(missing)}", flush=True)
    results.sort(key=lambda r: (r["task_id"], r["trial"]))
    return results


async def incremental_one(provider: str, temperature: float, out_name: str) -> bool:
    out_dir = BASE / out_name
    traces_path = out_dir / "real_traces.jsonl"
    rule_path = out_dir / "rule_scores.json"
    llm_path = out_dir / "llm_scores.jsonl"

    # 已有 traces 的 (task_id, trial) 集合
    existing: set = set()
    if traces_path.exists():
        for l in traces_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                t = json.loads(l)
                existing.add((t["task_id"], t["trial"]))

    # 已有 llm judge 的 task_id 集合（judge 条目无 trial，隐式 trial=0）
    llm_existing: set = set()
    if llm_path.exists():
        for l in llm_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                llm_existing.add(json.loads(l)["task_id"])

    need = [(s["task_id"], t) for s in SAMPLES for t in range(N_TRIALS)
            if (s["task_id"], t) not in existing]
    need_llm_ids = [s["task_id"] for s in SAMPLES if s["task_id"] not in llm_existing]

    if not need and not need_llm_ids:
        print(f"[{out_name}] 已覆盖 {len(existing) // N_TRIALS} 样本 + {len(llm_existing)} judge，跳过", flush=True)
        return False

    client, model = get_client(provider)
    judge_client, judge_model = get_client(JUDGE_PROVIDER)
    did_work = False

    # 1) agent 阶段（缺 traces 才跑）
    if need:
        print(f"\n=== [{out_name}] 缺 {len(need)} 个 (task,trial)，补跑 ===", flush=True)
        new_traces = await run_missing_agents(client, model, temperature, existing)
        if new_traces:
            with open(traces_path, "a", encoding="utf-8") as f:
                for t in new_traces:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
            print(f"  ✅ 追加 traces {len(new_traces)} 条", flush=True)

        # 2) rule 阶段（只对新增 traces 重算，再合并）
        if new_traces:
            new_rule = await rule_score(new_traces)
            rule = json.loads(rule_path.read_text(encoding="utf-8")) if rule_path.exists() else {}
            for tid, trials in new_rule.items():
                rule.setdefault(tid, {}).update(trials)
            rule_path.write_text(json.dumps(rule, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✅ 合并 rule（新增 {len(new_rule)} task）", flush=True)

        # 3) LLM-as-Judge 阶段（只对新增 trial=0）
        new_t0 = [t for t in new_traces if t["trial"] == 0]
        if new_t0:
            new_llm = await llm_score(judge_client, judge_model, new_t0)
            with open(llm_path, "a", encoding="utf-8") as f:
                for r in new_llm:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"  ✅ 追加 llm {len(new_llm)} 条", flush=True)
        did_work = True

    # 4) llm-only 补缺：traces 已全、judge 缺（如 judge API 中途挂掉）
    if need_llm_ids:
        cur = set()
        if llm_path.exists():
            for l in llm_path.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    cur.add(json.loads(l)["task_id"])
        still = [sid for sid in need_llm_ids if sid not in cur]
        if still:
            t0: dict[str, dict] = {}
            for l in traces_path.read_text(encoding="utf-8").splitlines():
                t = json.loads(l)
                if t["trial"] == 0 and t["task_id"] in still:
                    t0[t["task_id"]] = t
            missing_t0 = [t0[sid] for sid in still if sid in t0]
            if missing_t0:
                print(f"[{out_name}] 补 judge {len(missing_t0)} 条（traces 已全）", flush=True)
                new_llm = await llm_score(judge_client, judge_model, missing_t0)
                with open(llm_path, "a", encoding="utf-8") as f:
                    for r in new_llm:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                print(f"  ✅ 追加 llm {len(new_llm)} 条", flush=True)
                did_work = True

    return did_work


async def main(limit: int | None = None) -> None:
    done = 0
    for provider, temp, name in CONFIGS:
        if limit is not None and done >= limit:
            break
        try:
            if await incremental_one(provider, temp, name):
                done += 1
        except Exception as e:
            print(f"\n  ❌ [{name}] 失败：{type(e).__name__}: {e}\n", flush=True)
            done += 1  # 计数失败，避免卡在同一个模型
    print(f"\n✅ 本批完成（实际处理 {done} 个模型）")


if __name__ == "__main__":
    import sys
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    asyncio.run(main(limit))
