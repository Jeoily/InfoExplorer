# 通用网页研究设计

2026-10-19 最新：Java/React 与日常 MySQL V6 已接入无模型网页摘录，覆盖下方较早“尚未切换”描述。后续模型闭环参照 [厂商公开策略](../research/RESEARCH_AGENT_STRATEGIES_20261019.md)：证据驱动调整方向、显式停止原因、程序硬预算。首版补搜一轮为上限而非必须步骤；模型接入尚未实现。

2026-10-19 实施更新：受限下载提取、真实 SearXNG、稳定证据编号与审核快照已实现；Python 默认关闭的 v2 HTTP 已通过真实公开搜索/正文提取。当前 HTTP 仅直接检索/摘录，模型关闭；Java/持久化/React 尚未切换。具体 wire 契约及验收见 [WEB_RESEARCH_V2.md](../contracts/WEB_RESEARCH_V2.md)。下文“尚未实现”属于原始设计时点，最新完成状态以 CURRENT_STATE 为准。

日期：2026-10-15。状态：整体方案尚未接入；Python 离线基础、固定本机 SearXNG 适配器与本地 HTML 提取已部分实现，验证边界见 CURRENT_STATE.md。用户确认扩展信息来源，不建立问题集或做新旧结果对比；保留必要的接口、安全、迁移及功能测试。

当前 app/main.py 仍使用原 Wikipedia 实现。新增 app/web_research 不被运行接口导入；模型适配、安全网页下载、Java v2 契约/迁移与前端接入尚未完成。事件追踪另见 [EVENT_TRACKING.md](EVENT_TRACKING.md)，工程交付见 [DELIVERY.md](DELIVERY.md)。

## 1. 目标与当前差距

现有 Java 业务 API、任务状态、执行历史、MySQL、幂等和前端继续使用。现有 Python 仅查询 Wikipedia 开头摘录，三关键词、五证据和轮流取样是早期实现限制，不作为新架构的固定产品规则。

目标是：问题 → 研究计划 → 多网站候选来源 → 正文相关段落 → 缺口判断 → 有界补搜 → 有引用的报告。回答不要求在某一网页找到完整原句，但每项引用应能定位保存的证据；模型推断应明确标记。引用存在校验不等于事实核验。

本轮不实现定时事件监控、全网爬虫、自建搜索索引、登录、公开部署、向量数据库或多实例执行。网页研究为未来事件追踪提供来源与时间数据，但不把一次检索称为事件追踪。

## 2. 数据源与接入决策

模型与搜索服务独立配置。Agnes 用于规划/报告，不假定它的聊天接口自带联网搜索。2026-10-15 根据用户要求改为开源自部署优先，不依赖付费 Search/Extract API。Python 使用固定配置的自建 SearXNG 地址；缺少搜索配置时显示配置错误，不悄悄切回百科后仍称网页搜索。

首版选型：SearXNG Search + 自有受控 HTTP 下载器 + Trafilatura 正文提取。SearXNG 聚合上游搜索服务，不维护自己的全网索引；自建实例需启用 JSON 格式。仅选择无需付费 Key 且本机可达的上游，逐个核验，不能承诺所有引擎可用。公共实例可能关闭 JSON，不作为默认依赖。结果摘要仅选网页，不冒充正文。Trafilatura 接收已经安全下载的 HTML，负责正文和元数据提取，不直接调用其便捷下载函数绕过网络安全策略。

Crawl4AI 为后续动态页面候选，首版不安装、不启用；浏览器渲染需要独立进程隔离、子资源网络限制和资源预算，不能视为提取失败后的无条件回退，也不绕过登录、验证码或付费墙。Wikipedia 保留为可选百科来源。Tavily 不再是实施前置条件，不要求注册或充值。

开源组件免去其商业 API 按次费用，不代表零成本：本机算力、带宽、维护及可选模型费用仍存在。限流、上游变更、中文覆盖和实际可达性必须验证。自行实现的是查询规划、候选筛选、去重、证据选择、覆盖判断、有界补搜与引用追踪，不从零重写浏览器或全网搜索引擎。

