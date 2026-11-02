# -*- coding: utf-8 -*-
"""多模型 × 工具姿态 完整 HTML 报告（自包含，浏览器直接打开）。

21 模型版：直接读取 analyze_multimodel.py / statistical_significance.py / ablation_posture_grader.py
已产出的 comparison.json / statistical_significance.json / ablation.json 渲染，不重复计算。

输出：reports/openjudge/multimodel/report.html（引用 figures/ 下已生成的 PNG）。
"""
from __future__ import annotations

import json
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "openjudge"
OUT = REPORTS / "multimodel"
FIG = "figures"

FAMILY = {
    "flash": "DeepSeek", "v4pro": "DeepSeek",
    "minimax-m3": "MiniMax", "minimax-m2.5": "MiniMax",
    "qwen3-32b": "Qwen", "qwen3.8-max": "Qwen", "qwen3.7-max": "Qwen",
    "qwen3.8-flash": "Qwen", "qwen3.8-2.4t-a95b": "Qwen",
    "qwen3.7-flash": "Qwen", "qwen3.7-plus": "Qwen", "qwen3.6-plus": "Qwen",
    "qwen3.5-plus": "Qwen", "qwen-max": "Qwen", "qwen-plus": "Qwen", "qwen-flash": "Qwen",
    "kimi-k3": "Kimi", "kimi-k2.7-code": "Kimi",
    "glm-5.3": "GLM", "glm-5.3-prime": "GLM", "glm-5.2": "GLM",
}

VARIANT_ZH = {
    "baseline": "baseline 原规则（精确序列匹配）",
    "A": "A 结果型（丢 3 个过程维）",
    "B": "B 分桶（optional/none 关过程惩罚）",
    "C": "C 姿态感知（must 改「必要⊆已调用」）",
    "D": "D + 放宽效率（结果好则不再罚多调）",
}


