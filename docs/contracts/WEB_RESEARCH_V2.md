# 网页研究 v2：Python 接口实现与 Java 接入约定

2026-10-19。Python HTTP 已实现并真实验证；Java、数据库与 React 尚未接入。JSON Schema 同目录，来自 app/web_research/api.py。旧 /internal/v1/research/run 不变。

## 请求与启用

POST /internal/v2/research/run，Content-Type: application/json。

```json
{"runId":"12345678-1234-1234-1234-123456789abc","question":"Python http.client documentation","language":"en"}
```

- runId 必填 UUID，由调用方生成；将来使用 Java 已创建的 research_run.id。接口归一化为小写 UUID，结果必须匹配调用方身份。它不是幂等缓存：重复请求仍会重新搜索，调用方不能自动重试。
- question 为非空字符串，规范化空白后最多 4000 UTF-16 单位；language 只接受 en/zh，省略为 en。额外字段拒绝；不允许请求指定 URL、搜索服务、模型、工具或预算。
- 默认关闭；仅 INFOEXPLORER_WEB_ENABLED=true 开放。固定 SearXNG 地址 http://127.0.0.1:8888。Start-WebResearch.ps1 使用项目 .venv/.web-deps、单 worker、仅 127.0.0.1:8000，并强制关闭模型与旧规划。
- 此版 mode=web-extract、planMode=direct，把原问题作为一次检索词；没有模型规划、覆盖判断或模型报告，也不会因为已有模型环境变量而调用模型。
- 进程内只接收一个正在执行的网页请求，不排队；不是跨进程限流，也不支持多实例。HTTP 断开尚不会取消底层工作。

## 返回与状态

HTTP 200 代表执行结果已形成，必须继续检查 outcome.status，不代表研究成功。

- schemaVersion 固定 web-research-v2；questions 保存 Q1 与归一化后的问题。
- outcome 包含 runId、status、completionReason、coverage、answer、evidence、queries、sources、usage、reviewApplied、reviewSnapshot。
- FAILED 可以带 evidence/sources，answer 可以为 null。Java 已按 outcome 保存已有成果，不能因为报告为空丢弃证据。
- 无可用资料可为 SUCCEEDED + NO_USABLE_EVIDENCE；不能标成已充分回答。无模型时 coverage 为 unknown；无证据为 partial。单个来源失败不会抹掉其他来源成功成果。
- queries 记录每次查询、轮次、返回来源 ID、错误和上游警告；sources 记录原始候选及最终 READ/FAILED/SKIPPED 状态。snippet 仅搜索摘要，不能当正文证据。
- 来源 metadata 保存 requested/resolved URL、读取时间、提取器、截断、未核验日期与提取文本 hash；没有元数据时为 null，不补造。正文 hash 算法为 paragraph-json-v1。
- usage 是尝试次数及剩余期限，不是实际账单。此 HTTP 版本 modelCalls=0。
- 输出序列化上限 512 KiB；Java 已在反序列化前限制响应流大小，不能仅在解析后检查。

入口拒绝为 400 INVALID_REQUEST（沿用现有全局错误结构）、503 {detail:{code:WEB_DISABLED}}、429 {detail:{code:WEB_BUSY}}；输出超限 502 {detail:{code:WEB_RESPONSE_TOO_LARGE}}。未预期内部异常为通用 500，不向客户端回传原始异常。

## 稳定引用与审核快照