| 组件 | 输入 | 输出/责任 |
|---|---|---|
| SearchProvider | 查询、语言偏好、时间范围、域名策略 | 候选 URL、标题、摘要、排名、可用的发布时间、供应商请求标识 |
| ContentProvider | 经过校验的候选 URL、读取预算 | 正文文本、返回 URL、获取时间、失败原因、截断标记 |
| EvidenceSelector | 问题/子问题、候选正文段落 | 相关段落、排序依据、来源与查询关联 |
| CoverageReviewer | 子问题与已选证据 | covered/partial/missing、引用编号、缺口及补搜建议 |
| ReportGenerator | 原始问题、已选证据、覆盖说明 | 结论、引用、推断与限制 |

## 3. 完整执行流程

1. Java 验证并保存问题、researchMode（web/wikipedia）、输出语言、可选日期范围；这些字段全部参与幂等比较。后台领取任务，保存本次生效的供应商与预算配置快照，重试沿用任务范围。
2. Python 规划出待回答的子问题和搜索词。第一版关键词沿用选择的语言；后续跨语言扩展需显式展示，不隐式承诺支持。规划失败仍允许用原始问题向配置好的网页搜索源检索。
3. 搜索最多三个查询，每查询最多五个候选。不同子问题可以对应不同关键词，不能仅按同义词堆数量。新闻请求可使用日期筛选；供应商不支持某个过滤条件时明确返回能力限制，不能假装已经过滤。
4. 规范化 URL、去重，按查询相关性、可识别的第一手来源、子问题覆盖和时效需求选取正文读取对象。官方网站不等于任何内容都可信，多域名不等于独立来源；未知来源属性保留 unknown。
5. 从正文中按段落/小节获取候选证据，使用查询词匹配、标题匹配和中文字符 n-gram 的本地排序做第一版筛选。按子问题覆盖和域名多样性选择，允许调整，记录分数依据；不要把排序分数称为真实性或置信度。不再只截文章开头，也不按第一查询结果填满证据名额。
6. 模型开启时进行一次覆盖判断，响应必须引用实际存在的证据编号。缺口明确且还有预算时，最多补搜一轮、两个新查询；禁止重复查询，补搜仍经过相同 URL/内容检查。第一版不递归无限调用，也不引入多个自主 Agent。
7. 根据最终证据生成报告。模型关闭时返回结构化摘录和实际检索过程，不伪造问题理解或语义覆盖结论；模型报告失败时保留证据并说明“报告生成失败”，允许用户查看资料。
8. Java 保存完整执行摘要和证据；前端显示搜索范围、查询与轮次、读取成功/失败、来源及时间、回答与未解决问题。中间进度第一版可在完成时统一显示，不为此提前引入 WebSocket。

## 4. 内容与引用

候选结果的摘要仅用于选网页。正文获取失败时保留候选和错误，不把摘要冒充正文证据；报告应说明资料缺失。PDF、需要登录、验证码、付费墙、视频和动态页面若首个适配器不支持，标记 unsupported，不绕过限制。

保留 requestedUrl 与供应商返回的 resolvedUrl（仅当实际提供），不要编造最终跳转地址。URL 规范化去片段和明确的追踪参数，不随意删除可能标识不同文章的查询参数。规范化 URL 去重后再做正文 hash 去重；近似重复第一版仅标记疑似，不声称解决转载独立性。

只保存被用于回答的正文段落及必要来源元数据；不永久保存整站或完整 HTML。每条证据具备稳定 run 内编号、sourceId、段落位置（相对提取文本）、excerpt、hash。位置不是原网页 DOM 定位，hash 不是事实核验。

publishedAt（来源声称发布时间）、retrievedAt（本次获取时间）和时间来源必须分开。缺失发布日期为 null，不能用抓取日期代替。用于事件分析时，报道发布日期也不等于事件发生时间。

## 5. 数据与 API 设计

以下是计划字段，不是当前已支持接口。采用版本化的 Python 执行响应 schemaVersion=2；Java 明确识别新旧形状，不让新增来源字段被静默丢弃。

- task：新增 research_mode；API 未提供时兼容旧请求 wikipedia，React 新版明确选择网页研究。语言、日期范围可继续扩展，旧任务和旧报告不重写。
- run：新增 outcome_json，保存 schemaVersion、阶段结果、覆盖情况、预算使用、终止原因、可用成果；现有 plan_json 保留用于旧报告。子问题使用稳定 ID，查询记录 round/query/language/provider/status/error。
- 新增 research_source：runId、sourceId、规范化/请求/返回 URL、标题、域名、发布时间及其来源、获取时间、contentKind、读取状态、截断标记、正文 hash。长度约束与全文存储上限在实现时与两端契约同步。
- 新增 research_query_source：查询与候选来源的多对多关系、原排名和选取/排除理由。重复来源可属于多个查询。
- evidence：新增可空 sourceId 和段落位置；旧数据保留原字段。新证据允许 E1–E8，须同步修改 Java E1–E5 校验、Python prompt、前端和测试；正文按统一 UTF-16 长度预算验证，避免两端 Unicode 计数差异。
- 报告 generation 与 planning generation、coverage generation 分开记录；inputHash 仅用于诊断，不承诺重现模型输出。