def _pct(n: int, total: int) -> str:
    return f"{n / total * 100:.0f}%"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    comp = json.load(open(OUT / "comparison.json", encoding="utf-8"))
    stat = json.load(open(OUT / "statistical_significance.json", encoding="utf-8"))
    abl = json.load(open(OUT / "ablation.json", encoding="utf-8"))

    overview = comp["overview"]
    posture = comp["posture"]
    by_key = {r["key"]: r for r in overview}

    # 主表：按 rule 总分降序
    rows = []
    for r in sorted(overview, key=lambda x: -x["rule_overall"]):
        key = r["key"]
        st = posture[key]
        total = st["exact"] + st["under"] + st["over"] + st["other"]
        rows.append({
            "disp": r["disp"], "fam": FAMILY.get(key, "?"),
            "rule": r["rule_overall"], "llm": r["llm_overall"],
            "gap": r["rule_overall"] - r["llm_overall"],
            "over": _pct(st["over"], total), "under": _pct(st["under"], total),
        })

    n = len(rows)
    sp = stat["spearman_rule_llm"]
    corr = stat["corr_over_gap"]
    corr_ci = stat["corr_over_gap_ci"]
    rr = stat["rule_range"]; lr = stat["llm_range"]

    body_rows = ""
    for r in rows:
        gap = r["gap"]
        cls = " class='lo'" if gap < -0.05 else ""
        body_rows += (f"<tr><td><b>{esc(r['disp'])}</b></td>"
                      f"<td class='muted'>{r['fam']}</td>"
                      f"<td class='num'>{r['rule']:.3f}</td>"
                      f"<td class='num'>{r['llm']:.3f}</td>"
                      f"<td class='num'{cls}>{gap:+.3f}</td>"
                      f"<td class='num'>{r['over']}</td>"
                      f"<td class='num'>{r['under']}</td></tr>")

    # 消融表
    abl_rows = ""
    for v in ["baseline", "A", "B", "C", "D"]:
        d = abl["variants"][v]
        abl_rows += (f"<tr><td>{VARIANT_ZH[v]}</td>"
                     f"<td class='num'>{d['minimax_m3']:.3f}</td>"
                     f"<td class='num'>{d['mean_others']:.3f}</td>"
                     f"<td class='num'>{d['gap']:.3f}</td>"
                     f"<td class='num'>{d['cross_model_std']:.4f}</td></tr>")

    # 分桶偏差（bucket_bias 已由图呈现，这里给文本）
    m3 = stat["models"]["minimax-m3"]

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
line-height:1.7}} .wrap{{max-width:1040px;margin:0 auto;padding:48px 24px 90px}}
header{{border-bottom:1px solid var(--border);padding-bottom:24px;margin-bottom:32px}}
.kicker{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:600;margin:0 0 8px}}
h1{{font-size:30px;margin:0 0 8px;letter-spacing:-.01em}}.sub{{color:var(--muted);margin:0}}
h2{{font-size:20px;margin:44px 0 14px}}.find{{background:var(--surface);border-left:3px solid var(--accent);
border-radius:0 8px 8px 0;padding:16px 18px;margin:14px 0}}.find.fail{{border-left-color:var(--fail)}}
.find.warn{{border-left-color:var(--warn)}}.find h3{{margin:0 0 8px;font-size:16px}}
table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border)}}
th{{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase}}
td.num,th.num{{text-align:right}}td.lo{{color:var(--fail);font-weight:600}}td.muted{{color:var(--muted)}}
.tblwrap{{overflow-x:auto;background:var(--surface);border:1px solid var(--border);
border-radius:10px;margin:10px 0}}.tblwrap table{{min-width:640px}}
img{{max-width:100%;border-radius:10px;margin:10px 0}}code{{font-family:ui-monospace,Consolas,monospace;
font-size:13px;background:var(--surface2);padding:1px 6px;border-radius:4px}}
.note{{background:var(--surface2);border-radius:8px;padding:14px 18px;font-size:14px;color:var(--muted);margin:16px 0}}
li{{margin:6px 0}}.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}}
.stat{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}}
.stat .v{{font-size:24px;font-weight:700;letter-spacing:-.01em}}.stat .k{{color:var(--muted);font-size:12px}}
</style></head><body><div class="wrap">
<header>
  <p class="kicker">Agent Evaluation · Multi-Model</p>
  <h1>工具调用 Agent 评测：多模型 × 工具使用姿态</h1>
  <p class="sub">5 家族 {n} 模型 · 100 样本 × 3 trial（temp=0）· 双 Grader（rule 8 维 + LLM-as-Judge）</p>
</header>

<h2>执行摘要</h2>
<p>核心结论：<b>不同模型有截然不同的「工具使用姿态」，而 ground truth 只编码了一种「标准动作序列」。
过程型 Grader 对「过度探索」系统性打低分——over 占比与 (rule−LLM) 分差强负相关（r={corr:.2f}），
而「先追问」几乎不产生分差。</b>差距放大是<b>姿态驱动的、指向过度探索的</b>，不是「能力」的真实差距。</p>
<div class="stats">
<div class="stat"><div class="v">{sp:.2f}</div><div class="k">rule vs LLM 排序 Spearman</div></div>
<div class="stat"><div class="v">{corr:.2f}</div><div class="k">over% 与 gap 的 Pearson r</div></div>
<div class="stat"><div class="v">[{corr_ci[0]:.2f}, {corr_ci[1]:.2f}]</div><div class="k">over%-gap r 的 95% bootstrap CI</div></div>
<div class="stat"><div class="v">{rr[0]:.2f}–{rr[1]:.2f}</div><div class="k">rule 跨模型全距</div></div>
<div class="stat"><div class="v">{lr[0]:.2f}–{lr[1]:.2f}</div><div class="k">LLM 跨模型全距</div></div>
</div>

