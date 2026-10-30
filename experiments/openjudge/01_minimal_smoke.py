# -*- coding: utf-8 -*-
"""OpenJudge 最小 smoke test：验证 FunctionGrader + GradingRunner 核心 API。

不依赖任何 LLM API，纯本地规则打分，用于验证「官方源码 API 是否与文档一致」。
"""
import asyncio

from openjudge.graders.function_grader import FunctionGrader
from openjudge.graders.schema import GraderMode, GraderScore
from openjudge.runner.grading_runner import GradingRunner


async def keyword_grader_func(query: str, answer: str, keywords: list[str]) -> GraderScore:
    """检查 answer 是否包含所有必需关键词（模拟 Groundedness 判定）。"""
    hit = [k for k in keywords if k in answer]
    score = len(hit) / len(keywords) if keywords else 0.0
    return GraderScore(
        name="keyword",
        score=score,
        reason=f"命中 {len(hit)}/{len(keywords)} 关键词: {hit}",
        metadata={"hit": hit, "required": keywords},
    )


async def main() -> None:
    grader = FunctionGrader(
        func=keyword_grader_func,
        name="keyword_grader",
        mode=GraderMode.POINTWISE,
        description="检查回答是否包含必需关键词",
    )

    dataset = [
        {"query": "法国的首都是哪", "answer": "巴黎是法国的首都", "keywords": ["巴黎", "首都"]},
        {"query": "法国的首都是哪", "answer": "伦敦在英国", "keywords": ["巴黎", "首都"]},
        {"query": "2+2=?", "answer": "4", "keywords": ["4"]},
    ]

    runner = GradingRunner(
        grader_configs={"keyword": (grader, None)},
        max_concurrency=3,
        show_progress=False,
    )
    results = await runner.arun(dataset)

    print("=== RunnerResult 结构 ===")
    for name, per_sample in results.items():
        print(f"grader [{name}]: {len(per_sample)} 条结果")
        for i, r in enumerate(per_sample):
            print(f"  sample {i}: score={r.score:.2f}  reason={r.reason!r}")
            print(f"    metadata={r.metadata}")

    # 断言核心结构（若 API 与预期不符会抛错）
    assert len(results["keyword"]) == 3
    assert results["keyword"][0].score == 1.0
    assert results["keyword"][1].score == 0.0
    assert results["keyword"][2].score == 1.0
    print("\n✅ 核心 API 验证通过：FunctionGrader → GradingRunner → RunnerResult 链路正常")


if __name__ == "__main__":
    asyncio.run(main())
