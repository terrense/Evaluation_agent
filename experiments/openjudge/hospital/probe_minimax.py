# -*- coding: utf-8 -*-
"""MiniMax API 探测：确认 base_url + 可用模型列表（OpenAI 兼容接口）。"""
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from openai import OpenAI

KEY = os.getenv("MINIMAX_API_KEY")
BASE_URLS = [
    "https://api.minimaxi.com/v1",
    "https://api.minimax.chat/v1",
    "https://api.minimax.io/v1",
    "https://api.minimax.chat",
    "https://api.minimaxi.com",
]

for base in BASE_URLS:
    try:
        c = OpenAI(api_key=KEY, base_url=base, timeout=30)
        models = c.models.list()
        ids = [m.id for m in models.data]
        print(f"[OK] base_url={base}")
        print(f"  模型数={len(ids)}")
        for i in ids[:40]:
            print(f"    - {i}")
        break
    except Exception as e:
        print(f"[FAIL] base_url={base} -> {type(e).__name__}: {e}")
