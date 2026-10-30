# Qwen3 扩模型部署指南（H20 自托管 + DashScope API）

> 目标：模型数 3 → 5~6，覆盖「独立训练家族」维度，全部在大陆可获取（无需美系 API）。
> 现有 infra（`providers.py` / `run_multimodel.py`）已就绪，只需把下面两个来源注册进去即可一键扩。

## 两个来源

| 来源 | 模型 | 获取方式 | 需要 key |
|---|---|---|---|
| H20 自托管 | Qwen3-32B / Qwen3-30B-A3B（开源权重） | vLLM 起 OpenAI 兼容服务 | 否（key=EMPTY） |
| 阿里云百炼 | Qwen3-Max（专有，不开源） | DashScope 兼容模式 API | 是（DashScope key） |

## 1. H20 自托管（开源 Qwen3）

H20 = 96GB HBM3，单卡可放：

- **Qwen3-32B**（32B 稠密）：BF16 ≈ 64GB，舒适；FP8 ≈ 32GB，更快。主推。
- **Qwen3-30B-A3B**（MoE，30B 总 / 3B 激活）：显存占用极小、吞吐极高，适合做一致性/烧机消融。
- ~~Qwen3-235B-A22B~~：BF16 ≈ 470GB，**单卡放不下**，需多卡张量并行，暂不做。

```bash
# H20 服务器上（一次装好）
pip install -U vllm

vllm serve Qwen/Qwen3-32B \
  --served-model-name qwen3-32b \
  --max-model-len 32768 \
  --port 8000

# 测通
curl http://localhost:8000/v1/models
```

关键点：`--served-model-name` 必须与 `providers.py` 里 `qwen3-32b` 的 `model` 字段一致。

Qwen3 是「混合思考」模型，不同 vLLM 版本的思考开关不同（启动参数或 chat 模板）。无论思考落在 `reasoning_content` 还是 `content`，现有 `real_agent.py::_clean_content()` 都会剥离 `<think>…</think>`，兜底不污染最终答案评分。

## 2. Qwen3-Max 专有模型 → DashScope API

专有模型不开源，走阿里云百炼的 OpenAI 兼容模式：

```
DASHSCOPE_API_KEY=sk-你的百炼key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# model = qwen3-max（以百炼控制台当前模型列表为准）
```

注册：阿里云 → 开通「百炼」→ 创建 API Key。大陆手机号即可，无需外币卡。

## 3. 接入现有评测

`providers.py` 已登记 3 个新条目（`qwen3-32b` / `qwen3-30b-a3b` / `qwen3-max`）。
在 `run_multimodel.py` 的 `CONFIGS` 里加：

```python
("qwen3-32b", 0.0, "qwen3-32b__t0.0"),
("qwen3-max",  0.0, "qwen3-max__t0.0"),
```

跑完后 `analyze_multimodel.py` 会自动并入总览 + 图表（记得在 `MODELS` 列表登记新的目录）。

## 4. 扩完后的模型家族 roster

| 家族 | 模型 | 姿态预期 |
|---|---|---|
| DeepSeek | Flash / V4-Pro | ask-first |
| MiniMax | M3 | over-explore |
| 阿里 Qwen | 32B（自托管）/ Max（API） | 待测 |
| 智谱 GLM | GLM-4.*（bigmodel.cn，可选） | 待测 |
| 月之暗面 Kimi | moonshot.cn（可选） | 待测 |

> 每个家族补 1~2 个模型，即可把「两家族现象」升级为「跨 5~6 独立家族的姿态-评测错配」，达到正会门槛（§7 的样本量仍需同步扩到 ≥100）。