- evidenceKey = SHA256(UTF-8 紧凑 JSON 数组 [runId, sourceId, paragraphIndex, offsetUtf16, contentHash])。
- 每个执行内首次选中时分配 E1、E2……，之后排序、移除和再次选入不改绑定。最多分配 16 个身份（两轮各最多 8 个）；最终集合最多 8 段，允许显示编号不连续。
- 原始选择器的临时编号不能对外使用；执行器通过 EvidenceRegistry 重新绑定稳定身份。不同 run 的相同摘录 evidenceKey 不同。
- reviewSnapshot 在有效审核后记录该轮完整证据快照及覆盖判断；补搜后不覆盖快照，不把此前审核套到新集合。无审核或审核无效时为 null。
- 报告只能引用最终集合；曾存在于审核快照、现已被移除的编号也会拒绝。引用存在不等于真实性核验。
- Python 独立执行器仍支持注入审核/报告工具以离线测试补搜，HTTP 当前不启用它们。未来真实模型接入需单独元数据与契约版本演进，不能将测试夹具称为真实模型。

## Python 接口阶段验证（历史）

- 全 Python 离线测试 310 passed、1 skipped（真实 Wikipedia 测试未启用）。含真实本机 HTTP、默认禁用、无效输入、工具覆盖拒绝、并发拒绝、异常释放锁、失败保留证据、补搜排序变化稳定编号和审核快照、过期引用拒绝。
- scripts/check_web_api.py --live 启动并关闭临时本机 Uvicorn。公开关键词 Python http.client documentation 经真实 HTTP → SearXNG → 受限下载 → Trafilatura，返回 SUCCEEDED/COMPLETED、coverage=unknown、3 个已读来源、6 段证据、11921 字节响应；搜索 1 次、读取尝试 5 次、模型 0 次。
- 两个来源 CONTENT_ROBOTS_UNSUPPORTED，保留 SEARCH_ENGINES_PARTIALLY_UNAVAILABLE 警告；没有放宽 robots/网络安全策略。
- 尚未运行 Java/MySQL/React 联调、没有新增数据库迁移或改变日常库。本结果不是前端已经切换。

## Java/前端验收标准（本轮已落实）

1. 显式 researchMode 与旧任务兼容，幂等键包含模式，重试沿用原模式。
2. 按运行身份、来源与证据关联、hash、边界和枚举校验 v2，限制读取字节数；研究超时覆盖 150 秒预算及回收余量。
3. 事务保存终态与部分成果，单独处理持久化失败；旧迁移不修改。先隔离 H2，再随机临时 MySQL，最后用户备份后升级日常库。
4. 前端显示真实资料范围、局部失败、检索词、正文来源和摘录；模型未运行不展示为模型报告或已覆盖问题。失败结果仍可阅读证据。

## Java/React 接入与当前状态（2026-10-19）

创建任务增加 researchMode（wikipedia/web，默认前者），旧任务不变。响应新增 researchMode/webResult，网页结果不复用旧 result 对象。GET /api/v1/research-tasks/{id}/runs/{runId}/web-result 返回该运行快照；404 可能表示任务/运行不存在或该次未产生快照。

Java 当前严格接受 direct/web-extract 子集：最多一个查询、五个来源/读取尝试、八段最终证据、模型调用为零、无审核快照。扩展模型/补搜时必须同步更新双端验证，而非悄悄放宽当前接口。成功流限制 512 KiB、错误流 2 KiB，175 秒超时。

H2 V8/MySQL V6 新迁移完成，旧迁移未修改；真实 MySQL 随机临时库 9 项通过，日常库已备份升级。真实 Java/Python/SearXNG/正文/临时 H2/重启与幂等链路通过；React 浏览器 8 项通过（离线来源）。详见 CURRENT_STATE。本节覆盖上方历史阶段“未接入”的描述。


## 2026-10-22 正文提取实现版本

`extractor=trafilatura-2.3.1-context-v2` 使用 XML 段落、标题及定义列表整理有界证据块，避免软换行拆散含义。标题/定义上下文来自原始提取文本，不是模型生成的摘要；paragraphIndex 指整理后的块，offsetUtf16 相对于该块。extractedTextHash 仍是保留块数组的 JSON 哈希（paragraph-json-v1），不是原始 HTML 或未截断全文哈希。提取器变更时追踪标 EXTRACTOR_CHANGED，不冒充网站更新。旧快照继续可读。
