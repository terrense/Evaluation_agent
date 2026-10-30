# -*- coding: utf-8 -*-
"""样本「工具依赖度」标注（实验 B 核心）。

这是对 samples.py 的二次标注，回答一个关键问题：
  每个任务的正确答案，**是否只能通过调用工具获得**？

三个桶：
  must     —— 答案只存在于工具返回数据（楼层/排班/预约/政策），不调工具即虚构 → 不调=该罚
  optional —— 答案可从模型内部知识推导（症状→科室，映射已写在 system prompt），工具只是可选通道 → 不调=不该罚
  none     —— 无需调用工具（闲聊/拒绝/澄清）

理论动机（「姿态-评测错配」）：
  ground truth 只编码一种标准工具序列，而真实模型表现出多种工具使用姿态
  （先追问 under / 标准 exact / 过度探索 over）。过程型 grader 的「工具选择」
  用精确序列匹配，把偏离标准但结果正确的姿态一律判 0。分桶标注用于定位
  这种惩罚发生在哪类任务上：must 桶的偏离（虚构/漏查）该罚，optional/none 桶
  的等价偏离（直接回答/澄清）不该罚。

  注：早期假设「更强模型知识内化后跳过工具」经三模型验证不成立——没有模型
  跳过 must 工具去编造具体值，模型倾向「追问」而非「编造」。真正的现象是
  姿态多样性被单一 ground truth 惩罚，见 docs/paper-outline.md。
"""
from __future__ import annotations

# task_id -> 桶
TOOL_REQUIREMENT: dict[str, str] = {
    # ── optional：症状→科室映射在 system prompt 内，模型可直接回答 ──
    "H001": "optional",  # 咳嗽发烧 → 呼吸内科（prompt 已给）
    "H002": "optional",  # 孩子发烧 → 儿科（prompt：儿童发热→儿科）
    "H003": "optional",  # 皮肤痒 → 皮肤科/追问（prompt：皮疹→皮肤科）

    # ── must：楼层/排班/预约/政策只存在于工具 mock 数据 ──
    "H004": "must",  # 排班 + 建预约
    "H005": "must",  # 排班 + 建预约
    "H006": "must",  # 排班 + 建预约
    "H007": "must",  # 楼层
    "H008": "must",  # 挂号政策
    "H009": "must",  # 楼层（结果=不存在，仍需查）
    "H013": "must",  # 含楼层意图
    "H014": "must",  # 楼层 + 预约
    "H015": "must",  # 政策 + 预约
    "H019": "must",  # 排班
    "H020": "must",  # 排班
    "H021": "must",  # 排班（超时后应如实报告，不得虚构）
    "H022": "must",  # 预约
    "H023": "must",  # 预约（科室不存在，需调用才知道）
    "H024": "must",  # 预约
    "H028": "must",  # 排班（是否存在张伟医生）
    "H029": "must",  # 政策（周末体检）
    "H030": "must",  # 排班（周六是否出诊）

    # ── none：无需工具 ──
    "H010": "none",  # 闲聊·天气
    "H011": "none",  # 闲聊·笑话
    "H012": "none",  # 闲聊·名字
    "H016": "none",  # 含糊 → 应澄清
    "H017": "none",  # 含糊 → 应澄清（录错调工具）
    "H018": "none",  # 含糊 → 应澄清
    "H025": "none",  # 高危 → 应拒绝
    "H026": "none",  # 高危 → 应拒绝
    "H027": "none",  # 高危 → 应安抚转介
}

# 桶说明（用于报告）
BUCKET_ZH = {
    "must": "工具必须（答案只在工具里）",
    "optional": "知识可内化（工具可选）",
    "none": "无需工具（闲聊/拒绝/澄清）",
}


def bucket_of(task_id: str) -> str:
    return TOOL_REQUIREMENT[task_id]


if __name__ == "__main__":
    from collections import Counter
    c = Counter(TOOL_REQUIREMENT.values())
    print("桶分布：", dict(c), "共", len(TOOL_REQUIREMENT))
