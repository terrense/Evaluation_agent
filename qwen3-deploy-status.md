# Qwen3 部署进展（2026-11-02）

> 供另一个 Claude 会话交接用。主线 = H20 本地化部署 Qwen3-32B；另发现 Qwen3-Max 模型名问题。

## 1. H20 本地化部署（主线，进行中）

| 阶段 | 状态 |
|---|---|
| venv + vLLM 安装 | ✅ vLLM 0.32.0 + torch 2.13.0+cu130，CUDA 可用（`/data/shenxin/vllm_qwen3`） |
| Qwen3-32B 权重下载 | ⏳ 52G / 17 分片已到 9 个（hf-mirror） |
| 起 vLLM serve（port 8000） | ⏸ 等下载完 |
| 验证服务 | ⏸ 等起服 |

- 服务器：`172.24.27.11:5133`（root，K8s pod，内网 IP 10.244.0.81）
- 下载完自动执行：`vllm serve /data/shenxin/qwen3_models/Qwen3-32B --served-model-name qwen3-32b --port 8000 --host 0.0.0.0`
- 8000 端口外部不暴露，本机经 SSH 隧道访问：`ssh -N -L 8000:127.0.0.1:8000 -p 5133 root@172.24.27.11`

## 2. Qwen3-Max（新发现，重要）

- 用户给的 DASHSCOPE key 是**私有 MaaS 签名 token**（`sk-ws-...` 带 ECDSA 签名），不是标准百炼 key
- 实测：模型名 **`qwen3-max` 不存在**，正确名是 **`qwen3.8-max`**（目录里还有 qwen3.7-max / qwen-max）
- 已修 `providers.py`：`qwen3-max` → `qwen3.8-max`
- 两个端点都能跑（key 实测通过 /models、补全、tool-calling）：
  - 公网 `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - 私有 MaaS `https://cn-beijing.maas.qianwenaiapi.com/compatible-mode/v1`（`.env` 用这个）
- tool-calling 实测通过（`finish_reason: tool_calls`，正常返回 `query_department`）

## 3. 本机 `.env`（gitignore 已忽略，key 不上库）

- `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` 已填真实值（key 见本机 `.env`）
- `QWEN_H20_KEY=EMPTY`、`QWEN_H20_BASE=http://localhost:8000/v1`（经 SSH 隧道）
- DeepSeek / MiniMax 的 key 仍是占位符，需另外填