第一版保留现有 PENDING/RUNNING/SUCCEEDED/FAILED 四个任务状态。另增 outcome.coverage=unknown/partial/sufficient 和 completionReason，区分流程完成与资料充分。零结果但搜索成功可为 SUCCEEDED/partial；全部搜索服务失败、总时限耗尽为 FAILED，但保留已完成阶段和可用证据。报告模型失败时 FAILED 并允许展示已取得资料；前端不能因为 status=FAILED 就隐藏证据。

新增只读 run 详情用于查看旧执行的计划与失败过程，现有 runs 摘要接口不扩大。Python 对预期执行错误返回结构化执行结果（带 outcome/error），Java 再决定成功或失败并事务保存；HTTP 非成功用于协议/认证/不可解析等传输错误。Java–Python 断连或 Python 崩溃时可能拿不到中间过程：记录 EXECUTION_INTERRUPTED/AGENT_TIMEOUT，不能声称部分成果全部可恢复。

新增迁移预计 H2 V8/MySQL V6，以实施时实际序列为准。旧迁移不改，不清库，不自动移动 H2 数据。计划、来源、证据和任务状态仍由 Java 统一事务写入。

## 6. 首版预算与超时（设计默认值，可配置）

| 项目 | 上限 |
|---|---:|
| 初始查询 | 3 |
| 补搜轮数 / 新查询 | 1 / 2 |
| 单查询候选 | 5 |
| 整次任务正文读取 URL | 8，包含补搜，不在轮次间重置 |
| 首轮正文名额 | 最多 6，保留 2 给补搜 |
| 最终证据 | 8，最多每来源 2 段 |
| 单页提取文本 | 30000 UTF-16 单元，超出标记截断 |
| 单证据 / 模型总证据文本 | 1600 / 12800 UTF-16 单元 |
| 模型调用 | 最多 3：规划、覆盖判断、报告；补搜不额外生成新计划 |
| 并发外部请求 | 2 |
| 单供应商 HTTP / 端到端执行 | 20 秒 / 150 秒 |

预算在执行层强制，模型不能修改。记录搜索请求数、正文下载数、字节数、耗时和模型 usage（缺失为 unknown），不能把请求次数当作账单金额。首版不开通商业搜索/提取 API。失败不自动重复请求；用户人工重试是新的执行预算，页面提示。

150 秒为拟实施的墙钟总预算：所有子请求使用剩余时间，截止后取消并关闭连接，避免后台继续调用。供应商已接收的请求不保证可以撤回或免计费。Java 研究等待建议 165 秒、优雅停机 175 秒；必须随实现测试取消路径，不能只把超时数值调大。

## 7. 外部网页边界

2026-10-19 实施更新：content.py 已将受限下载与本地提取组合，统一剩余时间和固定失败码；Document/SourceAttempt 元数据在内存中保留真实跳转地址、读取时间、提取器、未核验日期、截断和 paragraph-json-v1 提取文本 hash。离线及单个公开页面验证通过，尚未接运行 API/数据库；以下下载提取组合草案已有对应模块，但稳定编号和持久化仍待实现。

搜索仅访问配置好的自建 SearXNG；其本机地址是专用搜索连接的例外，不能用于放宽正文下载策略。正文下载只接受本次搜索发现的公开候选，拒绝凭据 URL、localhost、内网/链路本地/保留 IP、非 HTTP(S) 协议及非标准端口。模型不能任意指定网络目标。禁用环境代理自动继承，不携带本机 cookie、凭据或浏览器用户数据。

直接下载使网络安全成为首版前置要求：检查全部 DNS 结果，连接固定到已验证的公共 IP 并保持 TLS 主机名校验；逐跳重复校验，最多 3 次跳转，防止 DNS 重绑定。独立 download.py 已实现这些边界及最多 2 MiB HTML 读取，暂时只接受 identity 编码，不做解压；拒绝不支持的媒体类型。不执行网页脚本，不下载附件，不自动遍历链接。robots 同样经过受控下载并计入时间/次数预算，但当前是保守子集，非完整 RFC 9309 实现；复杂规则会拒绝访问，具体见模块 README。

