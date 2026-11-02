# Posture-Grader：姿态-评测错配修正框架（开源复用指南）

> 一个 **与具体场景无关** 的纯标准库 Python 模块（`posture_grader.py`），
> 供任何「工具调用 Agent 评测」的维护者直接套用，用来诊断并修正一个被广泛忽略的
> 系统性偏差：**单一标准工具序列（ground truth）对模型工具使用姿态（posture）的误罚**。

配套论文见 `docs/paper-draft.md`；本工具把论文里「姿态-评测错配」这一观察
落成可复现、可移植的代码与标注 schema。

---

## 1. 它解决什么问题

工具调用 Agent 的评测普遍这样设计：

- 每个任务给出 ground truth，其中包含一条「标准工具调用序列」`correct_tools`；
- 过程型 rule grader 用 **精确序列匹配** 给 `tool_selection` 打分：调对了 1，调多/调少/调错 0。

但真实模型并不都走这条标准序列。观察到的典型姿态有四种（`classify_posture`）：

| 姿态 | 含义 | 例子 | 结果是否仍可能正确 |
|------|------|------|--------------------|
| `exact` | 实际序列 == 期望序列 | 只查了该查的工具 | ✅ |
| `under` | 实际零工具（先追问） | 信息缺失先问患者 | ✅（结果常对） |
| `over`  | 实际工具数 > 期望（过度探索） | 多查了科室/楼层 | ✅（结果常对） |
| `other` | 长度相同但工具不同（调错） | 查了别的工具 | ❌ |

**问题**：过程型 grader 把 `under`/`over` 这些「偏离标准但结果正确」的姿态也判 0，
于是「姿态不同」被误判成「能力不行」。当两个模型的**真实能力差距**很小、但
**姿态分布差异**很大时，rule grader 会把能力差距**放大 2~3 倍**——本仓库用
cluster bootstrap + McNemar 定量证明了这一点（见 `statistical_significance.py`）。

---

## 2. 四件事（API）

```python
from posture_grader import (
    classify_posture, posture_distribution, rescore, aggregate,
    decompose_gap, BUCKET_MUST, BUCKET_OPTIONAL, BUCKET_NONE,
    ANNOTATION_SCHEMA, DIMS,
)
```

### ① `classify_posture(actual_tools, expected_tools) -> str`
把一次工具调用序列相对期望序列分成 `exact / under / over / other`。
这是姿态的**操作化定义**（基于与 expected 的长度关系），不是对「合理探索 vs 乱调」
的语义判断——见 §5 局限。

### ② `posture_distribution(traces, expected_by_task) -> dict`
聚合一个模型/配置下四种姿态的计数，输出 `{exact, under, over, other, total}`。

### ③ `rescore(dims, bucket, expected_tools, actual_tools, variant) -> dict`
在原始 8 维分基础上按 grader 变体改写过程维，返回新 8 维。五个变体：

| 变体 | 名称 | 改什么 |
|------|------|--------|
| `baseline` | 原 rule grader | 不改（`tool_selection`=精确序列匹配） |
| `A` | 结果型 | 丢弃 3 个过程维（`tool_selection`/`trajectory_efficiency`/`stop_decision` 置 1） |
| `B` | 分桶 | `optional`/`none` 桶关闭 `tool_selection` + `stop_decision` 惩罚 |
| `C` | 姿态感知 | B + `must` 桶 `tool_selection` 改为「必要工具 ⊆ 已调用」 |
| `D` | 全修复 | C + 结果已 `grounded`+`complete` 时不再罚「多调」 |

### ④ `aggregate(scores) -> float`
`safety × mean(8 维)`，与论文聚合口径一致（pass 阈值 0.75）。

### ⑤ `decompose_gap(rows, variants) -> dict`
一次性把「姿态 vs 能力」拆开：给定各模型每 trial 的 8 维分 + bucket + 工具序列，
输出每个变体下各模型的 mean aggregate，用于量化 gap inflation。

---

## 3. 工具依赖度标注 schema（`ANNOTATION_SCHEMA`）

修正在于：**不是所有任务都该罚「不调工具」**。每个任务先标注一个桶：

| 桶 | 定义 | 不该罚的情形 |
|----|------|--------------|
| `must` | 答案只存在于工具返回数据（楼层/排班/预约/政策） | 无（漏调=虚构，该罚） |
| `optional` | 答案可从模型内部知识推导，工具只是可选通道 | 直接回答 = 不该罚 |
| `none` | 无需工具（闲聊/拒绝/澄清） | 不调 = 不该罚 |

`must` 桶还需标注 `necessary_tools`：完成任务**必须**调用的工具集合
（本仓库即 ground truth 的 `correct_tools`）。

JSON 导出（本仓库 `hospital` 场景的完整标注）见 `annotation.json`，
由 `export_annotation.py` 从 `samples.py` + `tool_requirement.py` 自动生成。

---

## 4. 移植到你的 benchmark（三步）

1. **导出轨迹**：把每 trial 的 `(task_id, [实际调用工具序列], [8 维分])` 摊平成
   `posture_distribution` / `decompose_gap` 所需的 `rows` 结构。
2. **打桶标注**：对每个任务标 `must/optional/none`；`must` 桶补 `necessary_tools`。
3. **跑消融**：对每个模型算 `baseline/A/B/C/D` 五个变体的 mean aggregate，
   看「模型间差距」随变体如何变化。若 `baseline` 的差距在 `C/D` 下显著收窄，
   说明你的 benchmark 同样存在姿态-评测错配。

---

## 5. 局限（诚实的边界，论文 Limitations 同步）

- `classify_posture` 是**基于长度的粗分法**：它不区分「合理的多调」（比如多查一层确认）
  与「无意义乱调」；`over` 只是「工具数 > 期望」，不保证语义。
- 姿态分类依赖 ground truth 的 `correct_tools` 本身是可靠的；若某 benchmark 的
  `correct_tools` 标注有噪声，姿态分类同样有噪声。
- `rescore` 的 C/D 变体只在「结果维度本身已可靠打分」的前提下才公平——
  它不修补结果维的打分缺陷，只剔除过程维的姿态误罚。

---

## 6. 复现（本仓库）

```bash
python posture_grader.py                    # 最小 demo
python ablation_posture_grader.py           # 五变体消融（校验 baseline 复现后输出 ablation.json）
python statistical_significance.py          # cluster bootstrap + McNemar
python -m pytest test_date_normalize.py -q  # mock 日期归一化回归
```
