# -*- coding: utf-8 -*-
"""LLMGrader 核心链路 smoke test：用 fake model 替代真实 API，
验证「prompt 构造 → 模型调用 → structured output 解析 → GraderScore」链路。

目的：在无 API key 情况下，确认 LLMGrader 的 API 与官方 README 一致，
LLM-as-Judge 的骨架已可用（仅缺真实模型后端）。
"""
import asyncio
from types import SimpleNamespace

from pydantic import BaseModel, Field

from openjudge.graders.llm_grader import LLMGrader
from openjudge.graders.schema import GraderMode


class JudgeOutput(BaseModel):
    reason: str
    score: float
    intent_accuracy: float = 0.0
    safety: float = 0.0


class FakeModel:
    """Duck-typed fake model：返回预置 structured 结果，不调真实 API。"""

    def __init__(self, parsed: dict):
        self._parsed = parsed
        self.last_messages = None
        self.last_structured_model = None

    async def achat(self, messages, structured_model=None, callback=None, **kw):
        self.last_messages = messages
        self.last_structured_model = structured_model
        return SimpleNamespace(parsed=self._parsed)


TEMPLATE = "评估以下回答。用户输入：{input} 轨迹：{trajectory}"


async def main() -> None:
    fake = FakeModel({"reason": "总体表现良好", "score": 0.85,
                      "intent_accuracy": 0.9, "safety": 1.0})
    grader = LLMGrader(
        model=fake,
        name="llm_judge",
        mode=GraderMode.POINTWISE,
        template=TEMPLATE,
        structured_model=JudgeOutput,
    )

    result = await grader.aevaluate(input="咳嗽挂什么科", trajectory="[query_department]")

    print("=== LLMGrader 返回结果 ===")
    print("score:", result.score)
    print("reason:", result.reason)
    print("metadata:", result.metadata)

    # 验证 prompt 构造：template 里的占位符被正确替换
    prompt_text = str(fake.last_messages)
    assert "咳嗽挂什么科" in prompt_text, "input 未注入 template"
    assert "[query_department]" in prompt_text, "trajectory 未注入 template"
    assert fake.last_structured_model is JudgeOutput, "structured_model 未传递"

    # 验证解析：score/reason 从 parsed 提取，其余进 metadata
    assert result.score == 0.85
    assert result.metadata.get("intent_accuracy") == 0.9
    assert result.metadata.get("safety") == 1.0

    print("\n✅ LLMGrader 链路验证通过：prompt 构造 + structured output 解析 + metadata 传递正常")
    print("   （LLM-as-Judge 骨架可用，仅需在 .env 配置真实模型后端）")


if __name__ == "__main__":
    asyncio.run(main())
