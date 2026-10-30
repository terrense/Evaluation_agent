#!/usr/bin/env bash
# 真实 Agent 全量评测一键脚本（可换模型）
# 用法：bash scripts/run_real_eval.sh [模型名] [输出目录名]
# 默认：deepseek-flash → reports/openjudge/real_eval
# 示例：bash scripts/run_real_eval.sh deepseek-v4-pro real_eval_pro

set -e
cd "$(dirname "$0")/.."
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

MODEL="${1:-deepseek-flash}"
OUT="${2:-real_eval}"

cd experiments/openjudge/hospital
../../.venv-openjudge/Scripts/python.exe run_real_eval.py --agent-model "$MODEL" --out "$OUT"
../../.venv-openjudge/Scripts/python.exe make_report.py "$OUT" 2>/dev/null || true
echo "完成：报告在 reports/openjudge/$OUT/report.md"
