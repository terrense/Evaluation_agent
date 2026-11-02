# -*- coding: utf-8 -*-
"""「症状→科室」扩样（v2）框架 —— 18 个新映射 + 口语别名归一化 + 72 条新样本。

数据源：data/symptom_expansion.json（ChatGPT 生成，2026-11-02），本模块读取并生成
合并产物。目的是把 optional 桶从 20 条扩到 92 条，同时修复 query_department 的
「子串匹配」脆弱性（患者说「嗓子疼」匹配不到 canonical「咽痛」→ 工具误返回未找到，
把 mock 工具的缺陷算到模型头上，污染 groundedness / completion 评分）。

**合并步骤（实验 1 —— 100 样本 × 21 模型跑完后执行，避免污染在跑的实验）：**
  1. tools.py：`SYMPTOM_TO_DEPARTMENT` += `NEW_MAPPINGS`；`query_department` 加别名归一化
     （见下方 `query_department_v2` 参考实现）；`DEPARTMENT_LOCATION`/`DOCTOR_SCHEDULE`
     补 `NEW_DEPARTMENTS`（否则 over-explore 姿态查新科室会撞「无此科室」假失败）。
  2. real_agent.py：`SYSTEM_PROMPT` 的可用科室 += `NEW_DEPARTMENTS`，症状映射 += `PROMPT_LINES`。
  3. samples.py：`SAMPLES` += `EXPANSION_SAMPLES`（H101-H172，72 条）。
  4. tool_requirement.py：`TOOL_REQUIREMENT` += `TOOL_REQ_ENTRIES`（全 optional）。
  5. 重跑 `export_annotation.py` 导出 annotation.json；跑 `pytest`。

别名归一化是「best-effort」：只收无歧义的口语别名；「月经/经期/小便」这类跨症状
歧义词不收（靠 system prompt 里给的 canonical 词让模型直接用标准名），残余歧义
记为论文 Limitations。
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_JSON = json.loads((HERE / "data" / "symptom_expansion.json").read_text(encoding="utf-8"))

# ── 1. 新增 canonical 映射（18 条）+ 新科室（6 个）────────────────────

NEW_MAPPINGS: dict[str, str] = {
    m["symptom"]: m["department"] for m in _JSON["mappings"]
}

# 现有可用科室（tools.py 的 DEPARTMENT_LOCATION / real_agent.py 的 SYSTEM_PROMPT）
_EXISTING_DEPTS = {"呼吸内科", "心血管内科", "消化内科", "儿科", "骨科",
                   "皮肤科", "眼科", "口腔科", "急诊科", "体检中心"}
# 真正需要新增进 mock 数据 / prompt 的科室（4 个旧科室复用，不算新增）
NEW_DEPARTMENTS: list[str] = sorted(
    {m["department"] for m in _JSON["mappings"]} - _EXISTING_DEPTS
)

# ── 2. 口语别名 → canonical（归一化表，无歧义项 only）────────────────

# 说明：query_department_v2 先按此表做「口语→canonical」归一化，再查 canonical 映射。
# 别名用短词（如「嗓子」而非「嗓子疼」），覆盖「嗓子疼 / 嗓子疼了三四天」等变体。
SYMPTOM_ALIASES: dict[str, str] = {
    # 耳鼻喉科
    "嗓子": "咽痛", "喉咙": "咽痛", "咽喉": "咽痛",
    "鼻子": "鼻塞", "鼻孔": "鼻塞", "不通气": "鼻塞", "流鼻涕": "鼻塞",
    "耳朵": "耳鸣", "嗡嗡": "耳鸣", "电流声": "耳鸣",
    # 神经内科
    "头疼": "头痛", "太阳穴": "头痛", "后脑勺": "头痛", "胀痛": "头痛",
    "发麻": "手脚发麻", "麻麻": "手脚发麻",
    # 消化内科
    "反酸": "反酸烧心", "烧心": "反酸烧心", "酸水": "反酸烧心",
    # 皮肤科
    "掉头发": "脱发", "头发": "脱发",
    "长痘": "痤疮", "痘痘": "痤疮",
    # 眼科
    "干涩": "眼睛干涩", "发干": "眼睛干涩",
    # 骨科
    "膝盖": "膝关节疼痛",
    # 风湿免疫科
    "晨僵": "多关节晨僵", "僵硬": "多关节晨僵",
    # 肛肠科
    "肛门": "排便时肛门疼痛",
    # 妇科（「月经/经期」歧义，仅收无歧义的「白带」）
    "白带": "白带异常",
    # 泌尿外科（「小便」歧义，仅收无歧义的「尿尿/尿道/灼热」）
    "尿尿": "排尿疼痛", "尿道": "排尿疼痛", "灼热": "排尿疼痛",
}


def query_department_v2(symptom: str, sym2dept: dict, aliases: dict) -> dict:
    """参考实现：tools.py 的 query_department 升级版（合并时照此改）。

    两段式：先口语别名归一化，再 canonical 子串匹配；都失败才返回未找到。
    """
    s = symptom.strip()
    # 1) 口语别名 → canonical（直接返回，别名已映射到 canonical 的科室）
    for alias, canonical in aliases.items():
        if alias in s:
            return {"symptom": symptom, "department": sym2dept[canonical], "found": True}
    # 2) canonical 子串匹配（原逻辑）
    for key, dept in sym2dept.items():
        if key in s:
            return {"symptom": symptom, "department": dept, "found": True}
    return {"symptom": symptom, "department": None, "found": False,
            "hint": "未匹配到对应科室，建议进一步描述症状或前往导诊台咨询"}


# ── 3. 生成 72 条样本（H101-H172）+ 依赖标注 + prompt 行 ────────────

def _tc(tool: str, args: dict, result: dict) -> dict:
    return {"type": "tool_call", "tool": tool, "args": args, "result": result}

def _fa(text: str) -> dict:
    return {"type": "final_answer", "text": text}


EXPANSION_SAMPLES: list[dict] = []
TOOL_REQ_ENTRIES: dict[str, str] = {}
PROMPT_LINES: list[str] = []

_idx = 0
for m in _JSON["mappings"]:
    sym, dept = m["symptom"], m["department"]
    for phrasing in m["phrasings"]:
        _idx += 1
        tid = f"H{100 + _idx}"
        EXPANSION_SAMPLES.append({
            "task_id": tid, "scenario": "辅助问诊",
            "input": phrasing,
            "trajectory": [
                _tc("query_department", {"symptom": sym},
                    {"symptom": sym, "department": dept, "found": True}),
                _fa(f"建议您挂{dept}"),
            ],
            "expected": {"intent": "辅助问诊", "correct_tools": ["query_department"],
                         "argument_valid": True, "completed": True, "grounded": True,
                         "should_refuse": False, "efficient": True, "stop_correct": True},
        })
        TOOL_REQ_ENTRIES[tid] = "optional"

# prompt 行：按科室分组，同科室多症状用「/」合并
_by_dept: dict[str, list[str]] = {}
for sym, dept in NEW_MAPPINGS.items():
    _by_dept.setdefault(dept, []).append(sym)
PROMPT_LINES = ["，".join(f"{'/'.join(syms)}→{dept}" for dept, syms in _by_dept.items())]


# ── 4. 校验 ─────────────────────────────────────────────────────

def validate() -> None:
    """扩样数据自检：无重复症状 / 无急诊 / 科室合法 / 样本 id 连续。"""
    EXISTING = {"咳嗽", "发烧", "胸闷", "心悸", "胃痛", "腹泻", "皮疹",
                "视力模糊", "牙痛", "骨折", "儿童发热"}
    EMERGENCY = ("胸痛", "卒中", "中风", "大出血", "呼吸困难", "高热惊厥",
                 "口角歪斜", "肢体无力", "失语", "严重外伤")
    FORBIDDEN_DEPT = {"急诊科", "体检中心"}

    for sym, dept in NEW_MAPPINGS.items():
        assert sym not in EXISTING, f"症状重复：{sym}"
        assert dept not in FORBIDDEN_DEPT, f"科室禁止：{dept}"
        for p in [x["input"] for x in EXPANSION_SAMPLES
                  if x["expected"]["intent"] == "辅助问诊"]:
            for e in EMERGENCY:
                assert e not in p, f"疑似急诊：{p}"
    ids = [s["task_id"] for s in EXPANSION_SAMPLES]
    assert ids == [f"H{101 + i}" for i in range(len(ids))], "task_id 不连续"
    assert len(EXPANSION_SAMPLES) == 72, f"样本数 {len(EXPANSION_SAMPLES)} != 72"
    assert len(TOOL_REQ_ENTRIES) == 72


if __name__ == "__main__":
    validate()
    print(f"✅ 校验通过：{len(NEW_MAPPINGS)} 映射 / {len(EXPANSION_SAMPLES)} 样本")
    print(f"   新科室：{'、'.join(NEW_DEPARTMENTS)}")
    print(f"   别名表：{len(SYMPTOM_ALIASES)} 条口语别名")
    print(f"   prompt 行：{PROMPT_LINES[0]}")
    print(f"   样本 id 范围：H101–H{100 + len(EXPANSION_SAMPLES)}")
