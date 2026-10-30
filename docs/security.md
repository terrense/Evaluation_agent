# 安全威胁模型与检测结果（AI-Infra-Guard 实战）

> 本文档基于 Phase 4 真实运行 AI-Infra-Guard 的 `skill_scan.utils.pre_scan` 静态预扫描源码，对 6 类可控安全用例的检测结果。所有攻击仅针对本机合成模拟环境。

## 1. 威胁模型：三大攻击面

【官方设计 + 源码事实】AI-Infra-Guard 覆盖三个攻击面（对应三个 Python 扫描器）：

| 攻击面 | 扫描器 | 威胁类型 | 静态检测模式（源码） |
|---|---|---|---|
| **Skill 包** | skill-scan | 恶意技能代码（curl\|bash、云元数据、凭据窃取、提示注入） | `pre_scan.py` 13 种通用模式 |
| **MCP Server** | mcp-scan | MCP token 窃取、工具投毒、提示注入 | 通用模式 + `mcp_token_steal` + `mcp_tool_poisoning` |
| **Agent 平台** | agent-scan | 授权绕过、数据泄露、间接提示注入、工具滥用（10 种技能） | 动态黑盒（需 LLM） |

【我的分析】核心威胁源是 **MCP（Model Context Protocol）——「AI Agent 的通用连接器」**。BHEU'25 演讲标题《MCP Unchained: Compromising the AI Agent Ecosystem via its Universal Connector》点明：恶意 MCP server 可窃取 agent↔server 间的认证 token（`mcp_token_steal`）或投毒工具返回内容诱导 agent 执行恶意操作（`mcp_tool_poisoning`）。这是 2026 年 AI Agent 生态最现实的攻击面。

## 2. 静态预扫描设计哲学（源码事实）

`pre_scan.py:15` 的 `_PATTERNS` 每个正则都带一句**自我约束**描述，如：
- `curl_pipe_exec`：*"正则匹配不构成执行或数据流证据"*
- `cloud_metadata_access`：*"验证实际访问、请求字段、是否跨越信任边界"*
- `prompt_injection`：*"区分任务指导、引用数据、还是试图覆盖约束"*

【关键设计】静态正则的定位是 **navigation hints（导航提示），从未作为 confirmed vulnerabilities（已确认漏洞）**。这直接对应 `extract_vuln.py` 的 verdict 机制：`normal` / `suspicious` / `malicious` 三级，静态命中只能产生 "suspicious" 候选，最终判定由 LLM 审计完成。

## 3. 检测结果（6 类可控用例，真实 pre_scan）

| 用例 | 攻击类别 | 静态命中 | 判定 |
|---|---|---|---|
| T01 正常无害 Skill | negative | 否 | **真阴性 TN**（正确放过） |
| T02 含不可信指令文档 | prompt_injection | 是 | **真阳性 TP** |
| T03 恶意工具(云元数据+curl\|bash) | tool_poisoning | 是（2 模式） | **真阳性 TP** |
| T04 诱导跳过预约确认 | prompt_injection | 是 | **真阳性 TP** |
| T05 诱导读取隐私信息 | privacy_exfil | 是（2 模式） | **真阳性 TP** |
| T06 诱导无视工具白名单 | prompt_injection | 是 | **真阳性 TP** |

汇总：**TP=5, TN=1, FP=0, FN=0；recall=1.0, FPR=0.0**。

### 3.1 诚实标注：结果"过于干净"的原因

【我的分析，重要】这个完美结果（recall=1.0, FPR=0.0）**恰恰暴露了静态检测的局限**，而非证明它完美：

1. 我的用例是"教科书式"的**明显模式**（明文 `curl|bash`、明文 `169.254.169.254`、明文 `ignore previous instructions`），正则当然能精确命中。
2. **真实攻击会绕过正则**：base64 编码混淆、字符拆分、Unicode 同形替换、动态字符串拼接——这些 pre_scan 的 `encoded_payload` 只能覆盖"编码+执行"共现，无法覆盖任意混淆。
3. 因此 pre_scan 定位为"提示"而非"定论"是**正确的工程取舍**：静态正则追求低误报（宁可漏报不明模式），语义判断交给 LLM 审计。

### 3.2 静态 vs LLM 的分工（源码 + 分析）

| 阶段 | 机制 | 能力 | 局限 |
|---|---|---|---|
| 静态预扫描 | 正则（pre_scan） | 快、可解释、零成本、低误报 | 只覆盖已知模式，漏报混淆攻击 |
| LLM Code Audit | LLM 读源码判漏洞 | 理解语义、跨文件数据流 | 需 API、有噪声、可能误报 |
| Verdict Review | LLM 复审首轮 suspicious | 减少 LLM 首轮误判 | 仍受 LLM 偏见影响 |

skill-scan 默认走"两阶段快速路径"（Code Audit → 仅 suspicious 才 Verdict Review），`normal`/`malicious` 走快速路径——这是**成本-精度权衡**。

## 4. Security Detection vs Runtime Enforcement（教学要求）

【我的分析，核心区分】AI-Infra-Guard 是 **Security Detection（检测）**，不是 **Runtime Enforcement（执行期强制）**：

- **Detection**：事后/静态扫描，输出"这个 Skill/MCP/Agent 有 X 风险 + 证据 + 严重度 + 修复建议"（SARIF 报告）。它是**观察者**。
- **Enforcement**：运行期真正拦截（沙箱隔离、工具白名单、权限校验、确认步骤）。它是**执行者**。

二者缺一不可：检测告诉你在哪里、有什么风险；执行保证风险不会真的发生。我的 Phase 4 实验只验证了 Detection 这一半；Enforcement 是另一个机制（如 OpenJudge 的 AgenticGrader 沙箱、claw-eval 的 sandbox）。

**对应到我的用例**：
- T04（诱导跳过确认）被"检测"到 → 但真正阻止它需要"运行时强制确认步骤"（Enforcement）。
- 我的 Phase 2 医院 Agent 的 Safety grader（`_is_dangerous` 拒绝越权开药）是**运行时的 Rule-based 检测**，介于二者之间。

## 5. 修复建议（每个攻击类别的缓解）

| 攻击类别 | 检测证据 | 修复建议 |
|---|---|---|
| prompt_injection（T02/T04/T06） | 文档/输入含指令覆盖文本 | 输入与指令隔离（分隔符+角色标记）；不可信内容一律视为数据；LLM 侧注入防御（agent-scan 内置） |
| tool_poisoning（T03） | curl\|bash + 云元数据 | 禁止 shell 拼接执行；云元数据请求需显式授权；沙箱隔离 |
| privacy_exfil（T05） | 凭据路径 + 外发请求 | 凭据走密钥管理不落盘；外发请求需白名单目标；最小权限 |
| 越权（Phase 2 H025） | 声称开药 | 运行时硬约束：高危操作必须确认 + 权限校验（Enforcement） |

## 6. 未验证部分（诚实标注）

- **LLM 完整审计**（skill-scan/mcp-scan 的 Code Audit → Verdict Review）：需 API key，未运行。
- **Agent 动态黑盒测试**（agent-scan 的 10 种检测技能）：需 API key + 目标 agent 平台，未运行。
- **MCP 红队**（mcp-scan 的 redteam/）：需 MCP server + LLM，未运行。
- 上述均已从源码理解其机制，但未实际运行验证；配置模板见 `configs/`。