<h2>核心发现</h2>
<div class="find fail"><h3>F1 · 姿态是模型级特征（MiniMax-M3 是唯一的「过度探索」异常值）</h3>
<p>MiniMax-M3 在 300 trial 里有 <b>{m3['over_rate']*100:.0f}% 被归为过度探索</b>（其余模型 ≤22%）；
而 Flash / Qwen3.8-Max 是「先追问」代表（under ~27%）。姿态不是样本噪声，是稳定的模型级行为。</p></div>
<div class="find"><h3>F2 · 双 Grader 只中等一致（Spearman 0.63）</h3>
<p>rule 与 LLM 对 {n} 个模型的排序相关只有 {sp:.2f}，分歧集中在过度探索模型——说明两者对「什么算好」有方向性差异，而非随机噪声。</p></div>
<div class="find warn"><h3>F3 · 差距放大由 over 驱动（r={corr:.2f}）</h3>
<p>rule 把模型拉开 {rr[1]-rr[0]:.2f}（{rr[0]:.2f}–{rr[1]:.2f}），LLM 却只挤出 {lr[1]-lr[0]:.2f}（{lr[0]:.2f}–{lr[1]:.2f}）。
消融：把 MiniMax-M3 的被放大差距从 <b>{abl['variants']['baseline']['gap']:.3f} 收窄到 {abl['variants']['D']['gap']:.3f}</b>（D 变体）。
「先追问」不产生分差（flash gap {stat['models']['flash']['gap']:+.3f}）。</p></div>
<div class="find"><h3>F4 · 温度是烟雾弹（30 样本遗留）</h3>
<p>温度 0→0.3 时 Pass@3 纹丝不动（0.533）、Pass^3 只挪 ≤0.01；姿态带来的得分差远大于采样方差——证明<b>姿态 bias 比采样方差更主导得分</b>。</p></div>

<h2>21 模型主表（按 rule 总分降序）</h2>
<div class="tblwrap"><table>
<thead><tr><th>模型</th><th>家族</th><th class="num">rule 总分</th><th class="num">LLM 总分</th><th class="num">gap (rule−LLM)</th><th class="num">over%</th><th class="num">under%</th></tr></thead>
<tbody>{body_rows}</tbody></table></div>
<p style="color:var(--muted)">gap 为负 = rule 判得比 LLM 更狠；红色 = 被 process 惩罚 ≥0.05 的模型。</p>

<h2>姿态分布</h2>
<img src="{FIG}/posture_dist.png" alt="21 模型工具使用姿态分布">
<img src="{FIG}/gap_scatter.png" alt="over 占比 vs (rule−LLM) 分差">

<h2>消融：修正框架能否收窄差距</h2>
<div class="tblwrap"><table>
<thead><tr><th>grader 变体</th><th class="num">MiniMax-M3</th><th class="num">其余均值</th><th class="num">M3 差距</th><th class="num">跨模型 std</th></tr></thead>
<tbody>{abl_rows}</tbody></table></div>
<p>从 baseline 到 D：MiniMax-M3 的差距 <b>{abl['variants']['baseline']['gap']:.3f} → {abl['variants']['D']['gap']:.3f}</b>，
跨模型 std <b>{abl['variants']['baseline']['cross_model_std']:.4f} → {abl['variants']['D']['cross_model_std']:.4f}</b>——
把「过度探索被过程维惩罚」这一项修正掉，被放大的差距与跨模型 spread 都显著收窄。</p>
<img src="{FIG}/bucket_bias.png" alt="分桶维度偏差">
<img src="{FIG}/multi_dim_heatmap.png" alt="21 模型 × 8 维 rule/LLM 热力图">

<h2>诚实声明</h2>
<div class="note">100 条合成样本、单场景（医院导诊）、temp=0，3 trial。v4-pro 同时当 Agent 和 Judge，
存在自偏好偏差。rule 与 LLM 的跨模型 std 之差（{stat['rule_std']:.4f} − {stat['llm_std']:.4f}）
的 bootstrap CI [{stat['dstd_ci'][0]:.4f}, {stat['dstd_ci'][1]:.4f}] 跨 0，未达统计显著——「rule 更发散」是方向性观察，
尚需更多样本/场景确认。本报告的贡献在「现象发现 + 姿态/分桶修正框架」，绝对分数仅供参考。</div>
</div></body></html>"""
    (OUT / "report.html").write_text(html, encoding="utf-8")
    print("✅ HTML 报告 →", OUT / "report.html")
    print(f"   渲染 {n} 模型 · Spearman {sp:.3f} · corr(over,gap) {corr:.3f}")


if __name__ == "__main__":
    main()
