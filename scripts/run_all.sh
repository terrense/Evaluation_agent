#!/usr/bin/env bash
# Agent Evaluation Lab 可复现启动脚本
# 用法：bash scripts/run_all.sh
# 注意：Windows 下需 PYTHONUTF8=1（读 UTF-8 yaml/json 文件）；DLP 环境 .md 用 git show 读

set -e
cd "$(dirname "$0")/.."

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

OJ="experiments/.venv-openjudge/Scripts/python.exe"
CE="experiments/.venv-claweval/Scripts/python.exe"
AIG="experiments/.venv-aig/Scripts/python.exe"

echo "========== Phase 2: OpenJudge 医院导诊评测 =========="
(cd experiments/openjudge/hospital && ../../.venv-openjudge/Scripts/python.exe run_eval.py)
echo ""
echo "========== Phase 2: grader 校验（17 断言）=========="
(cd experiments/openjudge/hospital && ../../.venv-openjudge/Scripts/python.exe -m pytest test_grader.py -q)
echo ""
echo "========== Phase 3: claw-eval 轻量实验 =========="
(cd experiments/claweval && ../.venv-claweval/Scripts/python.exe lightweight.py)
echo ""
echo "========== Phase 4: AI-Infra-Guard 静态预扫描 =========="
(cd experiments/aiginfra && ../.venv-aig/Scripts/python.exe generate_testcases.py && ../.venv-aig/Scripts/python.exe run_security_scan.py)
echo ""
echo "========== Phase 5: 四方案对比 =========="
(cd experiments/lab && ../.venv-openjudge/Scripts/python.exe four_methods.py)
echo ""
echo "========== Phase 6: RQ 实验 =========="
(cd experiments/lab && ../.venv-openjudge/Scripts/python.exe rq_experiments.py)
echo ""
echo "========== 全部完成 =========="
