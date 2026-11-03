# Evaluation_agent 科研升级执行任务

请阅读 `Research_Plan_ZH.md` 与 `Manuscript.md`。目标是验证评测器修复能否同时接纳有效替代路径并控制无效轨迹误放行。已完成的只有固定版本离线审计与 35 条位置诊断；正式方法和跨域实验尚未实现。严禁伪造结果、人工标签或显著性。

## Phase 0：复现与冻结

在隔离 checkout 固定 commit `1422f412f25fd55a282e4551739a24e7deb3649f` 运行 `repro/`。保留用户现有变更，不回退当前工作区，不覆盖旧缓存。核对 6,300 条、2,100 judge、0 重算差异、25 隔离单测；r=−0.7882524836，去 M3=−0.2805483459；A 设 1 差距 .0794747917，真实删除 .1273596667。35 诊断中 21 无效均被旧规则放行。

输出输入哈希、重复输入与终止原因报告。所有旧数据划为探索材料，不进入未来测试集。审计的分数容器替身不是 OpenJudge 集成验证。

## Phase 1：执行和数据语义

改 `real_agent.py`、runner，终止原因独立字段，max_turns/runtime_error 不当模型最终回答。`providers.py`/`run_multimodel.py` 捕获 request 与 served model，按代码/数据/policy/prompt/schema/model/budget 指纹缓存，禁止只凭文件存在复用。

新增 env_v2：固定逻辑时钟、随机实体事实、持久预约/库存/授权表、幂等键、pre/post state hash、只追加事件与快照回放。工具声明 read_set/write_set、纯读、权限与可能部分提交；错误不等于未提交。

必要测试：重复非幂等写产生差异；同幂等键不双写；报错后已提交可识别；未授权写被记录；回滚不删除历史；不同周日期按固定时钟正确；指纹变化不误命中。

## Phase 2：强基线和契约同时实现

契约从可见政策写，含 goal/entity/evidence/freshness/authorization/forbidden_effects/completion。独立 oracle 不调用被评 grader 的核心判断。保留 legacy、A-set1、A-remove、D，并实现完整 state+communication、milestone+minefield 基线。

新判定 PASS/FAIL/UNKNOWN，另有 COMPLETE/VALID_PENDING/FAILED，每项失败给证据 ID，成本单列。不能把任意图匹配伪称线性；设搜索预算，超时 UNKNOWN。

验收：参考 PASS；重复纯读仍正确但成本高；错楼层/实体/空答不 PASS；合理追问 pending；证据缺失 UNKNOWN；相同终态但晚授权 FAIL。对强基线提供同样信息，防止不公平获胜。

## Phase 3：开发集认证变换

12 家族×2 世界 pilot。先 duplicate_pure_read、commute_independent_reads、wrong_entity、wrong_value、missing_final，再 alternative_authorized_source、late_authorization。候选要真实沙箱回放，不能只编辑返回 JSON。

每对记录适用性、前提、义务、附带变化、证据、回放、独立 oracle。正例不能自动按变换名定真；负例必须可证明破坏条件。输出完整可展开 JSONL 或本地 HTML 报告。不适用和 UNKNOWN 都保留。

## Phase 4：审阅与预注册

导出盲审，不暴露模型、分数、预期变换标签，保留证据、分歧与 uncertainty。研究负责人审定政策，冻结 family split、主要比较、阈值、样本量、模型预算和分析版本。

正式目标 160 家族×2世界，40/20/100 家族开发/校准/测试；先确认零售许可与独立语义，不能换词冒充新家族。相同世界、模板兄弟和变换都不能泄漏跨 split。

## Phase 5：正式运行与分析

环境、独立标签与强基线通过后，再跑 2,000 自然 rollouts。5 配置尽量来自不同家族，核验当时可用版本，记录响应身份。不得自动动用无限 API 预算。

family cluster bootstrap、配对、主比较校正，报告误拒绝、误放行、UNKNOWN、覆盖、成本及区间。未达到非劣条件就是未达标，禁止挑阈值、删模型或把探索集改名测试。

每阶段交付：目的、diff、实际命令、日志、测试、最小样例和剩余问题。每图绑定输入与脚本。先完成 Phase 0–1，再推进后续。独立审阅和研究判断由负责人安排，不能自动填成已完成。
