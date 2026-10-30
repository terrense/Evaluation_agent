# WORKLOG

> Claude Code hooks 自动追加：会话开始 / 每条任务 / 每轮结果，均带时间戳。
> 终端被误关也不丢——用每段开头的 `claude --resume <id>` 直接恢复原会话。

---

## 2026-10-30 17:32:30  会话开始  `fd5c544d`

崩了/误关终端后恢复：`claude --resume fd5c544d-b67e-446c-87c9-0d4648a27bd9`

**[2026-10-30 17:34:37] 结果**

- 改动文件：`F:\agent-eval-lab\experiments\openjudge\hospital\analyze_multimodel.py`、`F:\agent-eval-lab\experiments\openjudge\hospital\tool_requirement.py`
- 执行命令：2 条
- 小结：「都需要」三件事全部收口，下面是最终交付汇总。  ## 1. 修正了那个标错的指标  原 `correct_but_no_tool` 是个**误命名**——它实际统计的是「有依据=1 且 完成=1 且 工具选择=0」，而 `tool_selection==0` 表示「实际序列 ≠ 期望序列」，包含三种姿态：**零工具追问(under) / 额外工具(over) / 错误工具(other)**，并不只是「没调工具」。  已把 `analyze_multimodel.py` 里的函数、JSON key、报告叙事三处统一改成 `correct_but_sequence_mismatch`，并重跑生成 `comparison.json`（数字不变，仅 key + 叙事）。`report_multimodel_html.py` 直接读原始 traces，不依赖这个 key，所以 HTML 报告从生成时起就是修正版。  ## 2. 核心结论修正（这是本次最重要的产出）  | | 旧假设（已推翻） | 修正后的真实发现 | |---|---|---| | 现象 | 强模型「知识内化后跳过工具」被误罚 | **三种工具使用姿态并存**，被单一 ground truth 惩罚 | | 证据 | ❌ 没有任何模型跳过 must 工具去编造 | flash/v4-pro「先追问」、MiniMax-M3「过度探索」 | | 命名 | 能力-评测悖论（跳过工具版） | **姿态-评测错配**（posture–grader misalignment） |  关键点：must 桶不调工具必然虚构（有依据=0），三模型里这种签名几乎不出现——模型倾向**追问**而非**编造**。所以真正的 bias 不在「跳过工具」，而在「ground truth 只编码一条标准序列，容纳不下等价但不同的完成路径」。   …

### [2026-10-30 19:37:12] 任务
鍐欙紒鍙槸鎴戞病鏈夊埆鐨刟pi浜? 鍥藉唴澶ч檰杩樹拱涓嶅埌chatgpt涔嬬被鐨刟pi

**[2026-10-30 19:48:31] 结果**

- 改动文件：`F:\agent-eval-lab\experiments\openjudge\hospital\ablation_posture_grader.py`、`F:\agent-eval-lab\docs\paper-draft.md`、`F:\agent-eval-lab\docs\paper-outline.md`
- 执行命令：2 条
- 小结：全部收口。你不在的这段时间，我把「能独立做的」都做完了，进度如下：  ## 这轮完成的事  **1. 论文全文写完** → `docs/paper-draft.md`（英文，Abstract→Intro→Related Work→Method→4 RQ→Results→Fix→Limitations→Conclusion→Appendix→References，可直接转 LaTeX）。  **2. 做了最有说服力的一张表——姿态感知 grader 消融**（`ablation_posture_grader.py`，用现有数据，**baseline 精确复现 0.783/0.793/0.644** 才继续）：  | grader 变体 | flash | v4-pro | MiniMax-M3 | 倒挂 | |---|---|---|---|---| | 原 rule（精确序列） | .783 | .793 | .644 | **−.149** | | 全修复（分桶+姿态感知+放宽效率） | .796 | .800 | .735 | **−.065** |  → 修正后倒挂**缩小 56% 但没消失**，和 LLM judge 的 −.043 一致。这推翻了我之前「倒挂是假象」的说法，换成更站得住的结论：**MiniMax 有真实结果短板，rule grader 把本不大的真实差距放大了 2–3 倍**（gap inflation，不是凭空倒挂）。全文、摘要、F3/F4 都改成了这个口径。  **3. 引用全部核实**（WebSearch 逐条查过，不是编的）： - SABench = *Task Success Is Not Enough*（arXiv:2610.34167，NeurIPS 2026） - τ-bench（arXiv:2406.12045）——**并修正了  …

