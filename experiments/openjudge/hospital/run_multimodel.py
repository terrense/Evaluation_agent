# -*- coding: utf-8 -*-
"""多模型 × 温度 统一评测 runner。

每个 (provider, temperature) 配置：100 样本 × 3 trial 真实 Agent → rule 8 维 → LLM-as-Judge。
输出到 reports/openjudge/multimodel/{out}/

- 实验 A（一致性）：temp=0.3 引入真实随机性，量化 单次 vs Pass@3 vs Pass^3
- 实验 B（分桶）  ：由 analyze_multimodel.py 对 temp=0 数据按 tool_requirement 分桶
- 多模型对比     ：5 家族 22 模型（DeepSeek / MiniMax / Qwen / Kimi / GLM）× 8 维
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from samples import SAMPLES
from graders_rule import RULE_GRADERS
from real_agent import run_agent
from providers import get_client
from llm_judge import SYSTEM_PROMPT as JUDGE_SYSTEM, DIMS, _parse_json

BASE = Path(__file__).resolve().parents[3] / "reports" / "openjudge" / "multimodel"
N_TRIALS = 3
CONCURRENCY = 6
JUDGE_PROVIDER = "v4pro"  # 统一 judge（v4pro 自评存在自偏好偏差，报告里会注明）

# (provider, temperature, 输出目录名)
# 2026-11-02 扩到 5 家族 22 模型 × temp=0（主对比，100 样本确定性）：
#   DeepSeek: flash / v4pro；MiniMax: m3 / m2.5；Qwen: 自托管 32b/8b + 云端 3.5~3.8 全线；
#   Kimi: k3 / k2.7-code；GLM: 5.3 / 5.3-prime / 5.2。
#   注：qwen3-max 已于 2026-10-10 下线，改用 qwen3.8-max（见 providers.py）。
# 注：tools.py 已内置日期归一化，此轮重跑的所有目录天然是「fixed」版，
#     不再需要 minimax-m3__t0.0_fixed 这类单独修补目录。
CONFIGS = [
    # ── 主对比（temp=0，100 样本 × 3 trial，5 家族 22 模型）──
    # DeepSeek
    ("flash",        0.0, "flash__t0.0"),
    ("v4pro",        0.0, "v4pro__t0.0"),
    # MiniMax
    ("minimax-m3",   0.0, "minimax-m3__t0.0"),
    ("minimax-m2.5", 0.0, "minimax-m2.5__t0.0"),
    # Qwen 自托管（H20）
    ("qwen3-32b",    0.0, "qwen3-32b__t0.0"),
    ("qwen3-8b",     0.0, "qwen3-8b__t0.0"),
    # Qwen 云端
    ("qwen3.8-max",  0.0, "qwen3.8-max__t0.0"),
    ("qwen3.7-max",  0.0, "qwen3.7-max__t0.0"),
    ("qwen3.8-flash",0.0, "qwen3.8-flash__t0.0"),
    ("qwen3.8-2.4t-a95b", 0.0, "qwen3.8-2.4t-a95b__t0.0"),
    ("qwen3.7-flash",0.0, "qwen3.7-flash__t0.0"),
    ("qwen3.7-plus", 0.0, "qwen3.7-plus__t0.0"),
    ("qwen3.6-plus", 0.0, "qwen3.6-plus__t0.0"),
    ("qwen3.5-plus", 0.0, "qwen3.5-plus__t0.0"),
    ("qwen-max",     0.0, "qwen-max__t0.0"),
    ("qwen-plus",    0.0, "qwen-plus__t0.0"),
    ("qwen-flash",   0.0, "qwen-flash__t0.0"),
    # Kimi
    ("kimi-k3",      0.0, "kimi-k3__t0.0"),
    ("kimi-k2.7-code", 0.0, "kimi-k2.7-code__t0.0"),
    # GLM
    ("glm-5.3",      0.0, "glm-5.3__t0.0"),
    ("glm-5.3-prime",0.0, "glm-5.3-prime__t0.0"),
    ("glm-5.2",      0.0, "glm-5.2__t0.0"),
    # ── 实验 A（一致性，temp=0.3，可选，跑完主对比再开）──
    # ("flash",      0.3, "flash__t0.3"),
    # ("v4pro",      0.3, "v4pro__t0.3"),
]


async def run_agents(client, model: str, temperature: float) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def _one(sample: dict, trial: int) -> dict:
        async with sem:
            traj, final = await run_agent(client, model, sample["input"], temperature=temperature)
            return {"task_id": sample["task_id"], "scenario": sample["scenario"],
                    "trial": trial, "query": sample["input"],
                    "trajectory": traj, "final": final}

    tasks = [_one(s, t) for s in SAMPLES for t in range(N_TRIALS)]
    results = []
    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        results.append(await coro)
        if i % 15 == 0:
            print(f"    agent {i}/{len(tasks)}")
    results.sort(key=lambda r: (r["task_id"], r["trial"]))
    return results


async def rule_score(traces: list[dict]) -> dict:
    by_id = {s["task_id"]: s["expected"] for s in SAMPLES}
    out: dict = {}
    for t in traces:
        expected = by_id[t["task_id"]]
        scores = {}
        for dim, fn in RULE_GRADERS.items():
            r = await fn(trajectory=t["trajectory"], expected=expected)
            scores[dim] = r.score
        out.setdefault(t["task_id"], {})[t["trial"]] = scores
    return out


async def llm_score(judge_client, judge_model: str, traces: list[dict]) -> list[dict]:
    trial0 = [t for t in traces if t["trial"] == 0]
    out = []
    for t in trial0:
        traj = json.dumps(t["trajectory"], ensure_ascii=False)
        user = f"用户输入：{t['query']}\n\nAgent 轨迹（JSON）：\n{traj}"
        resp = await asyncio.to_thread(
            judge_client.chat.completions.create,
            model=judge_model,
            messages=[{"role": "system", "content": JUDGE_SYSTEM},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"}, temperature=0.0,
        )
        raw = resp.choices[0].message.content or "{}"
        try:
            parsed = _parse_json(raw)
        except Exception as e:
            print(f"    [judge parse fail {t['task_id']}] {e}")
            parsed = {}
        dims = {k: float(parsed.get(k, 0.0)) for k in DIMS}
        out.append({"task_id": t["task_id"], "scenario": t["scenario"],
                    "query": t["query"], "score": float(parsed.get("score", 0.0)),
                    "reason": str(parsed.get("reason", ""))[:300], "dims": dims})
    return out


async def run_one(provider: str, temperature: float, out_name: str) -> Path:
    out_dir = BASE / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    client, model = get_client(provider)
    judge_client, judge_model = get_client(JUDGE_PROVIDER)
    print(f"\n=== [{out_name}] provider={provider} model={model} temp={temperature} ===")

    traces = await run_agents(client, model, temperature)
    (out_dir / "real_traces.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8")
    print(f"  ✅ traces {len(traces)} 条")

    rule = await rule_score(traces)
    (out_dir / "rule_scores.json").write_text(json.dumps(rule, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  ✅ rule 8 维")

    llm = await llm_score(judge_client, judge_model, traces)
    (out_dir / "llm_scores.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in llm) + "\n", encoding="utf-8")
    print("  ✅ LLM-as-Judge")
    return out_dir


async def main() -> None:
    for provider, temp, name in CONFIGS:
        await run_one(provider, temp, name)
    print("\n✅ 全部配置完成")


if __name__ == "__main__":
    asyncio.run(main())
