# -*- coding: utf-8 -*-
"""探测 MiniMax-M3 原始响应：content / reasoning_content / tool_calls 结构。"""
import json
from providers import get_client
from real_agent import TOOL_SCHEMAS, SYSTEM_PROMPT


def main():
    client, model = get_client("minimax-m3")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": "呼吸内科在几楼？"}],
        tools=TOOL_SCHEMAS, tool_choice="auto", temperature=0.0,
    )
    msg = resp.choices[0].message
    print("=== message 字段 ===")
    print("content:", repr(msg.content))
    print("reasoning_content:", repr(getattr(msg, "reasoning_content", None)))
    print("tool_calls:", repr(getattr(msg, "tool_calls", None)))
    # 完整响应 JSON 的顶层 keys
    raw = json.loads(resp.model_dump_json())
    print("=== 顶层 keys ===", list(raw["choices"][0]["message"].keys()))


if __name__ == "__main__":
    main()
