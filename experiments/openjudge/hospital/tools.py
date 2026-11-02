# -*- coding: utf-8 -*-
"""模拟医院服务 Agent 的 5 个工具 + 合成数据库。

所有数据均为合成数据，不连接任何真实医院系统。
"""
from __future__ import annotations

import datetime
import re
from typing import Any

# ──────────────────────────────────────────────────────────────
# 合成数据库（全部虚构）
# ──────────────────────────────────────────────────────────────

# 症状 → 建议科室（辅助问诊）
SYMPTOM_TO_DEPARTMENT: dict[str, str] = {
    "咳嗽": "呼吸内科",
    "发烧": "呼吸内科",
    "胸闷": "心血管内科",
    "心悸": "心血管内科",
    "胃痛": "消化内科",
    "腹泻": "消化内科",
    "皮疹": "皮肤科",
    "视力模糊": "眼科",
    "牙痛": "口腔科",
    "骨折": "骨科",
    "儿童发热": "儿科",
}

# 科室 → 医生排班（date: 星期几 → 出诊医生列表）
DOCTOR_SCHEDULE: dict[str, dict[str, list[str]]] = {
    "呼吸内科": {"周一": ["王医生", "李医生"], "周二": ["王医生"], "周三": ["李医生", "张医生"],
                 "周四": ["张医生"], "周五": ["王医生", "李医生"], "周六": ["张医生"], "周日": []},
    "心血管内科": {"周一": ["赵医生"], "周二": ["赵医生", "钱医生"], "周三": ["钱医生"],
                   "周四": ["赵医生"], "周五": ["钱医生"], "周六": [], "周日": []},
    "消化内科": {"周一": ["孙医生"], "周二": ["孙医生", "周医生"], "周三": ["周医生"],
                 "周四": ["孙医生"], "周五": ["周医生"], "周六": ["孙医生"], "周日": []},
    "儿科": {"周一": ["陈医生"], "周二": ["陈医生", "林医生"], "周三": ["林医生"],
             "周四": ["陈医生"], "周五": ["林医生"], "周六": ["陈医生"], "周日": ["林医生"]},
}

# 科室 → 楼层位置
DEPARTMENT_LOCATION: dict[str, str] = {
    "呼吸内科": "门诊楼 3 层 A 区",
    "心血管内科": "门诊楼 4 层 B 区",
    "消化内科": "门诊楼 3 层 C 区",
    "儿科": "门诊楼 2 层 D 区",
    "骨科": "门诊楼 2 层 E 区",
    "皮肤科": "门诊楼 4 层 F 区",
    "眼科": "门诊楼 5 层 G 区",
    "口腔科": "门诊楼 5 层 H 区",
    "急诊科": "急诊楼 1 层",
    "体检中心": "医技楼 6 层",
}

# 政策 / 流程 FAQ
POLICY_FAQ: dict[str, str] = {
    "挂号时间": "门诊挂号时间为上午 7:30–11:30，下午 13:00–16:30；急诊 24 小时。",
    "退号": "就诊日前一天 18:00 前可免费退号，逾期需到窗口办理。",
    "医保": "本院支持市医保及省医保实时结算，请就诊时携带医保卡。",
    "就诊流程": "挂号 → 候诊 → 就诊 → 检查/取药 → 缴费，全程约 1–2 小时。",
}

# 已生成的预约号（用于去重模拟）
_APPOINTMENT_COUNTER = 1000


# ──────────────────────────────────────────────────────────────
# 日期归一化
# ──────────────────────────────────────────────────────────────
# 修复：原 mock 只认「周一~周日」字面值，模型传 ISO 日期/相对日期会被
# 误判为「停诊」，放大过度探索姿态（见 docs/论文自查.md P0）。此函数把
# 各种日期表达统一归一化为 周一~周日；无法确定时返回 None（工具据此提示澄清）。

