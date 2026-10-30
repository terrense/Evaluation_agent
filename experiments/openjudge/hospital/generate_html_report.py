# -*- coding: utf-8 -*-
"""读取评测数据，生成自包含 HTML 报告（供 Artifact 发布，浏览器直接看）。

数据源：reports/openjudge/{real_eval, real_eval_pro}/ 的 metrics.json + llm_scores.jsonl
输出：reports/openjudge/agent_eval_report.html
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
OUT = BASE / "agent_eval_report.html"

DIMS = ["intent_accuracy", "tool_selection", "argument_correctness",
        "task_completion", "groundedness", "safety",
        "trajectory_efficiency", "stop_decision"]
DIM_ZH = {"intent_accuracy": "意图准确", "tool_selection": "工具选择",
          "argument_correctness": "参数正确", "task_completion": "任务完成",
          "groundedness": "有依据", "safety": "安全",
          "trajectory_efficiency": "轨迹高效", "stop_decision": "停止决策"}


def load_metrics(name: str) -> dict:
    return json.load(open(BASE / name / "metrics.json", encoding="utf-8"))


def load_llm(name: str) -> list:
    return [json.loads(l) for l in open(BASE / name / "llm_scores.jsonl", encoding="utf-8")]


CSS = """
:root{
  --bg:#f5f7fa; --surface:#ffffff; --surface2:#eef1f6;
  --text:#1a2332; --muted:#5a6b82; --border:#d8dfe8;
  --accent:#1f5fe8; --accent-soft:#e8effd;
  --pass:#14964a; --fail:#d52b2b; --warn:#b8720d;
  --bar-track:#e6ebf2;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0d1117; --surface:#161c26; --surface2:#1c2330;
    --text:#e6edf3; --muted:#8b98a8; --border:#2a3442;
    --accent:#5b8def; --accent-soft:#16233c;
    --pass:#2ea86a; --fail:#e5534b; --warn:#d99a2b;
    --bar-track:#232d3b;
  }
}
:root[data-theme="dark"]{
  --bg:#0d1117; --surface:#161c26; --surface2:#1c2330;
  --text:#e6edf3; --muted:#8b98a8; --border:#2a3442;
  --accent:#5b8def; --accent-soft:#16233c;
  --pass:#2ea86a; --fail:#e5534b; --warn:#d99a2b;
  --bar-track:#232d3b;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:48px 24px 80px}
header{border-bottom:1px solid var(--border);padding-bottom:24px;margin-bottom:32px}
.kicker{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:600;margin:0 0 8px}
h1{font-size:32px;line-height:1.2;margin:0 0 8px;text-wrap:balance;font-weight:700;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:15px;margin:0}
h2{font-size:20px;margin:44px 0 16px;font-weight:700;letter-spacing:-.01em}
h3{font-size:16px;margin:24px 0 10px;font-weight:600}
p{margin:0 0 12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px}
.card .n{font-size:28px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.card .l{font-size:12px;color:var(--muted);margin-top:4px}
.card .n.pass{color:var(--pass)} .card .n.fail{color:var(--fail)} .card .n.accent{color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600;font-size:12px;letter-spacing:.04em;text-transform:uppercase}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
.tblwrap{overflow-x:auto;background:var(--surface);border:1px solid var(--border);border-radius:10px}
.tblwrap table{min-width:640px}
.bar-row{display:grid;grid-template-columns:96px 1fr 1fr;gap:12px;align-items:center;margin:7px 0}
.bar-lbl{font-size:13px;color:var(--text)}
.bar-track{background:var(--bar-track);border-radius:3px;height:18px;position:relative;overflow:hidden}
.bar-fill{height:100%;border-radius:3px}
.bar-fill.flash{background:var(--accent)}
.bar-fill.pro{background:var(--warn)}
.bar-val{font-size:12px;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
.finding{background:var(--surface);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;padding:16px 18px;margin:14px 0}
.finding h3{margin:0 0 8px}
.finding.warn{border-left-color:var(--warn)}
.finding.fail{border-left-color:var(--fail)}
.note{background:var(--surface2);border-radius:8px;padding:14px 18px;font-size:14px;color:var(--muted);margin:16px 0}
.pill{display:inline-block;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600}
.pill.pass{background:var(--pass);color:#fff}
.pill.fail{background:var(--fail);color:#fff}
.legend{display:flex;gap:16px;font-size:13px;color:var(--muted);margin:8px 0 4px}
.dot{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle}
code{font-family:ui-monospace,Consolas,"SF Mono",monospace;font-size:13px;background:var(--surface2);padding:1px 6px;border-radius:4px}
footer{color:var(--muted);font-size:13px;margin-top:48px;border-top:1px solid var(--border);padding-top:16px}
"""


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bar_section(title: str, flash: dict, pro: dict) -> str:
    rows = []
    for d in DIMS:
        fv = flash[d]; pv = pro[d]
        rows.append(
            f'<div class="bar-row"><div class="bar-lbl">{DIM_ZH[d]}</div>'
            f'<div class="bar-track"><div class="bar-fill flash" style="width:{fv*100:.1f}%"></div></div>'
            f'<div class="bar-track"><div class="bar-fill pro" style="width:{pv*100:.1f}%"></div></div>'
            f'<div class="bar-val">{fv:.2f} / {pv:.2f}</div></div>'
        )
    return f'<h3>{title}</h3><div class="legend"><span><span class="dot" style="background:var(--accent)"></span>flash</span><span><span class="dot" style="background:var(--warn)"></span>v4-pro</span></div>' + "\n".join(rows)


def build_html() -> str:
    fm = load_metrics("real_eval"); pm = load_metrics("real_eval_pro")
    fllm = load_llm("real_eval"); pllm = load_llm("real_eval_pro")

    f_dim_llm = {d: sum(r["dims"][d] for r in fllm) / len(fllm) for d in DIMS}
    p_dim_llm = {d: sum(r["dims"][d] for r in pllm) / len(pllm) for d in DIMS}
    f_dim_rule = {d: sum(r["dims"][d] for r in fllm) / len(fllm) for d in DIMS}  # placeholder overwritten below
    # rule 维度从 metrics 拿
    f_dim_rule = fm["dim_rule_mean"]; p_dim_rule = pm["dim_rule_mean"]

    cards = [
        ("单次通过率", f"{fm['single_pass_rate']:.0%}", "accent", "30 样本 × 3 trial"),
        ("Pass@3", f"{fm['pass_at_3']:.2f}", "accent", "至少一次成功（无偏估计）"),
        ("Pass^3", f"{fm['pass_hat_3']:.2f}", "accent", "三次全成功（稳定可靠）"),
        ("LLM 总分", f"{fm['llm_overall']:.2f}", "pass", "flash 胜出 +0.04"),
    ]
    card_html = "".join(f'<div class="card"><div class="n {c}">{n}</div><div class="l">{l} · {d}</div></div>' for n, l, c, d in cards)

    # 逐样本明细
    p_by_id = {r["task_id"]: r for r in pllm}
    f_by_id = {r["task_id"]: r for r in fllm}
    from samples import SAMPLES
    rows = []
    for s in SAMPLES:
        tid = s["task_id"]
        fs = f_by_id[tid]["score"]; ps = p_by_id[tid]["score"]
        diff = ps - fs
        better = "pro" if diff > 0.02 else ("flash" if diff < -0.02 else "≈")
        rows.append(f'<tr><td><code>{tid}</code></td><td>{esc(s["scenario"])}</td><td>{esc(s["input"][:22])}</td>'
                    f'<td class="num">{fs:.2f}</td><td class="num">{ps:.2f}</td>'
                    f'<td class="num" style="color:{"var(--warn)" if better=="pro" else ("var(--accent)" if better=="flash" else "var(--muted)")}">{diff:+.2f}</td></tr>')
    sample_rows = "\n".join(rows)

    # 关键指标对比表
    cmp_rows = [
        ("单次通过率", fm["single_pass_rate"], pm["single_pass_rate"]),
        ("Pass@3", fm["pass_at_3"], pm["pass_at_3"]),
        ("Pass^3", fm["pass_hat_3"], pm["pass_hat_3"]),
        ("rule 总分", fm["rule_overall"], pm["rule_overall"]),
        ("LLM 总分", fm["llm_overall"], pm["llm_overall"]),
        ("工具成功率", fm["tool_success_rate"], pm["tool_success_rate"]),
        ("工具调用数", fm["n_tool_calls"], pm["n_tool_calls"]),
        ("工具错误", fm["n_tool_errors"], pm["n_tool_errors"]),
    ]
    def fmt(v):
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    cmp_table = "".join(
        f'<tr><td>{k}</td><td class="num">{fmt(a)}</td><td class="num">{fmt(b)}</td></tr>'
        for k, a, b in cmp_rows
    )

    html = f"""<style>{CSS}</style>
<div class="wrap">
<header>
  <p class="kicker">Agent Evaluation · 真实 LLM 驱动</p>
  <h1>医院导诊 Agent 评测</h1>
  <p class="sub">DeepSeek 驱动 tool-calling Agent · 30 合成样本 × 3 trial · 双 Grader（rule-based 8 维 + LLM-as-Judge）</p>
</header>

<h2>执行摘要</h2>
<div class="cards">{card_html}</div>
<p>真实 Agent（<code>deepseek-flash</code>）在「安全」「有依据」上稳健，但在「任务完成」上暴露短板——
它倾向追问缺失信息而非直接执行，导致单次通过率仅 {fm['single_pass_rate']:.0%}。</p>

<h2>评测方法</h2>
<p><b>被测对象</b>：DeepSeek <code>deepseek-flash</code> / <code>deepseek-v4-pro</code> 驱动的 tool-calling loop（真实 LLM 决策）。
<b>工具</b>：5 个合成 mock 工具（查科室 / 查排班 / 查楼层 / 建预约 / 通用问答）。<b>评分</b>：8 维，rule-based（确定性，pytest 17 断言校验）与 LLM-as-Judge（<code>deepseek-v4-pro</code>）双通道。</p>

<h2>8 维能力（LLM-as-Judge）</h2>
{bar_section("flash vs v4-pro 各维度得分", f_dim_llm, p_dim_llm)}

<h2>模型对比：flash vs v4-pro</h2>
<div class="tblwrap"><table>
<thead><tr><th>指标</th><th class="num">flash</th><th class="num">v4-pro</th></tr></thead>
<tbody>{cmp_table}</tbody>
</table></div>

<div class="finding fail"><h3>反直觉发现：更强 ≠ 得分更高</h3>
<p>v4-pro 的 LLM-as-Judge 总分 <b>反而更低</b>（{pm['llm_overall']:.2f} vs {fm['llm_overall']:.2f}），差距几乎全在「工具选择」（−0.15）与「参数正确」（−0.07）。</p>
<p>但 v4-pro 更「干净」：工具成功率 <b>100%</b>（零错误 vs flash 3 次）、Pass^3 更高（{pm['pass_hat_3']:.2f} vs {fm['pass_hat_3']:.2f}）。</p></div>

<div class="finding"><h3>根源：工具使用策略差异</h3>
<p>flash 倾向「先调工具再回答」；v4-pro 倾向「用自己的知识直接回答/追问」。v4-pro 调用少 13 次却零出错，但「该调工具时直接答了」被 LLM judge 判为工具选择错误。</p>
<p>这揭示一个评测 bias：<b>「工具调用」被隐含当作「正确」，而「不调工具直接答对」被当作「偷懒」</b>——二者现实中可能等价。解法：ground truth 应标注「哪些任务<em>必须</em>调工具」，而非一刀切假设「正确=调了工具」。</p></div>

<div class="finding warn"><h3>双 Grader 在「任务完成/停止决策」判断相反</h3>
<p>rule-based 认为任务完成 0.93（有回答即完成），LLM 认为 0.57（只追问未执行）；rule 认为停止决策 0.57（遗漏工具），LLM 认为 0.94（追问是合理停止）。</p>
<p>根源：expected 的 <code>correct_tools</code> 假设「唯一正确=直接调这些工具」，惩罚了合理但不同的「先追问」行为。</p></div>

<h2>逐样本明细（LLM-as-Judge 得分）</h2>
<div class="tblwrap"><table>
<thead><tr><th>样本</th><th>场景</th><th>输入</th><th class="num">flash</th><th class="num">v4-pro</th><th class="num">Δ</th></tr></thead>
<tbody>{sample_rows}</tbody>
</table></div>

<div class="note"><b>诚实声明</b>：30 条合成样本、单场景、温度 0，样本量不足以做统计显著性判断。
核心价值不在绝对分数，而在揭示的评测设计问题（ground truth 粒度、工具调用 bias、一致性需随机性）。</div>

<footer>生成于 agent-eval-lab · 数据源 reports/openjudge/{{real_eval, real_eval_pro}}/ · 可复现 bash scripts/run_real_eval.sh</footer>
</div>"""
    return html


if __name__ == "__main__":
    OUT.write_text(build_html(), encoding="utf-8")
    print(f"HTML 报告 → {OUT}")