2026-10-15 下载器离线 36 项测试通过，并成功读取一次 Python 官方公开 HTML（包括 robots 共 2 次请求）。父进程截止覆盖启动/DNS/TLS，回收存在额外耗时；仅进程内串行与固定间隔，尚无跨进程按域限流、OS 内存隔离和与业务取消信号的完整连接。未接 ContentTool 或运行 API，不能将单页成功称为通用抓取或 SSRF 完整审计通过。

网页、摘要和模型结果均为不可信数据；页面使用文本渲染，外链检查，模型不能执行来源中的指令、访问文件或调用数据库。HTML/Markdown 清理与正文提取不等于提示词注入完全免疫。

## 8. 前端变化

创建页展示“网页研究 / 百科检索”，输出语言、可选日期范围；清楚区分模型规划是否启用。来源配置属于本机配置，不要求普通使用者填写供应商名或 API 地址。

详情页分为回答、证据来源、检索过程三部分。证据展示站点、标题、摘录、发布时间（未知则明示）、获取时间、原文链接；检索过程显示初次/补充查询、失败与排除原因。证据不足、全部失败、预算停止、模型失败分别展示。旧报告正常显示，不补造新字段。

## 9. 实施顺序与完成标准

1. **网页检索基本链路**：先核验 Windows 上可用的部署环境与 SearXNG 上游可达性；实现 SearchProvider/SearXNG 适配器、受控下载器与 Trafilatura 适配器，区分候选摘要和正文，再接相关段落筛选、Java 契约与持久化、来源展示。先不启用补搜；离线测试不依赖运行中的搜索引擎。通过公开页面真实联调才能称接入完成。
2. **覆盖与一次补搜**：加入子问题覆盖、预算计数、补搜理由、终止原因和失败成果展示；覆盖判断是模型判断，不称作事实核验。
3. **事件追踪另案**：主题、轮次、内容变化和调度方案已写入 EVENT_TRACKING.md；待网页研究真实链路通过后实施，不提前启用调度。

不建立固定问题评测集、不做新旧质量对照实验。必要测试包括：契约校验、中文与 Unicode、摘要/正文区分、空结果、429/超时、恶意 URL、重复来源、引用映射、预算和取消、部分失败持久化、迁移兼容、刷新不重复执行。少量公开资料真实联调仅证明功能路径，不宣称准确率提升。

实施会修改 Python 检索/模型流程、Java 契约/存储/迁移和 React 展示；保留现有任务管理。开始涉及 Java 编译/迁移前通知用户停止 Java，日常库升级前重新备份；当前设计阶段服务无需停止。

## 10. 部署前置检查（环境已检查，SearXNG 尚未部署）

本轮环境检查未找到 docker 命令，wsl --status 返回退出码 50 及未安装提示；没有安装系统组件或启动容器。后续确定受支持运行环境，再部署只绑定本机的 SearXNG，固定版本并核对依赖及许可证，启用 JSON、选定上游和限流。真实搜索覆盖仍未验证。仅 Trafilatura 可选依赖已安装在工程 .web-deps 隔离目录并用本地 HTML 测试，未改变现有 .venv。无需申请 Tavily Key。模型密钥与计费约束保持原样。

## 11. 下一次跨服务接入的契约约束（尚未实现）

不把当前 Python 内部 dataclass 直接当成业务 HTTP 契约。新增 schemaVersion=2 响应应包含 executionId、status、completionReason、coverage、plan、queries、sources、evidence、answer、generation、usage；由显式序列化与 Java 校验共同约束。

