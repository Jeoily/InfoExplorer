# 有界研究闭环：详细设计与实施边界

2026-10-19 更新：Python 会话与模型适配层已接入独立 v3 HTTP、Java 和 React，并完成外部工具模拟的联调。详见 [v3 契约](../contracts/WEB_RESEARCH_V3.md) 与 CURRENT_STATE。日常 v2 仍为无模型摘录；真实供应商验证和日常库升级不能从离线结果推定。以下描述设计与原首轮实现边界。

依据：[厂商公开策略](../research/RESEARCH_AGENT_STRATEGIES_20261019.md)。这是适合本项目的取舍，不是厂商内部架构的复刻。

## 流程与职责

问题 → 模型计划 → 搜索/正文读取 → 模型缺口判断 → 条件补搜 → 模型报告 → 程序引用校验 → 会话结果。

research_session.py 负责严格输出解析、共享预算、阶段记录及停止原因；model_completion.py 提供显式创建的 JsonCompletion，复用既有有界 HTTPS 传输。原 pipeline 继续负责来源、稳定证据、审核快照及失败证据保留。

这是受程序约束的工作流：模型决定子问题、检索词及是否补搜，不能增加工具、权限或循环次数。不是无限自主 Agent，没有多 Agent 调度。

## 模型契约

| 阶段 | 输出 | 程序约束 |
|---|---|---|
| plan | scope；questions[{id,question,evidenceNeed}]；queries | 1–8 个唯一 Q1..Q8；1–3 个非重复检索词；文本长度与额外字段校验 |
| review | action=finish/supplement；reason；coverage[{questionId,state,evidenceIds,gap}]；queries | 覆盖全部子问题；covered/partial 须引用现有证据；partial/missing 须说明缺口；补搜 1–2 个新词且不重复旧查询；全部 covered 不得补搜 |
| report | claims[{kind,text,evidenceIds}]；limitations | kind=source_statement/inference；结论须引用最终证据；必须给出局限；拒绝假编号、文本内伪引用及超长报告 |

拒绝额外字段、重复 JSON 键、非有限值、超长响应、未完成回复及模型工具调用。使用文本 JSON，不要求供应商支持特定 structured-output 扩展。

模型只收到问题、语言、已验证结构的计划、公开证据与来源元数据；网页是数据而非系统指令。不授予文件、终端和数据库工具。此边界不代表已证明免疫语义提示注入。

推断在渲染时显式标记。程序可以验证引用存在与身份，不能证明证据在语义上支持结论。独立支持性复核尚未实现；模型判断 covered 不等于事实核验。

## 预算与停止

默认统一 ExecutionBudget：150 秒总预算，每次工具最多 20 秒，最多 5 次搜索、8 次正文读取、3 次模型调用（plan/review/report）。失败尝试计入预算；进程终止清理允许短暂回收余量，不宣称毫秒级硬实时。

- EVIDENCE_SUFFICIENT：模型判断资料够用，停止检索并生成报告。
- SUPPLEMENT_ROUND_LIMIT：缺口触发一次补搜后结束。新增证据没有第二次审核，coverage 保留 partial，报告输入明确标记补搜后未复核。
- NO_PRODUCTIVE_SEARCH：仍有缺口但没有值得继续搜索的方向，报告说明局限。
- NO_USABLE_EVIDENCE 或读取失败：不调用报告模型凭空回答。
- 规划格式错误/暂时失败：降级原问题检索并保存 planReason，不重复规划；认证、配置、输入过大或忙碌则直接终止。
- 审核/报告失败：保留已读证据，报告不伪装成成功。取消、超时及预算耗尽由程序控制。

“一次补搜”是上限而非固定步骤。扩大循环前必须同时设计每轮快照、引用集合变化和总预算。

## 会话、数据库与恢复

当前内存 Session 包含 version/runId、planMode/planReason、验证后的 plan/decision/report、stopReason、events、usage、outcome。规划阶段终止时 outcome=null；后续失败沿用 Outcome 保留部分证据。events 仅记录阶段、状态、安全错误码和输入 hash，不记录凭据、提供商原始错误或私有推理。

events 当前是阶段结果记录，不是实时流或持久化检查点；数据库尚未保存 Session。

下一轮接口方案：

1. 显式增加模型研究选择，创建幂等比较包含选择，重试不得暗改模式。候选值 web-model-research；最终字段形式应在双端实施前定稿。
2. Python 新版本化会话接口与非敏感供应商/提示版本信息；旧 v2 保持 direct/web-extract/modelCalls=0。
3. Java 按模式严格验证并按 taskId/runId 保存会话，不把 Session 塞进现有 WebReport。首选独立版本化会话快照字段；实施时新增迁移，旧迁移不改。
4. 将来新增按运行/序号唯一的阶段事件和检查点，调用开始/完成分别记录。崩溃后无法确认提供商结果时不盲目重放付费调用。当前整次重试是新运行，不是续跑。

## 前端

分开展示研究计划、来源与证据、回答与局限；区分摘录/模型研究。显示简短补搜理由、停止原因和降级原因，不展示模型私有推理。失败仍可查看证据，历史展示当次快照。实时进度和取消按钮等后台事件/取消传播实现后再接。

## 本轮验证

新增 30 项离线场景：足够即停、一次补搜、共享预算、规划降级、空结果、重复查询、缺口完整性、假引用、响应截断/工具调用、认证/忙碌、超时与证据保留。包含合成提供商响应适配→完整会话链路，不是质量评测。

完整 Python 340 passed、1 skipped（真实联网测试未启用）。受限环境未能启动临时 HTTP 测试服务，改用允许本机端口的环境后执行；修正共享超时默认值兼容性后全量通过。

未调用真实模型/外部搜索，未运行本轮 Java/MySQL/React 测试（这些接口与代码未修改），未启动日常服务、安装依赖、升级数据库或执行 Git。真实模型和新版本 HTTP 联调仍待实施。
