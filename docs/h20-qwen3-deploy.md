# Qwen3 模型服务部署说明（H20 自托管 vLLM）

> 给**部署端**（另一台 Claude / 运维）看的自包含说明。目标：在 H20 GPU 服务器上起两个
> OpenAI 兼容的 Qwen3 模型服务，供评测 harness 用 OpenAI SDK 调用（**必须支持 function-calling**）。
> 看完本文档即可独立完成部署，无需接触评测 repo 的其余代码。

---

## 0. 一句话目标

起两个 vLLM 服务，`--served-model-name` 分别是 `qwen3-32b` 和 `qwen3-8b`，
监听 `http://<服务器IP>:8000/v1` 和 `http://<服务器IP>:8001/v1`，
并且**带 `tools` 的请求要能返回 `tool_calls`**（这是硬指标）。

---

## 1. 硬性契约（评测端写死，必须满足）

评测端 `providers.py` 这样构造 client：

```python
OpenAI(api_key=os.getenv("QWEN_H20_KEY"), base_url=os.getenv("QWEN_H20_BASE"))
model = "qwen3-32b"   # 或 "qwen3-8b"
```

因此部署端必须保证：

| 项 | 值 | 说明 |
|---|---|---|
| `--served-model-name` | `qwen3-32b` / `qwen3-8b` | **严格一致**，评测端 `model` 字段就是它 |
| base_url 路径 | `http://<IP>:8000/v1` | 带 `/v1` 后缀（OpenAI 兼容） |
| API key | 任意（如 `EMPTY`） | vLLM 不校验，评测端填 `QWEN_H20_KEY=EMPTY` 即可 |
| function-calling | **必须支持** | 评测端用 `tools=...` + `tool_choice="auto"` |

> 模型权重来源：`Qwen/Qwen3-32B` 与 `Qwen/Qwen3-8B`（HuggingFace，阿里通义官方）。

---

## 2. 安装与启动

```bash
pip install -U vllm   # 建议较新版本，确保 Qwen3 工具调用支持
```

### Qwen3-32B（BF16 ≈ 64GB，H20 96GB 单卡可放）

```bash
vllm serve Qwen/Qwen3-32B \
  --served-model-name qwen3-32b \
  --max-model-len 32768 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --port 8000
```

### Qwen3-8B（BF16 ≈ 16GB，可同机另端口）

```bash
vllm serve Qwen/Qwen3-8B \
  --served-model-name qwen3-8b \
  --max-model-len 32768 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --port 8001
```

**显存注意**：32B(64GB) + 8B(16GB) = 80GB < 96GB，理论上可同卡/同机并跑；
但为稳定建议 32B 独占一张卡，8B 单独或共享另一张卡（或用 `CUDA_VISIBLE_DEVICES` 指定）。

**关于 `--tool-call-parser hermes`**：Qwen3 的 chat 模板用 Hermes 风格的
`<tool_call>` 标签，`hermes` 是标准 parser。若实际 vLLM 版本工具调用不通，
按 §5 的 smoke test 排查（这是唯一的验收标准，别只看参数名）。

---

## 3. Qwen3 思考模式注意

Qwen3 是「混合思考」模型，不同 vLLM 版本对思考开关的处理不同：

- 若工具调用与思考 token 冲突，可尝试加 `--reasoning-parser deepseek_r1`，
  或显式用 chat 模板关闭思考。
- 评测端 `real_agent.py::_clean_content()` 已剥离 `<think>...</think>`，
  所以思考内容**不会**污染最终评分——部署端只要保证工具调用能正常解析即可。

---

## 4. 验证（关键：function-calling 必须通）

### 4.1 确认模型已注册

```bash
curl http://localhost:8000/v1/models
# 预期能看到 "id": "qwen3-32b"
curl http://localhost:8001/v1/models
# 预期能看到 "id": "qwen3-8b"
```

### 4.2 带 tools 的调用（验收核心）

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-32b",
    "messages": [{"role": "user", "content": "帮我查呼吸内科在几楼"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "query_hospital_location",
        "description": "查询科室所在楼层",
        "parameters": {
          "type": "object",
          "properties": {"department": {"type": "string"}},
          "required": ["department"]
        }
      }
    }],
    "tool_choice": "auto"
  }'
```

**预期**：响应里的 `message` 含 `tool_calls`，其中 `function.name == "query_hospital_location"`、
`arguments` 含 `{"department": "呼吸内科"}`。

**如果只回文本、不调工具** → function-calling 没配好。按优先级排查：
1. 确认 `--enable-auto-tool-choice` 和 `--tool-call-parser hermes` 都带上了；
2. 升级 vLLM 版本；
3. 换 parser 试（`hermes` → 试 `qwen` 或裸 `--tool-call-parser hermes` 不加 auto 的变体）；
4. 看 vLLM 启动日志里是否有 chat template / tool parser 警告。

---

## 5. 评测端实际会发的 5 个工具（供逐一验证）

评测 harness 会随请求发送这 5 个工具 schema。部署端可任取一个做 4.2 的验证。

| 工具名 | 参数（required） | 用途 |
|---|---|---|
| `query_department` | `symptom` | 症状→科室 |
| `query_doctor_schedule` | `department`, `date` | 查排班 |
| `query_hospital_location` | `department` | 查楼层 |
| `create_mock_appointment` | `patient_name`, `department`, `doctor`, `date`, `time` | 建预约 |
| `answer_general_question` | `question` | 政策/流程 FAQ |

---

## 6. 交付 checklist（给评测端回传）

- [ ] `/v1/models` 能看到 `qwen3-32b`（8000 端口）和 `qwen3-8b`（8001 端口）
- [ ] 带 `tools` 的请求能返回 `tool_calls`（不是纯文本）
- [ ] 回传服务器内网 IP 和两个端口，评测端据此填 `.env`：

```
QWEN_H20_BASE=http://<服务器IP>:8000/v1       # qwen3-32b 用
QWEN_H20_BASE_8B=http://<服务器IP>:8001/v1    # qwen3-8b 用（两个模型端口不同，所以各配各的）
QWEN_H20_KEY=EMPTY
```

> 注：两个自托管模型跑在不同端口（8000/8001），评测端 `providers.py` 已为 8B 单独登记
> `QWEN_H20_BASE_8B`，所以 32B 与 8B 各自一个 base_url，无需同端口。
