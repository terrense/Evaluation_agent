# -*- coding: utf-8 -*-
"""用「日期归一化后的 mock」重跑评测，量化 over-explore 姿态的真实性。

背景：原 mock 只认「周一~周日」字面值，模型传 ISO 日期/相对日期会被误报「停诊」，
放大过度探索姿态（见 docs/论文自查.md P0）。tools.py 已加入 _normalize_date 修复。

本脚本复用 run_multimodel.run_one，输出到 *_fixed 目录，不与旧结果（旧 mock）混淆。
"""
from __future__ import annotations

import asyncio

from run_multimodel import run_one

# (provider, temperature, 输出目录名) —— 输出到 *_fixed 以区分旧 mock 结果
CONFIGS = [
    ("minimax-m3", 0.0, "minimax-m3__t0.0_fixed"),
    # 后续一致性重跑（同 mock 才能横向比）：
    # ("flash", 0.0, "flash__t0.0_fixed"),
    # ("v4pro", 0.0, "v4pro__t0.0_fixed"),
    # ("flash", 0.3, "flash__t0.3_fixed"),
    # ("v4pro", 0.3, "v4pro__t0.3_fixed"),
]


async def main() -> None:
    for provider, temp, name in CONFIGS:
        await run_one(provider, temp, name)
    print("\n✅ 全部重跑完成")


if __name__ == "__main__":
    asyncio.run(main())
