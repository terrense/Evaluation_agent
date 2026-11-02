# Agent Evaluation Lab

研究并实操三个真实开源 Agent 评测/安全系统，搭建统一评测工程：

| 项目 | 定位 | commit |
|---|---|---|
| [OpenJudge](https://github.com/agentscope-ai/OpenJudge) | 通用评测框架 + 质量奖励 | `c2fdc38314cd` |
| [claw-eval](https://github.com/claw-eval/claw-eval) | 300 任务 Agent benchmark（arXiv:2604.06132） | `5680b8b11ff2` |
| [AI-Infra-Guard](https://github.com/Tencent/AI-Infra-Guard) | AI 红队安全平台 | `851e3f295031` |

## 目录结构

```
agent-eval-lab/
├── upstream/          # 三个上游仓库（不改源码）
├── experiments/       # 自研实验代码
│   ├── openjudge/     # Phase 2：医院导诊 Agent + 8 维 grader + 100 样本（22 模型 × 5 家族）
│   ├── claweval/      # Phase 3：3 任务 × 3 trial + 6 failure injection
│   ├── aiginfra/      # Phase 4：6 类安全用例 + 静态预扫描
│   └── lab/           # Phase 5/6：统一 Harness + 四方案对比 + RQ 实验
├── docs/              # 文档（architecture/papers/security/evaluation-design/experiments/findings）
├── reports/           # 真实实验结果（jsonl/csv/md/png）
├── configs/           # 配置模板
└── scripts/           # 可复现启动命令
```

## 环境

- Python 3.13 + uv；三个独立 venv：`.venv-openjudge` / `.venv-claweval` / `.venv-aig`（依赖隔离）
- GPU：RTX 5070 12GB（本实验无需 GPU）；H20 服务器（qwen3-32b 已部署验证，见 docs/h20-qwen3-deploy.md）

## 一键运行

```bash
# 1. 安装三个独立环境（依赖已锁定，用 uv）
uv venv --python 3.13 experiments/.venv-openjudge
uv pip install --python experiments/.venv-openjudge/Scripts/python.exe -e upstream/OpenJudge httpx_sse matplotlib pytest

uv venv --python 3.13 experiments/.venv-claweval
uv pip install --python experiments/.venv-claweval/Scripts/python.exe -e upstream/claw-eval

uv venv --python 3.13 experiments/.venv-aig
uv pip install --python experiments/.venv-aig/Scripts/python.exe -e upstream/AI-Infra-Guard/skill-scan

# 2. 运行各 Phase 实验（Windows 需 PYTHONUTF8=1 读 UTF-8）
bash scripts/run_all.sh
```

## 各 Phase 实验入口

| Phase | 脚本 | 产出 |
|---|---|---|
| 2 OpenJudge 实战 | `experiments/openjudge/hospital/run_eval.py` + `test_grader.py`（17 断言） | `reports/openjudge/` |
| 3 claw-eval 实战 | `experiments/claweval/lightweight.py` | 控制台 + `docs/papers.md` |
| 4 AI-Infra-Guard 实战 | `experiments/aiginfra/run_security_scan.py` | `reports/aiginfra/` |
| 5 统一 Harness | `experiments/lab/four_methods.py` | 四方案对比 |
| 6 RQ 实验 | `experiments/lab/rq_experiments.py` | RQ1/RQ3/RQ5 结论 |

## 关键结论（详见 docs/findings.md）

1. **Outcome-only 漏判率 0.667**，轨迹+确定性漏判 0.333（RQ1）。
2. **Pass@3=1.0 但 Pass^3=0.296**（3 trial 2 成功），Pass^3 暴露不可靠（RQ3）。
3. **hard gate 减漏判但增误判**（漏判 0.333→0.167，误判 0.167→0.222）（RQ5）。
4. **Rule-based grader 自身 bug 必须用 pytest 校验**（Phase 2 发现并修复 2 个 bug）。

## 诚实标注

- LLM-as-Judge 已端到端跑通（DeepSeek `deepseek-v4-pro`）；22 模型 × 5 家族 × 100 样本对比正在重跑（2026-11-02）。
- 早期 Phase 2-6 的 Agent 是确定性模拟；`run_multimodel.py` 已接入真实 LLM Agent。评分公式 / Pass@k/Pass^k / 静态检测来自真实上游源码。
- AI-Infra-Guard 的 LLM 完整审计（Code Audit → Verdict Review）与 MCP/Agent 动态扫描仍待接入。
- 本机 DLP 加密 `.md`/`.go`，读文档用 `git show`；Go 服务端未编译。
