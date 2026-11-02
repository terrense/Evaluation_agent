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
    # ── DeepSeek（直连，同一把 key）──
    "flash":         {"key_env": "OPENAI_API_KEY", "base_env": "OPENAI_BASE_URL", "model": "deepseek-flash"},
    "v4pro":         {"key_env": "OPENAI_API_KEY", "base_env": "OPENAI_BASE_URL", "model": "deepseek-v4-pro"},
    # ── MiniMax（M3/M3.1-Flash 走直连 key；M2.5 走 MaaS）──
    "minimax-m3":    {"key_env": "MINIMAX_API_KEY", "base_env": "MINIMAX_BASE_URL", "model": "MiniMax-M3"},
    "minimax-flash": {"key_env": "MINIMAX_API_KEY", "base_env": "MINIMAX_BASE_URL", "model": "MiniMax-M3.1-Flash"},
    "minimax-m2.5":  {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "MiniMax-M2.5"},
    # ── Qwen 开源权重（H20 自托管 vLLM，OpenAI 兼容；key 填 EMPTY）──
    #   model 名 = vLLM 的 --served-model-name，见 docs/h20-qwen3-deploy.md
    "qwen3-32b":     {"key_env": "QWEN_H20_KEY", "base_env": "QWEN_H20_BASE", "model": "qwen3-32b"},
    "qwen3-8b":      {"key_env": "QWEN_H20_KEY", "base_env": "QWEN_H20_BASE_8B", "model": "qwen3-8b"},
    # ── Qwen 云端（MaaS/百炼，同一把 DASHSCOPE key；qwen3-max 已于 2026-10-10 下线不登记）──
    "qwen3.8-max":   {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.8-max"},
    "qwen3.7-max":   {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.7-max"},
    "qwen3.8-flash": {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.8-flash"},
    "qwen3.8-2.4t-a95b": {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.8-2.4t-a95b"},
    "qwen3.7-flash": {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.7-flash"},
    "qwen3.7-plus":  {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.7-plus"},
    "qwen3.6-plus":  {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.6-plus"},
    "qwen3.5-plus":  {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen3.5-plus"},
    "qwen-max":      {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen-max"},
    "qwen-plus":     {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen-plus"},
    "qwen-flash":    {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "qwen-flash"},
    # ── Kimi（月之暗面，经 MaaS）──
    "kimi-k3":       {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "kimi-k3"},
    "kimi-k2.7-code": {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "kimi-k2.7-code"},
    # ── GLM（智谱，经 MaaS）──
    "glm-5.3":       {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "glm-5.3"},
    "glm-5.3-prime": {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "glm-5.3-prime"},
    "glm-5.2":       {"key_env": "DASHSCOPE_API_KEY", "base_env": "DASHSCOPE_BASE_URL", "model": "glm-5.2"},
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
