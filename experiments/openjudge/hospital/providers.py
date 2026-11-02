# -*- coding: utf-8 -*-
"""多模型 provider 注册表：统一 OpenAI 兼容 client 工厂。

三家公司（DeepSeek / MiniMax）均暴露 OpenAI 兼容接口，区别仅在 base_url + model 名。
新增模型只需在此登记一条。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

PROVIDERS: dict[str, dict] = {
    # DeepSeek（同一把 key，两个模型）
    "flash":        {"key_env": "OPENAI_API_KEY", "base_env": "OPENAI_BASE_URL", "model": "deepseek-flash"},
    "v4pro":        {"key_env": "OPENAI_API_KEY", "base_env": "OPENAI_BASE_URL", "model": "deepseek-v4-pro"},
    # MiniMax（用户提供的第二把 key）
    "minimax-m3":   {"key_env": "MINIMAX_API_KEY", "base_env": "MINIMAX_BASE_URL", "model": "MiniMax-M3"},
    "minimax-flash":{"key_env": "MINIMAX_API_KEY", "base_env": "MINIMAX_BASE_URL", "model": "MiniMax-M3.1-Flash"},
    # Qwen3 开源权重（H20 自托管 vLLM，OpenAI 兼容；key 填 EMPTY）
    #   model 名 = vLLM 的 --served-model-name，见 docs/h20-qwen3-deploy.md
    "qwen3-32b":    {"key_env": "QWEN_H20_KEY", "base_env": "QWEN_H20_BASE", "model": "qwen3-32b"},
    "qwen3-30b-a3b":{"key_env": "QWEN_H20_KEY", "base_env": "QWEN_H20_BASE", "model": "qwen3-30b-a3b"},
    # Qwen3-Max 专有模型（阿里云百炼 DashScope 兼容模式；不可自托管）
    "qwen3-max":    {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.8-max"},
}


def get_client(name: str):
    """返回 (OpenAI client, model 名)。"""
    p = PROVIDERS[name]
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv(p["key_env"]), base_url=os.getenv(p["base_env"]))
    return client, p["model"]


if __name__ == "__main__":
    for name in PROVIDERS:
        c, m = get_client(name)
        print(f"{name:14s} -> {m}")