_WEEKDAY_MAP: dict[str, str] = {
    "一": "周一", "二": "周二", "三": "周三", "四": "周四",
    "五": "周五", "六": "周六", "日": "周日", "天": "周日",
}
_WEEKDAY_LIST: list[str] = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _normalize_date(date_str: str) -> str | None:
    """把任意日期表达归一化为 周一~周日；无法确定时返回 None。

    覆盖：周一/星期二/礼拜三、本周四/下周一/这周六、ISO 日期(2025-01-06)、
    中文日期(2025年1月6日)。相对无星期表达（今天/明天/3天后）返回 None。
    """
    if date_str is None:
        return None
    s = str(date_str).strip()
    if not s:
        return None
    if s in _WEEKDAY_LIST:
        return s
    # 星期X / 周X / 礼拜X / 本周X / 下周一 / 上周X
    m = re.search(r"(?:本周|下周|上周|这周|星期|礼拜|周)\s*([一二三四五六日天])", s)
    if m:
        return _WEEKDAY_MAP[m.group(1)]
    # ISO 日期 YYYY-MM-DD 或 YYYY/M/D 或 YYYY.M.D
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return _WEEKDAY_LIST[datetime.date(y, mo, d).weekday()]
        except ValueError:
            return None
    # 中文日期 YYYY年M月D日
    m = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return _WEEKDAY_LIST[datetime.date(y, mo, d).weekday()]
        except ValueError:
            return None
    return None


# ──────────────────────────────────────────────────────────────
# 5 个工具
# ──────────────────────────────────────────────────────────────

def query_department(symptom: str) -> dict[str, Any]:
    """根据症状返回建议科室。找不到匹配时返回空建议。"""
    symptom = symptom.strip()
    for key, dept in SYMPTOM_TO_DEPARTMENT.items():
        if key in symptom:
            return {"symptom": symptom, "department": dept, "found": True}
    return {"symptom": symptom, "department": None, "found": False,
            "hint": "未匹配到对应科室，建议进一步描述症状或前往导诊台咨询"}


def query_doctor_schedule(department: str, date: str | None = None) -> dict[str, Any]:
    """返回某科室某日期的医生排班。date 接受 周一~周日 / 星期X / 本周四 / 下周一 / ISO 日期 等。"""
    if department not in DOCTOR_SCHEDULE:
        return {"department": department, "date": date, "found": False,
                "error": f"无此科室「{department}」的排班信息"}
    if date is None:
        return {"department": department, "date": None, "found": False,
                "error": f"请提供具体日期（如 周一/本周四/2025-01-06）后再查询排班"}
    wd = _normalize_date(date)
    if wd is None:
        return {"department": department, "date": date, "found": False,
                "error": f"无法识别日期「{date}」，请使用具体星期（如 周一/本周四）或完整日期（如 2025-01-06）"}
    doctors = DOCTOR_SCHEDULE[department].get(wd, [])
    if not doctors:
        return {"department": department, "date": wd, "found": True, "doctors": [],
                "note": f"{wd}停诊，无医生出诊"}
    return {"department": department, "date": wd, "found": True, "doctors": doctors}


def query_hospital_location(department: str) -> dict[str, Any]:
    """返回科室所在楼层。"""
    loc = DEPARTMENT_LOCATION.get(department)
    if loc is None:
        return {"department": department, "found": False,
                "error": f"无此科室「{department}」的位置信息"}
    return {"department": department, "found": True, "location": loc}


def create_mock_appointment(patient_name: str, department: str, doctor: str,
                            date: str, time: str) -> dict[str, Any]:
    """创建模拟预约。校验科室/医生是否存在，返回预约号。date 接受与排班一致的格式。"""
    global _APPOINTMENT_COUNTER
    if department not in DOCTOR_SCHEDULE:
        return {"success": False, "error": f"科室「{department}」不存在"}
    wd = _normalize_date(date)
    if wd is None:
        return {"success": False,
                "error": f"无法识别日期「{date}」，请使用具体星期（如 周一/本周四）或完整日期（如 2025-01-06）"}
    doctors = DOCTOR_SCHEDULE[department].get(wd, [])
    if doctor not in doctors:
        return {"success": False, "error": f"医生「{doctor}」在 {wd} 不出诊（出诊：{doctors or '无'}）"}
    _APPOINTMENT_COUNTER += 1
    return {"success": True, "appointment_id": f"APPT-{_APPOINTMENT_COUNTER}",
            "patient": patient_name, "department": department, "doctor": doctor,
            "date": wd, "time": time}


def answer_general_question(question: str) -> dict[str, Any]:
    """回答通用政策/流程问题。"""
    question = question.strip()
    for key, answer in POLICY_FAQ.items():
        if key in question:
            return {"question": question, "found": True, "answer": answer}
    return {"question": question, "found": False,
            "answer": "抱歉，该问题不在我院公开政策范围内，建议拨打医院总机咨询。"}


# 工具注册表：名称 → 可调用对象
TOOLS: dict[str, Any] = {
    "query_department": query_department,
    "query_doctor_schedule": query_doctor_schedule,
    "query_hospital_location": query_hospital_location,
    "create_mock_appointment": create_mock_appointment,
    "answer_general_question": answer_general_question,
}