| 对象 | 约束 |
|---|---|
| executionId | Java 创建的 runId，Python 原样返回；不接受上游生成替代 ID |
| status | SUCCEEDED/FAILED；不得返回未结束的 PENDING/RUNNING 作为终态响应 |
| completionReason | 固定枚举；包含完成、无可用证据、预算/时间截止、搜索/读取/模型失败；不传异常堆栈 |
| coverage | unknown/partial/sufficient，sufficient 仅表示一次明确的覆盖判断；不是事实认证 |
| plan | 最多 8 子问题，稳定 ID；保留直接/模型规划方式与失败降级原因 |
| queries | 最多 5，独立 queryId、round=0/1、查询原文、language、状态、sourceIds；同一来源可对应多查询 |
| sources | 最多 25 个去重候选，稳定 sourceId、requested/resolved/canonical URL、标题、读状态、日期来源、截断标记；正文不整篇持久化 |
| evidence | 最多 8 段，每源最多 2 段；id、sourceId、规范化段落位置、摘录、UTF-8 hash；总摘录最多 12800 UTF-16 单元 |
| answer | 可空；报告失败但 evidence 非空合法；非空最多 16000 UTF-16 单元 |
| generation | 分开记录 planning/coverage/report 的模型、提示词版本、输入 hash；未调用为 null，不能补造 |
| usage | 搜索/读取/模型尝试数、总耗时与实际取得的 token 使用量；未知 usage 为 null，不把次数当金额 |

Java 接收前先限制成功/错误响应总字节数（首版建议 512 KiB/2 KiB），再反序列化；source/证据的引用完整性、hash、唯一性与长度校验通过后，在一个事务内保存终态与已有成果。未知枚举、执行 ID 不匹配、引用越界和超长内容拒绝，不部分保存不可信响应。

来源状态至少区分 DISCOVERED、READ、FAILED、SKIPPED；最终结果不应仍显示某来源“读取中”。未读原因区分预算、重复、策略拒绝。当前内部 pipeline 输出的 SKIPPED/READ_LIMIT 是基础行为，不是既有 Java 接口的已支持字段。

补搜可能改变最终 E1–E8 分配。覆盖审核记录必须绑定审核时的证据快照（sourceId + paragraph position + hash），不能将旧 E1 的判断直接映射到补搜后新的 E1。前端显示审核发生在哪一轮；未二次审核保持 partial。当前内部协调器仅记录 review_applied，不持久化完整审核快照，接入前必须补齐。

接入设计进一步明确：内部 evidenceKey 使用 runId + sourceId + 段落位置 + 摘录 hash 标识，显示用 E 编号在执行内首次分配后不重新绑定。补搜筛选可以移除展示项，但不能把旧 E1 改指另一段；下一段使用新编号，界面允许编号不连续。最多保留 8 段是集合数量限制，不要求编号最大值为 8；仍需限制单次分配总量。报告只能引用最终保留集合，审核快照仍指向当时的 evidenceKey。跨 run 永远用复合身份，不能只凭 E1 查询。当前 selection/pipeline 尚未采用这一稳定编号方案，实施时必须同时更新审核、报告校验与 Java 契约测试。

下载与提取组合的下一批验收：同一 deadline 先分给下载，再将实际剩余时间交给提取；没有剩余时间不启动解析进程。DownloadError/ExtractionError 映射到固定 ToolFailure，不让新增错误码变成未捕获异常。保存 requested/resolved URL、retrievedAt、extractorVersion、truncated、日期原文及来源类型；HTML canonical 或网页中的 URL 不得替换真实连接身份。下载失败和提取空正文区分；不把搜索摘要降级伪装成已读取正文。当前 Document 不含这些完整元数据，需先扩展内部模型，再接 v2 持久化。

对于 FAILED + 有证据，Java 不应依赖 answer 非空才构造 result；新的 outcome 与报告文本解耦。前端按 result 中实际内容展示，不因任务失败隐藏证据。旧 v1 记录按原规则读取，不补造新字段。

先在隔离 H2/模拟 Python 上测试 v1/v2 兼容与错误契约，再用随机临时 MySQL 库验证迁移与事务；日常库升级仍需停止 Java 和备份。当前没有新增任何迁移文件。

## 官方依据（2026-10-15 查阅）

- [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)：搜索结果、正文选项及过滤参数；供应商能力不等同于本项目已实现。
- [Tavily Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract)：URL 正文提取；实际失败率、中文覆盖和额度尚未实测。
- [SearXNG Search API](https://docs.searxng.org/dev/search_api.html)：自建聚合检索的替代接口。
- [Trafilatura](https://trafilatura.readthedocs.io/en/latest/)：本地 HTML 正文与元数据提取。
- [Crawl4AI](https://docs.crawl4ai.com/)：后续浏览器渲染候选，尚未接入。
- [GPT Researcher 来源获取实现](https://github.com/assafelovic/gpt-researcher/blob/main/gpt_researcher/skills/researcher.py)：区分已有正文和需抓取的 URL。
- [Open Deep Research](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/deep_researcher.py)：有界研究迭代的参考，不照搬其全部框架。
