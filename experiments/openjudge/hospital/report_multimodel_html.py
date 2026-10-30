# -*- coding: utf-8 -*-
"""三模型 × 温度 × 工具姿态 完整 HTML 报告（自包含，浏览器直接打开）。

修正版：核心发现从「能力-评测悖论（跳过工具）」改为「工具使用姿态多样性被单一 ground truth 惩罚」。
输出：reports/openjudge/multimodel/report.html + figures/posture.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from samples import SAMPLES
from tool_requirement import TOOL_REQUIREMENT, BUCKET_ZH

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
OUT = REPORTS / "multimodel"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

DIMS = ["intent_accuracy", "tool_selection", "argument_correctness",
        "task_completion", "groundedness", "safety",
        "trajectory_efficiency", "stop_decision"]
DIM_ZH = {"intent_accuracy": "意图准确", "tool_selection": "工具选择",
          "argument_correctness": "参数正确", "task_completion": "任务完成",
          "groundedness": "有依据", "safety": "安全",
          "trajectory_efficiency": "轨迹高效", "stop_decision": "停止决策"}
BUCKETS = ["must", "optional", "none"]

MODELS_T0 = [
    ("flash", "deepseek-flash", "real_eval"),
    ("v4pro", "deepseek-v4-pro", "real_eval_pro"),
    ("minimax-m3", "MiniMax-M3", "multimodel/minimax-m3__t0.0"),
]


def load(rel: str):
    traces = [json.loads(l) for l in open(REPORTS / rel / "real_traces.jsonl", encoding="utf-8")]
    rule = json.load(open(REPORTS / rel / "rule_scores.json", encoding="utf-8"))
    llm = [json.loads(l) for l in open(REPORTS / rel / "llm_scores.jsonl", encoding="utf-8")]
    return traces, rule, llm


def aggregate(scores: dict) -> float:
    return scores.get("safety", 1.0) * (sum(scores.values()) / len(scores))


def _is_pass(s, thr=0.75):
    return s >= thr


def consistency(rule) -> dict:
    ts = {tid: [aggregate(rule[tid][str(t)]) for t in range(3)] for tid in rule}
    single = sum(1 for sc in ts.values() for s in sc if _is_pass(s)) / (len(ts) * 3)
    p3 = phat3 = 0.0
    for sc in ts.values():
        c = sum(1 for s in sc if _is_pass(s))
        p3 += 1.0 - math.comb(3 - c, 3) / math.comb(3, 3)
        phat3 += (c / 3) ** 3
    return {"single_pass": single, "pass_at_3": p3 / len(ts), "pass_hat_3": phat3 / len(ts)}


def dim_means(rule) -> dict:
    acc = {d: [] for d in DIMS}
    for tid in rule:
        for t in range(3):
            for d in DIMS:
                acc[d].append(rule[tid][str(t)][d])
    return {d: sum(v) / len(v) for d, v in acc.items()}


def llm_means(llm) -> dict:
    return {d: sum(r["dims"][d] for r in llm) / len(llm) for d in DIMS}


def posture(traces) -> dict:
    """工具使用姿态：exact / under(追问) / over(过度探索) / other。"""
    expected = {s["task_id"]: s["expected"]["correct_tools"] for s in SAMPLES}
    st = {"exact": 0, "under": 0, "over": 0, "other": 0, "total": 0}
    examples = {"under": [], "over": []}
    for t in traces:
        actual = [s["tool"] for s in t["trajectory"] if s["type"] == "tool_call"]
        want = expected[t["task_id"]]
        st["total"] += 1
        if actual == want:
            st["exact"] += 1
        elif len(actual) == 0:
            st["under"] += 1
            if len(examples["under"]) < 3:
                examples["under"].append((t["task_id"], t["trial"], actual, want,
                                          t["query"][:24]))
        elif len(actual) > len(want):
            st["over"] += 1
            if len(examples["over"]) < 3:
                examples["over"].append((t["task_id"], t["trial"], actual, want,
                                         t["query"][:24]))
        else:
            st["other"] += 1
    return st, examples


def bucket_dims(rule) -> dict:
    out = {b: {d: [] for d in DIMS} for b in BUCKETS}
    for tid in rule:
        b = TOOL_REQUIREMENT[tid]
        for t in range(3):
            for d in DIMS:
                out[b][d].append(rule[tid][str(t)][d])
    return {b: {d: sum(v) / len(v) for d, v in v.items()} for b, v in out.items()}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    # ── 加载 ──
    models = {}
    for key, disp, rel in MODELS_T0:
        traces, rule, llm = load(rel)
        models[key] = {
            "disp": disp, "traces": traces, "rule": rule, "llm": llm,
            "cons": consistency(rule), "dim_rule": dim_means(rule),
            "dim_llm": llm_means(llm),
            "rule_overall": sum(aggregate(rule[tid][str(t)]) for tid in rule for t in range(3)) / (len(rule) * 3),
            "llm_overall": sum(r["score"] for r in llm) / len(llm),
            "posture": posture(traces)[0], "posture_ex": posture(traces)[1],
            "bucket": bucket_dims(rule),
        }

    # 温度对比（实验 A）
    temp_models = {}
    for key, rel in (("v4pro", "real_eval_pro"), ("v4pro-t0.3", "multimodel/v4pro__t0.3"),
                     ("flash", "real_eval"), ("flash-t0.3", "multimodel/flash__t0.3")):
        traces, rule, llm = load(rel)
        temp_models[key] = {"cons": consistency(rule)}

    # ── 图：姿态堆叠 ──
    fig, ax = plt.subplots(figsize=(8, 4.5))
    keys = ["flash", "v4pro", "minimax-m3"]
    labels = ["exact 精确", "under 追问", "over 过度", "other 其它"]
    colors = ["#14964a", "#1f5fe8", "#b8720d", "#9aa5b1"]
    bottoms = [0, 0, 0]
    for i, lab in enumerate(labels):
        k = ["exact", "under", "over", "other"][i]
        vals = [models[m]["posture"][k] / models[m]["posture"]["total"] for m in keys]
        ax.bar(range(3), vals, bottom=bottoms, color=colors[i], label=lab)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_xticks(range(3)); ax.set_xticklabels([models[m]["disp"] for m in keys])
    ax.set_ylabel("比例"); ax.set_ylim(0, 1)
    ax.set_title("工具使用姿态分布（temp=0，90 trial）")
    ax.legend(ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    plt.tight_layout(); fig.savefig(FIG / "posture.png", dpi=120); plt.close(fig)

    # ── HTML ──
    def model_row(key):
        m = models[key]
        c = m["cons"]
        return (f"<tr><td><b>{m['disp']}</b></td>"
                f"<td class='num'>{c['single_pass']:.2f}</td>"
                f"<td class='num'>{c['pass_at_3']:.2f}</td>"
                f"<td class='num'>{c['pass_hat_3']:.2f}</td>"
                f"<td class='num'>{m['rule_overall']:.2f}</td>"
                f"<td class='num'>{m['llm_overall']:.2f}</td></tr>")

    def posture_row(key):
        m = models[key]; st = m["posture"]; n = st["total"]
        return (f"<tr><td><b>{m['disp']}</b></td>"
                f"<td class='num'>{st['exact']}/{n}</td>"
                f"<td class='num'>{st['under']}/{n}</td>"
                f"<td class='num'>{st['over']}/{n}</td>"
                f"<td class='num'>{st['other']}/{n}</td></tr>")

    # 8 维对比表（rule）
    dim_rows = ""
    for d in DIMS:
        dim_rows += (f"<tr><td>{DIM_ZH[d]}</td>"
                     + "".join(f"<td class='num'>{models[m]['dim_rule'][d]:.2f}</td>"
                               for m in keys)
                     + "</tr>")
    # 8 维对比表（llm）
    dim_rows_llm = ""
    for d in DIMS:
        dim_rows_llm += (f"<tr><td>{DIM_ZH[d]}</td>"
                         + "".join(f"<td class='num'>{models[m]['dim_llm'][d]:.2f}</td>"
                                   for m in keys)
                         + "</tr>")

    # 分桶表
    bucket_rows = ""
    for b in BUCKETS:
        for d in ["tool_selection", "groundedness", "task_completion", "stop_decision"]:
            bucket_rows += (f"<tr><td>{BUCKET_ZH[b]}</td><td>{DIM_ZH[d]}</td>"
                            + "".join(f"<td class='num'>{models[m]['bucket'][b][d]:.2f}</td>"
                                      for m in keys)
                            + "</tr>")

    # 温度一致性表
    temp_rows = ""
    for key, disp in (("v4pro", "v4-pro t0"), ("v4pro-t0.3", "v4-pro t0.3"),
                      ("flash", "flash t0"), ("flash-t0.3", "flash t0.3")):
        c = temp_models[key]["cons"]
        temp_rows += (f"<tr><td>{disp}</td>"
                      f"<td class='num'>{c['single_pass']:.2f}</td>"
                      f"<td class='num'>{c['pass_at_3']:.2f}</td>"
                      f"<td class='num'>{c['pass_hat_3']:.2f}</td>"
                      f"<td class='num'>{c['pass_at_3']-c['pass_hat_3']:+.2f}</td></tr>")

    # 姿态示例（under / over）
    under_ex = ""
    for tid, trial, actual, want, q in models["v4pro"]["posture_ex"]["under"]:
        under_ex += f"<li><code>{tid}</code> 「{esc(q)}…」 → 零工具调用，改为追问（期望 {want}）</li>"
    over_ex = ""
    for tid, trial, actual, want, q in models["minimax-m3"]["posture_ex"]["over"]:
        over_ex += f"<li><code>{tid}</code> 「{esc(q)}…」 → 调 {len(actual)} 个工具（期望 {len(want)} 个）</li>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>多模型工具调用 Agent 评测报告</title>
<style>
:root{{--bg:#f5f7fa;--surface:#fff;--surface2:#eef1f6;--text:#1a2332;--muted:#5a6b82;
--border:#d8dfe8;--accent:#1f5fe8;--accent-soft:#e8effd;--pass:#14964a;--fail:#d52b2b;--warn:#b8720d}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0d1117;--surface:#161c26;
--surface2:#1c2330;--text:#e6edf3;--muted:#8b98a8;--border:#2a3442;--accent:#5b8def;
--accent-soft:#16233c;--pass:#2ea86a;--fail:#e5534b;--warn:#d99a2b}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;
line-height:1.7}} .wrap{{max-width:980px;margin:0 auto;padding:48px 24px 90px}}
header{{border-bottom:1px solid var(--border);padding-bottom:24px;margin-bottom:32px}}
.kicker{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:600;margin:0 0 8px}}
h1{{font-size:30px;margin:0 0 8px;letter-spacing:-.01em}}.sub{{color:var(--muted);margin:0}}
h2{{font-size:20px;margin:44px 0 14px}}.find{{background:var(--surface);border-left:3px solid var(--accent);
border-radius:0 8px 8px 0;padding:16px 18px;margin:14px 0}}.find.fail{{border-left-color:var(--fail)}}
.find.warn{{border-left-color:var(--warn)}}.find h3{{margin:0 0 8px;font-size:16px}}
table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border)}}
th{{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase}}
td.num,th.num{{text-align:right}}.tblwrap{{overflow-x:auto;background:var(--surface);border:1px solid var(--border);
border-radius:10px;margin:10px 0}}.tblwrap table{{min-width:520px}}
img{{max-width:100%;border-radius:10px;margin:10px 0}}code{{font-family:ui-monospace,Consolas,monospace;
font-size:13px;background:var(--surface2);padding:1px 6px;border-radius:4px}}
.note{{background:var(--surface2);border-radius:8px;padding:14px 18px;font-size:14px;color:var(--muted);margin:16px 0}}
li{{margin:6px 0}}
</style></head><body><div class="wrap">
<header>
  <p class="kicker">Agent Evaluation · Multi-Model</p>
  <h1>工具调用 Agent 评测：三模型 × 温度 × 工具姿态</h1>
  <p class="sub">deepseek-flash / deepseek-v4-pro / MiniMax-M3 · 30 样本 × 3 trial · 双 Grader（rule 8 维 + LLM-as-Judge）</p>
</header>

<h2>执行摘要</h2>
<p>核心结论：<b>三个模型有三种截然不同的「工具使用姿态」，而 ground truth 只编码了一种「标准动作序列」。
过程型 Grader 把偏离标准的姿态一律打低分，导致「模型得分 = 离标准姿态多远」，而非「能力多强」。</b></p>
<div class="tblwrap"><table>
<thead><tr><th>模型</th><th class="num">单次通过</th><th class="num">Pass@3</th><th class="num">Pass^3</th><th class="num">rule 总分</th><th class="num">LLM 总分</th></tr></thead>
<tbody>{''.join(model_row(k) for k in keys)}</tbody></table></div>
<div class="find fail"><h3>能力-评测悖论（修正版）</h3>
<p>最强推理模型 <b>MiniMax-M3</b> 的 rule 总分（{models['minimax-m3']['rule_overall']:.2f}）反而最低，
因为它「过度探索」的姿态被「精确序列匹配 + 效率 ≤2 工具」双重惩罚；LLM-judge 稍宽容（{models['minimax-m3']['llm_overall']:.2f}），但仍三家垫底。</p></div>

<h2>工具使用姿态（本报告核心发现）</h2>
<div class="tblwrap"><table>
<thead><tr><th>模型</th><th class="num">exact 精确</th><th class="num">under 追问</th><th class="num">over 过度</th><th class="num">other 其它</th></tr></thead>
<tbody>{''.join(posture_row(k) for k in keys)}</tbody></table></div>
<img src="figures/posture.png" alt="姿态分布">
<div class="find"><h3>三种姿态</h3>
<ul>
<li><b>flash / v4-pro ——「先追问」姿态</b>：面对缺患者姓名/具体日期的请求，不调工具而是追问。规则判「工具选择=0」，LLM 判「合理」。{under_ex}</li>
<li><b>MiniMax-M3 ——「过度探索」姿态</b>：连调多工具（查完科室还查楼层），极端时超出 max_turns 无结论。{over_ex}</li>
<li><b>无模型「知识内化跳过工具」</b>——原假设「更强模型跳过工具直接答」不成立。</li>
</ul></div>

<h2>8 维能力对比</h2>
<p style="color:var(--muted)">Rule-based（确定性规则，精确序列匹配）</p>
<div class="tblwrap"><table>
<thead><tr><th>维度</th>{''.join(f"<th class='num'>{models[m]['disp']}</th>" for m in keys)}</tr></thead>
<tbody>{dim_rows}</tbody></table></div>
<p style="color:var(--muted)">LLM-as-Judge（语义合理性，deepseek-v4-pro）</p>
<div class="tblwrap"><table>
<thead><tr><th>维度</th>{''.join(f"<th class='num'>{models[m]['disp']}</th>" for m in keys)}</tr></thead>
<tbody>{dim_rows_llm}</tbody></table></div>
<div class="find warn"><h3>双 Grader 系统性分歧（非噪声）</h3>
<p><code>工具选择</code>：rule {models['flash']['dim_rule']['tool_selection']:.2f} vs LLM {models['flash']['dim_llm']['tool_selection']:.2f}（flash）；
<code>停止决策</code>：rule {models['flash']['dim_rule']['stop_decision']:.2f} vs LLM {models['flash']['dim_llm']['stop_decision']:.2f}。
根因：ground truth 假设「唯一正确=直接调这些工具」，把「先追问」当错误，LLM 却认为合理。</p></div>

<h2>实验 A：温度与一致性</h2>
<div class="tblwrap"><table>
<thead><tr><th>配置</th><th class="num">单次</th><th class="num">Pass@3</th><th class="num">Pass^3</th><th class="num">Pass@3−Pass^3</th></tr></thead>
<tbody>{temp_rows}</tbody></table></div>
<p>温度 0→0.3 引入真实随机性后，Pass@3（至少一次）与 Pass^3（三次全中）的差距被量化；但三模型差距远小于「姿态」带来的差距，说明<b>姿态 bias 比采样方差更主导得分</b>。</p>

<h2>实验 B：工具依赖度分桶</h2>
<div class="tblwrap"><table>
<thead><tr><th>桶</th><th>维度</th>{''.join(f"<th class='num'>{models[m]['disp']}</th>" for m in keys)}</tr></thead>
<tbody>{bucket_rows}</tbody></table></div>
<div class="find"><h3>分桶揭示：过程惩罚应只作用在 must 桶</h3>
<p>must 桶（答案只在工具里）不调工具=虚构，工具选择该罚；optional/none 桶「不调工具」是合理行为，不该罚。
当前规则对所有桶统一做「精确序列匹配」，是分歧的根源。</p></div>

<h2>Groundedness 盲区（实锤）</h2>
<div class="find warn"><h3>规则版 groundedness 抓不到「跳过工具 + 编造」</h3>
<p>它只在「工具返回了结果但 final 虚构」时能抓到。当模型<b>零工具调用</b>时退化成「看 expected 标签」，
于是「must 任务上跳过工具却编造具体值」这个失败模式永远抓不到。实测中模型倾向「追问」而非「编造」，盲区暂未误判，但这是潜在风险。</p></div>

<h2>诚实声明</h2>
<div class="note">30 条合成样本、单场景、温度 0/0.3，样本量不足以做统计显著性判断。
optional 桶仅 3 样本（H001-H003）。v4-pro 同时当 Agent 和 Judge 存在自偏好偏差。
本报告的贡献在「现象发现 + 姿态/分桶修正框架」，绝对分数仅供参考。</div>
</div></body></html>"""
    (OUT / "report.html").write_text(html, encoding="utf-8")
    print("✅ HTML 报告 →", OUT / "report.html")
    print("✅ 姿态图 →", FIG / "posture.png")


if __name__ == "__main__":
    main()
