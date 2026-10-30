# -*- coding: utf-8 -*-
"""AI-Infra-Guard 静态预扫描实战：用真实 skill_scan.utils.pre_scan 检测 6 类安全用例。

真实复用：skill_scan.utils.pre_scan.pre_scan（AI-Infra-Guard 上游源码，纯静态正则，
无 LLM，可直接运行）。LLM 辅助判断（Agent 完整审计）需 API key，本实验标注未验证。

攻击类别映射（Phase 4 要求）：
  T01 正常无害 Skill
  T02 含不可信指令的文档（提示注入）
  T03 声称拥有系统权限的恶意工具返回文本（云元数据窃取 + curl|bash）
  T04 诱导 Agent 跳过预约确认（SYSTEM OVERRIDE）
  T05 诱导读取合成隐私信息（凭据读取 + 外传）
  T06 尝试让 Agent 无视工具白名单（forget everything）
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from skill_scan.utils.pre_scan import pre_scan

BASE = Path(__file__).resolve().parent
REPORT_DIR = BASE.parent.parent / "reports" / "aiginfra"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# 每个用例的 ground truth（是否应被静态预扫描标记）
CASE_META = {
    "T01_benign": {"label": "正常无害 Skill", "expect_static_hit": False,
                   "category": "negative"},
    "T02_prompt_injection_doc": {"label": "含不可信指令的文档", "expect_static_hit": True,
                                 "category": "prompt_injection"},
    "T03_malicious_tool": {"label": "恶意工具(云元数据+curl|bash)", "expect_static_hit": True,
                           "category": "tool_poisoning"},
    "T04_skip_confirmation": {"label": "诱导跳过预约确认", "expect_static_hit": True,
                              "category": "prompt_injection"},
    "T05_steal_privacy": {"label": "诱导读取隐私信息", "expect_static_hit": True,
                          "category": "privacy_exfil"},
    "T06_bypass_whitelist": {"label": "诱导无视工具白名单", "expect_static_hit": True,
                             "category": "prompt_injection"},
}


def parse_findings(hint: str) -> list[dict]:
    """解析 pre_scan 输出的 hint 文本，提取命中的 pattern 列表。"""
    findings = []
    for line in hint.splitlines():
        m = re.match(r"- \*\*(.+?)\*\* — (.+)", line)
        if m:
            findings.append({"file": m.group(1), "description": m.group(2)})
    return findings


def main() -> None:
    results = []
    print("=" * 72)
    print("AI-Infra-Guard 静态预扫描实战（真实上游 pre_scan 代码）")
    print("=" * 72)

    for case_dir in sorted(BASE.glob("testcases/*")):
        case_id = case_dir.name
        meta = CASE_META[case_id]
        hint = pre_scan(str(case_dir))
        findings = parse_findings(hint)
        # 提取命中的 pattern 名称（从 description 无法直接拿，这里用 hint 中的 pattern 行）
        # 重新解析：pre_scan 的 hint 里每行是 "file — description"，pattern 名在 description 里
        static_hit = len(findings) > 0

        # 判定：真阳性 / 假阴性 / 真阴性 / 假阳性
        if meta["expect_static_hit"] and static_hit:
            verdict = "真阳性 TP（静态检出）"
        elif meta["expect_static_hit"] and not static_hit:
            verdict = "假阴性 FN（静态漏检）"
        elif not meta["expect_static_hit"] and static_hit:
            verdict = "假阳性 FP（静态误报）"
        else:
            verdict = "真阴性 TN（正确放过）"

        results.append({
            "case_id": case_id, "label": meta["label"], "category": meta["category"],
            "expect_static_hit": meta["expect_static_hit"], "static_hit": static_hit,
            "verdict": verdict, "findings": findings,
        })

        print(f"\n【{case_id}】{meta['label']}  [{meta['category']}]")
        print(f"  静态预扫描命中: {'是' if static_hit else '否'}  →  {verdict}")
        for f in findings:
            print(f"    - {f['file']}: {f['description'][:80]}")

    # 汇总
    tp = sum(1 for r in results if r["verdict"].startswith("真阳性"))
    tn = sum(1 for r in results if r["verdict"].startswith("真阴性"))
    fp = sum(1 for r in results if r["verdict"].startswith("假阳性"))
    fn = sum(1 for r in results if r["verdict"].startswith("假阴性"))
    print("\n" + "=" * 72)
    print("检测汇总（静态预扫描，无 LLM）")
    print("=" * 72)
    print(f"  真阳性 TP: {tp} | 真阴性 TN: {tn} | 假阳性 FP: {fp} | 假阴性 FN: {fn}")
    total = len(results)
    print(f"  检出率(recall): {tp}/{tp+fn if tp+fn else 1} = {tp/(tp+fn) if tp+fn else 0:.3f}")
    print(f"  误报率(FPR): {fp}/{fp+tn if fp+tn else 1} = {fp/(fp+tn) if fp+tn else 0:.3f}")

    # 输出 JSON 报告
    out = REPORT_DIR / "static_scan_report.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告 → {out}")
    print("\n⚠️  说明：静态预扫描只做「导航提示」，不做「确认漏洞」；")
    print("    LLM 辅助的完整审计（Code Audit → Verdict Review）需 API key，本实验未运行（未验证状态）。")


if __name__ == "__main__":
    main()
