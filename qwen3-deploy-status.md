# Qwen3 部署进展（2026-11-02）

> 供另一个 Claude 会话交接用。主线 = H20 本地化部署 Qwen3-32B（已完成并验证）。

## 1. Qwen3-32B（主线，✅ 完成并验证）

| 阶段 | 状态 |
|---|---|
| venv + vLLM 安装 | ✅ vLLM 0.32.0 + torch 2.13.0+cu130（`/data/shenxin/vllm_qwen3`）|
| 权重下载 | ✅ 62GB / 17 分片全量（`/data/shenxin/qwen3_models/Qwen3-32B`）|
| vLLM serve | ✅ port 8000，`--served-model-name qwen3-32b` |
| 补全验证 | ✅ 英文 + 中文补全 |
| tool-calling 验证 | ✅ 英文 + 中文，`finish_reason=tool_calls`，参数 JSON 正确 |

**起服命令**（带 tool-calling）：
```
HF_HUB_OFFLINE=1 nohup /data/shenxin/vllm_qwen3/bin/vllm serve \
  /data/shenxin/qwen3_models/Qwen3-32B \
  --served-model-name qwen3-32b --max-model-len 32768 \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  > /data/shenxin/logs/vllm_serve.log 2>&1 < /dev/null &
```

- 服务器：`172.24.27.11:5133`（root，K8s pod，内网 IP 10.244.0.81，单卡 H20-3e 140GB）
- 8000 端口外部不暴露，本机经 SSH 隧道访问：
  `ssh -N -L 8000:127.0.0.1:8000 -p 5133 root@172.24.27.11`
- 显存占用 ~129GB/140GB（`--max-model-len 32768` 的 KV cache 吃得多）
- 注意：Qwen3-32B 会把 `<think>...</think>` 推理块塞进 `content` 字段（评测时可能要剥掉）

## 2. Qwen3-8B（已下载，暂缓部署）

- 权重已全量下载（16GB / 5 分片，`/data/shenxin/qwen3_models/Qwen3-8B`）
- **单卡显存不够同时跑**：32B 占 129GB，只剩 ~12.6GB，8B BF16 需 ~16GB → 不能与 32B 并存
- 用户指示：回头测完 32B 再说；暂不部署，权重已备好

## 3. Qwen3.8-Max（新发现，重要）

- 用户给的 DASHSCOPE key 是私有 MaaS 签名 token（`sk-ws-...`）
- 正确模型名是 `qwen3.8-max`（不是 qwen3-max），已修 `providers.py`
- 两个端点都能跑：公网 `dashscope.aliyuncs.com` 和私有 MaaS `cn-beijing.maas.qianwenaiapi.com`（`.env` 用这个）

## 4. 本机 .env（gitignore，key 不上库）

- `QWEN_H20_KEY=EMPTY`、`QWEN_H20_BASE=http://localhost:8000/v1`（经 SSH 隧道）
- `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` 已填真实值
- DeepSeek / MiniMax key 仍占位
