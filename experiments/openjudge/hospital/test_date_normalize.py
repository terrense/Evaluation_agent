# -*- coding: utf-8 -*-
"""日期归一化 + 排班/预约工具的回归测试。

验证 tools.py 的 _normalize_date 能把 ISO 日期/相对日期/中文星期统一归一化，
且不再误报「停诊」/「不出诊」。用 pytest 跑：python -m pytest test_date_normalize.py -q
"""
from __future__ import annotations

from tools import _normalize_date, query_doctor_schedule, create_mock_appointment

_WEEKDAY_LIST = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def test_normalize_canonical():
    assert _normalize_date("周一") == "周一"
    assert _normalize_date("星期日") == "周日"
    assert _normalize_date("礼拜三") == "周三"


def test_normalize_relative_weekday():
    assert _normalize_date("本周四") == "周四"
    assert _normalize_date("下周一") == "周一"
    assert _normalize_date("这周六") == "周六"


def test_normalize_iso_date():
    # 2025-01-06 是周一；2026-06-15 也是周一
    assert _normalize_date("2025-01-06") == "周一"
    assert _normalize_date("2026-06-15") == "周一"
    assert _normalize_date("2025/1/6") == "周一"
    assert _normalize_date("2025年1月6日") == "周一"


def test_normalize_unresolvable_returns_none():
    for x in ("3天后", "今天", "明天", "神经外科", "", None):
        assert _normalize_date(x) is None


def test_schedule_no_longer_false_stopped():
    # 旧 mock 会把 ISO 日期误报停诊；修复后应返回正确排班
    r = query_doctor_schedule("呼吸内科", "2025-01-06")  # 周一
    assert r["found"] is True and r["doctors"] == ["王医生", "李医生"]
    r2 = query_doctor_schedule("呼吸内科", "本周四")
    assert r2["doctors"] == ["张医生"]


def test_appointment_accepts_iso_date():
    r = create_mock_appointment("张三", "呼吸内科", "王医生", "2025-01-06", "9:00")
    assert r["success"] is True and r["date"] == "周一"
    # 医生在指定星期不出诊时仍应正确拒绝
    r2 = create_mock_appointment("李四", "呼吸内科", "张医生", "2025-01-06", "9:00")  # 周一，张医生不出诊
    assert r2["success"] is False


def test_appointment_ambiguous_date_prompts():
    r = create_mock_appointment("王五", "呼吸内科", "王医生", "3天后", "9:00")
    assert r["success"] is False and "无法识别日期" in r["error"]


def test_schedule_missing_date_prompts():
    # 模型漏传 date 时，工具应返回提示而非抛 TypeError 崩溃整个 run
    r = query_doctor_schedule("呼吸内科")
    assert r["found"] is False and "请提供具体日期" in r["error"]
