# -*- coding: utf-8 -*-
"""补跑 flash__t0.3 的 LLM-as-Judge（并行 + 超时，只 judge 30 条 trial 0）。"""
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from providers import get_client
from llm_judge import SYSTEM_PROMPT as JUDGE_SYSTEM, DIMS, _parse_json

BASE = Path(__file__).resolve().parents[3] / "reports" / "openjudge" / "multimodel"
OUT = BASE / "flash__t0.3"
CONCURRENCY = 8


async def judge_one(client, model, t, sem):
    async with sem:
        traj = json.dumps(t["trajectory"], ensure_ascii=False)
        user = f"用户输入：{t['query']}\n\nAgent 轨迹（JSON）：\n{traj}"
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[{"role": "system", "content": JUDGE_SYSTEM},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"}, temperature=0.0, timeout=180,
        )
        raw = resp.choices[0].message.content or "{}"
        try:
            parsed = _parse_json(raw)
        except Exception as e:
            print(f"  [parse fail {t['task_id']}] {e}")
            parsed = {}
        dims = {k: float(parsed.get(k, 0.0)) for k in DIMS}
        return {"task_id": t["task_id"], "scenario": t["scenario"],
                "query": t["query"], "score": float(parsed.get("score", 0.0)),
                "reason": str(parsed.get("reason", ""))[:300], "dims": dims}


async def main():
    client, model = get_client("v4pro")
    traces = [json.loads(l) for l in open(OUT / "real_traces.jsonl", encoding="utf-8")]
    trial0 = [t for t in traces if t["trial"] == 0]
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(judge_one(client, model, t, sem) for t in trial0))
    results.sort(key=lambda r: r["task_id"])
    (OUT / "llm_scores.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n", encoding="utf-8")
    print(f"✅ flash__t0.3 LLM-judge 补跑完成，{len(results)} 条 → llm_scores.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
