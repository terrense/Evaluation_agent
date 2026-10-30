# -*- coding: utf-8 -*-
"""MiniMax-M3 工具调用冒烟测试：确认 function-calling 可用，轨迹格式正确。"""
import asyncio
from providers import get_client
from real_agent import run_agent


async def main():
    client, model = get_client("minimax-m3")
    queries = [
        "我最近一直咳嗽发烧，该挂哪个科？",   # optional：可能直接答
        "呼吸内科在几楼？",                    # must：必须调工具
        "帮我挂呼吸内科王医生周一的号",          # must：多工具链
    ]
    for q in queries:
        traj, final = await run_agent(client, model, q, temperature=0.0)
        print("=" * 60)
        print(f"Q: {q}")
        for step in traj:
            if step["type"] == "tool_call":
                print(f"  [tool] {step['tool']}{step['args']}")
            else:
                print(f"  [final] {step['text'][:80]}")
        print(f"  工具调用数 = {sum(1 for s in traj if s['type']=='tool_call')}")


if __name__ == "__main__":
    asyncio.run(main())
