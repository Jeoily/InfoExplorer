# 后端设计

## 2026-10-25 单实例长任务执行控制

已实现 [执行控制 v1](../contracts/EXECUTION_CONTROL_V1.md)。Java 继续负责排队、权威状态与证据持久化；新增 H2 V11/MySQL V9 执行控制表。取消请求与结果提交锁定同一任务行，旧 runId 不作用于后续执行。单线程 worker 发生存储异常后，数据库恢复时先处理遗留执行，再领取新任务。启动恢复只适用于单实例。

Python 新增本机持久化执行身份及原始公开检索资料缓存，不授予模型文件或数据库工具。相同执行编号返回已保存响应或拒绝再次执行；手动重试以新编号进行，最多复用一小时内同输入资料，不缓存/重放模型阶段。控制库与原有诊断回放目录分离，后一项仍不是可恢复检查点。

前端轮询具体阶段、显示取消等待、刷新查询数据库状态；未确认的新建提交在标签页内保存幂等键。取消是阶段边界协作式停止，当前供应商请求可能继续至超时且仍可能计费；不宣称强制撤销远端调用。Java 网络超时尝试取消 Python，Python 保留 150 秒预算。验证范围与日常部署状态以 CURRENT_STATE 为准，历史下文“尚未取消”等描述已被本节取代。

## 2026-10-25 质量诊断中的固定证据生成

网页模型报告新增供应商专用原文编号：对各证据预先生成有界连续原文 quoteOptions，供应商只选 evidenceId/quoteId，应用解析后仍逐字检查原文。内部旧 quote 形式继续用于旧记录兼容，公开 Java/React 报告契约不增加字段。保存验证后的原文，避免编号随分段变更而重映射；此检查不证明结论语义正确。

隔离 debug_agent 额外支持显式 POST `/__debug/records/{runId}/report-generation`：仅 live 模式，读取当前会话的冻结报告输入，单次 completion；共享研究锁和预算，结果单独保存，不修改日常数据库/原记录。不由离线复查按钮调用，不注册日常 API。用户本轮已取消累计真实调用次数上限，但每任务请求及超时约束继续保留。实际质量进度见 docs/QUALITY_2026-10-25.md，尚未验收达标。

## 2026-10-25 阶段复查只读接口

debug_agent 专有 `/__debug/records/{runId}` 和 `/__debug/records/{runId}/review/{action}`，不注册于日常 Python/Java。只在当前管理会话按 UUID 查找记录；未知/重复/损坏明确失败，动作仅 session/select/report-check，不提供真实调用或数据库写入。输出浏览器投影移除模型 instructions，只保留公开阶段数据。原记录保持不变，Java 业务快照仍为任务与历史的事实来源。

隔离前端由 INFOEXPLORER_DEBUG_UI=true 启用显示与固定本机代理；日常构建默认关闭。没有认证隔离设计，不应开放公网；它是既有本机可信诊断边界的一部分。前端按需读取，完整记录/研究成功区分，历史记录按 runId 绑定，不误称实时进度。验收见 CURRENT_STATE。

## 2026-10-25 阶段记录和回放边界

Python 协调器增加可选观察器；默认业务路径不记录，Java 仍管理任务和证据持久化。隔离 debug_agent 注入记录包装，固定样例自动开启，真实模式显式 RecordPublic 开启。保存 typed 搜索/正文、选择输入输出、模型请求和通过校验的结构输出；不存鉴权或拒绝原文。阶段完成前先写开始事件，完成记录独立于研究成功状态。

记录采用会话下编号文件、原子替换、大小/数量限制及摘要检查，不是业务数据库或断点检查点。离线回放注入保存结果，严格匹配输入和顺序，不允许网络回退；重新选择可使用当前算法和冻结正文。固定证据生成复用当前请求构造和报告校验，只允许显式注入 completion，预算/授权由调用方负责。当前仅离线合成测试，无真实生成验收。详见 docs/RESEARCH_REPLAY.md；前端展示属于后续阶段。

## 2026-10-25 独立调试运行边界

新增 scripts/debug_env.py 及 Start/Control-Debug.ps1，不扩展旧日常部署 supervisor。固定调试端口 18000/18080/15173；每会话 H2，Java 从源码复制后独立离线构建，强制 classpath 配置及 H2 迁移，不接日常 MySQL。默认 debug_agent 固定样例仅暴露 v3，复用既有会话工具夹具，通过真实 Java/Python/前端代理与 H2 流程验证；不是模型质量验证。

管理请求只允许固定动作，文件目录是本机同用户可信控制面。状态经活管理进程回复，旧 PID/状态文件不作存活证明。只停止仍持有的自有进程，端口冲突拒绝接管。Windows kill-on-close Job Object 包含管理进程及其后代，关闭/崩溃清理进程树；正常控制先检查隔离库无活跃研究任务，紧急退出不保证优雅结束。无定时任务或自动开机启动。

环境采用允许列表；调试模型密钥仅本机隐藏输入、管理内存保存、给 Python 子进程，Java/构建/前端不接收。可选真实模式每次研究前预约本会话次数，失败占次数、重启不重置，沿用每研究最多 3 模型请求；不自动探测账单，真实启用仍须用户确认。默认固定样例无需任何密钥，真实供应商尚未在此入口验证。详见 docs/DEBUG_ENV.md。

## 2026-10-22 追踪与研究可靠性决定

新增 tracking 模块，详见 [追踪契约](../contracts/TRACKING_V1.md)。主题/配置版本/轮次独立于研究任务与执行重试，配置乐观锁及主题行锁保护排队；任务与轮次同事务。独立 trackingScheduler 处理定时排队与结果汇总，researchScheduler 串行执行外部研究，避免网络请求阻塞调度。单实例约束保留。H2 V10 / MySQL V8 为新增迁移，不改旧迁移、不搬迁 H2。

资料变化依据 resolved URL、提取正文哈希及提取器版本，保留本轮和先前摘录与研究执行链接；发现时间不是事件时间。空/失败轮次不替换有效基线，改名/暂停不重置相同问题、语言、模式的比较范围。模型研究仅手动，自动调度只允许 web 且至少一小时，默认关闭；合并错过时槽而不无限补跑。定时执行并不提供分布式锁或多实例安全。

模型边界仅额外容许完整单层 JSON 代码围栏，不从任意文本提取 JSON、不自动修补不合法内容；重复键、未知字段、引用一致性继续严格校验。传输与父进程共享剩余预算，进程启动也计入时间。结构化 Schema 同步给供应商，错误日志仅固定类别。实际验证与剩余外部阻碍见 CURRENT_STATE。


## 2026-10-19 模型研究接入业务链路

检索运维：当前 SearXNG 默认仅启用本机实测可用的 DuckDuckGo，暂禁用返回无关资料的 Bing 和限流的 Brave。HTTP 200 不能作为检索质量验收；上线调整至少核对公开查询的来源相关性及受限正文读取。单个来源可用不代表稳定冗余，不绕过验证码，不以扩充来源数量替代验证。

真实供应商联调发现模型阶段可能返回合法 JSON 但结构不符合契约。各阶段提示现携带与本机校验相同的 JSON Schema，说明必填字段、数组及枚举；不假设供应商支持结构化输出接口，不放宽本机校验，不自动修复或重试。可选诊断只记录固定阶段/错误类别，不保存模型原文；真实验证状态见 CURRENT_STATE。

新增独立 v3 HTTP、web-model 任务模式与 ModelSessionReport；详见 [v3 契约](../contracts/WEB_RESEARCH_V3.md)。Java 严格核对计划、审核证据快照、最终引用与报告文本，研究会话和终态事务保存。React 展示计划、缺口/补搜理由、停止原因、引用与历史，失败保留资料。新增 H2 V9/MySQL V7 迁移，MySQL 隔离测试已于 2026-10-19 17:02 通过 10/10，含 V6→V7 升级与会话重启读取；日常库升级仍须先备份。

网页模型开关与旧 Wiki 模型开关独立；v2/v3 共用进程内门控。模型不能选供应商地址或执行任意工具。HTTP 返回后保存整次运行快照，仍无实时阶段推送、逐阶段持久化、断点恢复或多实例支持。结构引用校验不代表语义支持性核验。外部模拟的真实 Java/Python HTTP 与页面联调已验证，真实供应商验证另行记录。

## 2026-10-19 研究闭环离线实现

详见 [RESEARCH_LOOP.md](RESEARCH_LOOP.md)。Python 新增研究会话和显式模型适配器，共享规划/审核/报告预算，验证计划、缺口及最终引用，失败保留证据。新增 30 项离线场景，全 Python 340 passed/1 skipped。Session 未接 HTTP/Java/React 或数据库，旧 v2 无模型契约不变；不能把离线夹具称为真实供应商验证。持久化会话、实时事件、取消和检查点恢复仍待后续。

## 2026-10-19 后续设计依据（未实现）

已查阅 Anthropic、OpenAI、Google 公开研究 Agent 资料，见 [厂商策略与本项目建议](../research/RESEARCH_AGENT_STRATEGIES_20261019.md)。下一阶段采用受预算约束的证据驱动研究闭环；“最多补搜一次”是首版上限，不是必须执行的固定步骤。先实现单 Agent 的规划/缺口判断/报告职责，再按独立研究方向考虑并行子任务。阶段追踪、检查点和引用支持性检查分别设计，不能把当前整次重试称为断点恢复。此段不代表模型网页研究已上线。

## 2026-10-19 当前实现：网页任务与运行快照

以本节和 CURRENT_STATE 为最新状态，后文的“尚未接入”属于历史阶段记录。

- 创建请求新增 researchMode=wikipedia|web（默认 wikipedia），数据库迁移 H2 V8/MySQL V6。旧任务不改模式，幂等键重放比较模式，重试不切换数据源。
- Java 分流到 Python v1 或 v2。v1 保持原请求结构。v2 先限制响应流大小，再严格解析与校验运行 ID、来源关系、内容 hash、证据身份、枚举、预算及引用。总等待 175 秒，关闭等待 185 秒，无自动重发。
- 每次运行的 v2 结果以有界完整 JSON 快照和任务终态在同一事务提交。采用快照是为了原样保存失败成果和来源元数据，避免本轮扩张大量业务表；代价是不能直接高效 SQL 分析单条证据，事件追踪阶段需单独设计规范化表/索引。成功正文与已读来源投影写原有列，保留旧状态约束；web 的旧 result 字段为 null，使用 webResult。失败时原 answer/sources 仍为 null，已取得资料保留在快照。
- GET /api/v1/research-tasks/{id}/runs/{runId}/web-result 按两者限定；没有快照返回 404。保存失败不重新执行外部请求；尝试标记 RESULT_PERSISTENCE_FAILED，若数据库仍不可用则保留运行态，由现有启动恢复处理。当前不具备事务消息/跨进程恰好一次保证。
- React 支持模式、引用定位、来源/检索警告及历史快照，当前为摘录，未调用模型，不声称覆盖充分。默认 Wikipedia 保持旧行为，新增网页模式必须显式选择。Java 原生页面仍仅完整展示旧模式，应使用 React 查看网页结果。
- 本轮通过隔离 H2、真实 MySQL 临时库、Java/Python HTTP 和浏览器验证；真实公开搜索 2 个来源/4 段证据，模型 0。日常 MySQL 已由用户备份并从 V5 升 V6。仍仅本机单实例，不引入登录/调度/事件追踪。


日期：2026-10-14。以下明确区分当前实现和后续方向。

运行验证更新（2026-10-15）：日常 MySQL infoexplorer 已在本机备份后由 V1 升至 V3，React → Java → Python → Wikipedia → 日常 MySQL 真实检索通过，模型关闭。新增 Backup-And-Start-MySql.ps1 作为本机交互入口：root 仅用于数据库导出，应用继续使用 infoexplorer_app；导出失败阻止启动，不自动恢复/修复。备份已验证文件与哈希，未验证恢复；详细证据和边界见 CURRENT_STATE.md。

正式前端见 [FRONTEND.md](FRONTEND.md)：React/TypeScript/Vite 已在独立 frontend 目录实现，复用 Java 业务 API；Node.js 仅承担前端工具链，浏览器不直连数据库、Python 或模型。原生页面未替换，Java/Python 接口及数据库迁移未改。Vite 仅本机代理，无后端 CORS 放宽；hash 路由支持刷新。构建预览实现每响应随机样式 nonce 与同源脚本 CSP，并验证 Ant Design 动态样式兼容；仅样式属性允许 unsafe-inline。此策略尚未移植到 Java，不能直接把构建文件覆盖到原 static 下。公网部署未实现。

## 下一阶段设计：通用网页研究

2026-10-19 v2 更新：Python 新增默认关闭的 /internal/v2/research/run，固定本机搜索且仅直接检索/摘录，不调用模型；稳定 E 编号/evidenceKey 与审核证据快照已落地。真实 HTTP 搜索提取通过，失败证据在结果对象中保留。请求/响应 Schema、状态规则和 Java 后续验收见 [WEB_RESEARCH_V2.md](../contracts/WEB_RESEARCH_V2.md)。Java/数据库/React 尚未接入，不修改旧接口语义；后续必须处理模式幂等、512 KiB 读取前限制和失败成果事务。

2026-10-19 部署更新：SearXNG 独立容器已绑定 127.0.0.1:8888，配置及固定镜像摘要见 infra/searxng。Docker 数据实际在 E 盘。真实中英文公开搜索已通过；Bing/DuckDuckGo 返回结果，Brave 限流；实际搜索返回的官方文档已通过受限下载与 Trafilatura。一次宽泛查询正文超时保留为失败记录。暂不启用公网、Valkey 或自动启动，不将搜索可用等同覆盖质量。Java/React 仍使用 Wikipedia，v2 契约与持久化未实现。

2026-10-19 更新：独立 content.py 已组合受限下载与 Trafilatura，共享截止并保留来源元数据，离线测试和单个公开页面真实下载提取验证通过。Java/React 运行入口和数据库未改变，尚未接入业务接口；以下“组合未完成”为此前历史状态。稳定证据身份、审核快照、真实 SearXNG 和 v2 持久化仍待完成。

2026-10-15 用户确认扩大信息来源并优先开源自部署。具体设计见 [WEB_RESEARCH.md](WEB_RESEARCH.md)：SearXNG 搜索、受控 HTTP 下载与 Trafilatura 本地正文提取，随后实现相关段落筛选、失败证据保留和一次有界补搜；Crawl4AI 动态页面作为后续候选。取消 Tavily 注册/付费 API 前置要求。Python 独立基础模块已编码并做离线测试，保守下载器已独立通过边界测试和单个公开网页验证；SearXNG 真部署/上游可达性、下载提取组合、真实模型适配、Java 新契约与迁移仍未完成。以下 Wikipedia 实现保持运行入口，不建立问题集对比结果。

2026-10-15 开源代码调研后的取舍：保留 Java 业务状态与事务、Python 研究工具、React 展示的分工；优先稳定证据编号、阶段事件和执行配置快照，后续先手动追踪再调度。暂不迁移整个 Agent 框架，不授予模型机器工具权限。依据与逐项目比较见 [开源工程调研](../research/OPEN_SOURCE_REVIEW_20261015.md)。这些取舍是设计，不代表事件流或追踪已经实现。

整体产品范围见 [PROJECT.md](../PROJECT.md)，追踪主题/轮次/事件修订见 [EVENT_TRACKING.md](EVENT_TRACKING.md)，可靠性与部署设计见 [DELIVERY.md](DELIVERY.md)。本轮静态审阅识别了结果保存失败后任务可能停留 RUNNING 的路径，以及成功响应在反序列化前缺少总字节限制的问题；尚未修改 Java 或进行故障复现，后续与 v2 接入一并验证。

## 按任务选择 Wikipedia 语言（2026-10-15）

验证更新：日常 MySQL 已备份并成功升级 V4；中文与英文公开关键词通过 Java/Python/真实 Wikipedia/日常 MySQL 联调，各保存 5 条证据，模型关闭。备份未做恢复演练，详情见 CURRENT_STATE.md。

POST /api/v1/research-tasks 与 Python /internal/v1/research/run 接收 language，仅 en/zh；省略或 null 默认 en 兼容旧客户端，其他值返回 400。页面默认 zh。Java 保存 research_task.search_language，在详情返回 language；列表概要保持原接口。幂等键绑定问题和语言，换语言复用键返回 409；失败重试沿用已存语言。Python 每请求构造固定 en.wikipedia.org/zh.wikipedia.org 检索器，不共享可变语言配置，不再使用 SEARCH_WIKIPEDIA_LANGUAGE。

H2 V6 / MySQL V4 添加非空字段与 CHECK；存在 wikipedia-zh 历史执行的任务设 zh，其余 en。历史报告、证据不改写；不猜测旧问题的语言。空证据仍是流程 SUCCEEDED，界面明确无结果并允许更换主题或语言重新创建，不能把状态成功当成检索质量成功。此阶段不增加自动翻译、查询规划或其他搜索源。普通测试均离线；实际迁移和外部联调状态以 CURRENT_STATE 为准。

## 有界检索规划（2026-10-15，本轮新增）

验证更新：日常库已备份升级 MySQL V5，真实 Agnes search-plan-v1 规划、三次中文 Wikipedia 查询、evidence-report-v2 报告及日常库保存链路通过一次公开问题验证；刷新后数据一致。该例资料未充分覆盖用户问题，报告明确说明局限；尚未做规划效果评测。具体任务与验证边界见 CURRENT_STATE。

Python 在检索前增加可选 QueryPlanner。INFOEXPLORER_PLANNING_ENABLED 默认 false；启用还要求 INFOEXPLORER_MODEL_ENABLED=true 及既有供应商配置。规划只发送原始问题与选择的语言，不发送凭据之外的本机信息，不授予工具权限。供应商传输沿用固定 HTTPS host 校验、禁止跳转、无自动重试、响应大小限制、单请求进程期限和模型互斥锁。

规划响应严格限定 intent 和 queries；1–3 个不同关键词、每个最多 100 Unicode 字符，意图最多 300；拒绝多余字段、网址、控制字符、HTML 标记、工具调用和截断输出。语言由服务固定为用户选择，不允许模型改写请求地址或切换站点。本轮不做跨语言扩展、新闻搜索、多轮自主规划或工具执行。

规划关闭、模型关闭、配置不合法、请求失败或计划不合格时，记录机器可读原因并退回原始问题。启用规划但规划失败时，不再尝试模型报告，确保直接检索降级可用；规划关闭仍兼容既有可选模型报告。一次成功规划最多增加一次模型请求；若还有证据和模型报告配置，整次执行最多两次供应商调用，不自动重试。新增 Start-Model.ps1 -EnablePlanning 是显式启动入口，真实使用前核对当前供应商/模型/计费。

查询按顺序执行，最多三次，每次 Wikipedia 最多五条。记录每个查询的状态、可用资料数、错误码及最终 evidenceIds。按排名轮流从各查询选资料，按 URL 去重，总共最多五条；重复 URL 采用首次选中的摘录，其他查询保留指向该证据的关联，未保留的候选正文不落库。部分查询失败但至少一次正常响应仍可返回报告；全查询失败保留现有任务 FAILED 行为，此时详细计划不落库（仅安全错误码）。报告生成失败同样不保存中间计划，这是本轮边界。

ResearchReport 新增可空 plan；旧记录和旧 Agent 兼容 null。Java 再校验模式、语言、数量、状态、引用、规划元数据后，在同一事务保存报告、证据和 research_run.plan_json。H2 V7 / MySQL V5 新增列，旧迁移不改。每次人工重试重新规划，不能保证关键词相同；历史 run 保留计划 JSON，但现有历史 API 只返回状态摘要，不提供逐次历史报告界面。

React 与原生页面在结果返回后展示计划、降级提示及查询结果；尚不实时展示中间阶段。Java 研究读取超时默认由 60 秒调至 120 秒，优雅停机等待 130 秒，以容纳最多三次检索和两次模型调用。搜索仍使用现有 socket 超时，不宣称全流程硬期限或严格任务取消。普通测试不访问供应商，真实验证状态见 CURRENT_STATE。

## 服务边界

Java 管理对外 API、业务任务、执行记录、证据及上游错误转换。Python 提供 Wikipedia 检索和可选模型报告；模型默认关闭，Java 后台任务到 Agnes 中国站的真实调用、临时文件库入库与重启查询均已验证。旧聊天路径保留回显。

保留同步链路：客户端 → ChatController → ChatService → AgentClient → Python。

新增任务链路：客户端 → ResearchController → ResearchService → 数据库；后台 ResearchWorker → ResearchExecutor → AgentClient → Python → 保存结果。HTTP 创建请求在入库提交后返回，不等待研究完成。

## 本机任务网页（2026-10-14）

Java static 提供原生 HTML/CSS/JavaScript，浏览器同源调用现有任务 API，不新增 Python 接口或数据库迁移。此阶段优先串联现有业务闭环，不引入额外构建依赖。页面支持创建、列表每页 10 条及状态筛选、详情、证据、执行历史、失败确认重试。后续界面复杂度增加时再评估组件框架。

每 5 秒顺序轮询列表和当前详情，隐藏标签暂停；请求版本控制避免迟到响应覆盖新的选择，内容未变化不重建 DOM。没有 SSE/WebSocket，也不宣称即时推送。创建幂等键仅保留在当前页面内存，刷新后不保证复用；网络错误后同页重发相同问题复用键。重试确认绑定失败 runId，由后端事务和版本校验最终仲裁，前端按钮禁用不能代替后端幂等。

所有外部文本用 textContent 展示，不解析 Markdown/HTML；证据链接只接受无凭据 HTTPS，另开页设置 noopener/noreferrer。BrowserSecurityFilter 设置同源 CSP、nosniff、no-referrer、no-store。仍无登录、用户隔离和公网部署防护，此页面仅为本机入口。

验证使用真实浏览器、Java API、隔离内存 H2 和本机模拟 Agent；覆盖业务交互、网络响应丢失后的创建去重、重试防重复、分页筛选、文本注入和移动布局。没有重复调用真实模型，也没有升级日常 MySQL；详情见 CURRENT_STATE.md。

## 数据库选择与迁移

### 新增 MySQL 8.4 适配

默认 H2 保留用于本机兼容和普通测试；mysql profile 显式切换独立 MySQL 数据库，实际执行状态见 CURRENT_STATE.md。新增 Boot BOM 管理的 mysql-connector-j 与 flyway-mysql，不修改 H2 已应用迁移。MySQL 使用单独 db/mysql/V1__research_schema.sql 建立与当前 H2 V3 对应的结构，不共用历史或自动搬迁旧数据。

MySQL 专用 DDL 使用 InnoDB、MEDIUMTEXT、显式 FOREIGN KEY 与 CHECK。表级 utf8mb4_0900_bin 为大小写敏感且 NO PAD，避免 MySQL 默认比较规则将不同幂等键视为同一个键。领取查询替换为两种数据库均支持的 LIMIT 1，仍以条件 UPDATE 仲裁竞争。参考：[MySQL 外键](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html)、[二进制排序规则](https://dev.mysql.com/doc/refman/8.4/en/charset-binary-collations.html)。

本机 MySQL profile 要求 TLS 加密，不校验身份；远程部署须独立设计证书验证和最小权限账户。Flyway clean 禁用。MySQL DDL 不具备与业务 DML 同等的事务回滚语义，迁移失败需检查部分建表，不能直接当作业务事务回滚处理。

数据库更换不改变当前单实例所有权约束：启动时仍恢复所有 RUNNING，不能同时运行两个 Java 实例；多实例部署需要租约/心跳设计。

MySqlIntegrationTests 默认跳过，由本机交互脚本传入凭据显式运行。测试只连接 127.0.0.1，随机生成测试库名，CREATE 成功后才允许按严格库名模式 DROP。不接受用户指定测试库、不执行 Flyway clean、不使用真实模型。

2026-10-14 14:55 三项真实 MySQL 8.4 测试通过：约束、Unicode、大小写幂等、并发幂等/领取、业务事务回滚、应用重开持久化及中断恢复。测试库清理无错误。15:08 用户运行 Start-MySql.ps1 后，本地日志确认 mysql profile 已连接日常开发库 infoexplorer 并完成 V1 迁移，随后健康接口实测返回 UP。15:34:41 MySqlLiveModelIntegrationTests 通过（1 test、0 failures/errors/skipped）：真实 Java/Python/Wikipedia/Agnes 链路将 5 条证据和 v2 报告写入随机 MySQL 测试库，幂等重放与应用重开后的 HTTP 查询一致，执行记录仅一条，清理无错误。未重启 MySQL 服务器、未做性能压测；H2 仍为未指定 profile 时的默认配置。

未指定 mysql profile 时使用 H2 文件模式 + Spring JDBC + Flyway，无需先安装数据库服务器；mysql profile 改用本机 MySQL。两者均使用明确的 SQL、事务、约束和迁移，版本由 Spring Boot BOM 管理。

这是本地单实例开发方案。未启用 H2 TCP 服务或网页控制台。迁移位于 backend/java-api/src/main/resources/db/migration。V1 创建：

| 表 | 主要内容 |
|---|---|
| research_task | UUID、问题、可选唯一幂等键、任务状态、创建/更新时间 |
| research_run | UUID、唯一关联任务、执行状态、开始/结束时间、回答、来源 JSON、错误码 |

初版每任务一次执行；新增 H2 V5 / MySQL V3 后改为每任务最多 5 次执行，(task_id,attempt_no) 唯一，详细规则见手动重试小节。时间存为 UTC epoch 毫秒，API 返回 ISO-8601 时间。V2 新增结构化证据，详见下文。网络请求不持有数据库事务。

生产数据库可在后续选择 MySQL/PostgreSQL，但迁移 SQL、锁行为及驱动必须单独适配和验证，不能认为替换连接地址即可完成迁移。

## API 契约

请求问题统一使用 JSON 对象：`{"question":"..."}`。必须为非空白字符串，最多 4000 个 UTF-16 代码单元；保留原始空格，不隐式将数字转换成字符串。

| API | 行为 |
|---|---|
| POST /api/v1/chat/ask | 保留原同步接口；返回 answer、sources，不保存任务 |
| POST /internal/v1/agent/run | Python 内部模拟执行接口 |
| POST /internal/v1/research/run | Python 内部真实检索与摘录接口 |
| POST /api/v1/research-tasks | 提交后返回 202、任务快照和 Location |
| GET /api/v1/research-tasks | 概要分页列表，支持 page、size、status；非法查询返回 400 / INVALID_QUERY |
| GET /api/v1/research-tasks/{id} | 返回 200 和最新任务状态；不存在为 404，无效 UUID 为 400 |
| POST /api/v1/research-tasks/{id}/retry | failedRunId 指定失败执行，接受或重放返回 202 + 当前任务快照 |
| GET /api/v1/research-tasks/{id}/runs | 执行概要历史，按 attempt 升序；不存在任务 404，尚未执行为空数组 |

任务响应字段：id、question、status、createdAt、updatedAt、runId、startedAt、completedAt、result、errorCode。未产生的数据为 null。result 仅成功时存在，保留 answer/sources，新增 provider/query/retrievedAt/evidence，以及可空的 generation 元数据（V3）。

查询 FAILED 任务仍返回 200，失败原因由任务的 errorCode 描述。API 操作失败使用 `{"code":"...","message":"..."}`。

### 列表查询（2026-10-14）

GET 集合接口返回 items/page/size/hasNext。items 仅含 id、question、status、createdAt、updatedAt，不查询报告、执行或证据表，避免详情映射的逐条证据查询。默认 page=0、size=20；page 上限 10000，size 1–100。status 可省略或为四种大写任务状态之一。整数只接受 ASCII 数字，拒绝空值、负数、小数、重复及未知参数，统一 INVALID_QUERY；排序不可由客户端拼接。

单条参数化 SELECT，先按 status 筛选，再 ORDER BY created_at DESC,id DESC LIMIT size+1 OFFSET page*size，多取一行计算 hasNext。没有 COUNT 查询，不承诺总页数或跨请求一致快照。相同时间戳按 UUID 稳定排序，不声称 UUID 代表创建先后。新增/状态更新可使不同页重复或遗漏；大规模列表后续评估游标分页。

新增 H2 V4、MySQL V2 为全状态列表提供 (created_at,id) 索引；筛选列表复用已有 (status,created_at,id)。旧迁移不改、旧数据不改。2026-10-14 15:46:02 真实 MySQL 临时库验证通过，4 tests、0 failures/errors/skipped，覆盖 V2 索引、分页筛选及既有数据库回归，清理无错误。日常开发库未应用本轮迁移；大数据量既有库升级、索引访问计划及生产规模性能尚未实测。Python 请求/响应契约没有变化，列表不会调用 Python。

### 幂等提交规则

可选请求头 Idempotency-Key 为 1–128 位 ASCII 字母、数字或 `._:-`。未提供时每次创建新任务。

- 同键、相同原始问题：返回原任务当前快照，不重复执行；响应仍为 202，可能已经是终态。
- 同键、不同问题：409 / IDEMPOTENCY_CONFLICT。
- 并发插入通过数据库唯一约束仲裁；失败插入回滚后查询胜出记录。
- 键在整个本地应用内唯一且当前不自动过期；未来有用户后必须按用户隔离。

## 状态、事务和执行所有权

### 手动重试（实现、离线及真实 MySQL 验证完成）

2026-10-14 15:58:42 已核对真实 MySQL 测试报告：6 tests、0 failures/errors/skipped。新增并发重试、失败历史、次数上限、重开查询及含旧失败数据的 V2→V3 迁移均通过，测试库清理未报错。日常库未升级，未以真实供应商调用验证重试计费或稳定性。

请求体 {failedRunId} 指定失败执行，不用随机请求键替代失败版本。事务首先 SELECT research_task FOR UPDATE 锁定任务；检查该任务下指定 FAILED run 的 retry_accepted。已接受过的请求只返回当前任务快照，即使已成功或又失败也不再修改。未接受过的请求要求任务为 FAILED、runId 为当前执行，否则 409 RETRY_CONFLICT；attempt_no>=5 返回 409 RETRY_LIMIT_EXCEEDED。错误格式为 400 INVALID_RETRY。

同一事务把旧 run.retry_accepted 标为 true、任务 attempt_no+1 并转 PENDING。事务失败两者一起回滚；领取后新建当前次数的 run，旧失败 run 保留。详情通过 task_id + attempt_no 关联当前执行，排队期间没有当前 run，因此不泄漏旧 errorCode/result。每次完成仍要求 run=RUNNING 和 task=RUNNING，旧执行迟到结果无法覆盖新执行。新执行的结果、证据、状态仍一起提交。旧创建请求的 Idempotency-Key 保持原规则，重放不会自动重试。

历史接口最多返回 5 条执行概要（排队尚未开始的尝试不在其中），含 id/attempt/status/startedAt/completedAt/errorCode/retryAccepted。从未失败的成功结果不能重试；已接受的旧请求允许 202 重放成功状态，但不会新增执行。每任务 5 次不是全局额度限制，也不保证上游恰好调用一次；网络超时后旧 Python 请求可能仍在运行，重试可能遇到 MODEL_BUSY。仍仅支持单实例，无租约/自动重试。

新增版本化 Java 迁移 db.migration.V5__manual_retry / db.mysql.V3__manual_retry，共享 RetryMigration（作为这两个版本的一部分，应用后须冻结）。从元数据识别旧 task_id 单列唯一约束，新增次数及标记列、(task_id,attempt_no) 唯一约束，再移除旧唯一约束。H2 旧外键可能共享该唯一索引，需删除并重建 run→task 外键；MySQL 先建立替代联合索引，再移除旧唯一索引以保留外键支撑。原执行默认次数 1，retry_accepted=false，原 report/evidence 不改。Java 迁移固定 checksum=1，后续变更必须新增版本，不能改共享实现来改变已应用迁移。

MySQL DDL 无整批事务回滚保证，迁移失败不能盲目重跑或改历史，应检查部分变更；日常库升级前应停应用并备份。本轮只在隔离库验证，不擅自迁移用户库。Python 生产接口和模型逻辑未变；离线 HTTP 联调增加第一次 MODEL_TIMEOUT、手动重试后成功的固定样例，不代表真实供应商已验证。

正常流转：PENDING → RUNNING → SUCCEEDED / FAILED。

1. 创建事务只写 PENDING，不直接安排内存中的唯一任务副本。
2. 单后台工作线程每次完成后等待 500ms，再查找最早 PENDING。
3. 使用 `UPDATE ... WHERE status = 'PENDING'` 原子领取。领取和创建 RUNNING 执行记录在同一事务中完成；只有成功领取者调用 Agent。
4. Agent 调用在事务外发生，此时任务可查询，新任务可继续入库。
5. 结果/错误和任务终态在同一事务内保存；更新要求匹配 RUNNING 执行记录，拒绝迟到结果覆盖已经恢复的失败状态。

尚无自动重试。每次执行最多一次主动 Agent 调用不等于分布式 exactly-once：Python 完成后、Java 持久化前崩溃，仍无法确定外部执行是否已完成。

### 重启与关闭

应用 ready 时先恢复遗留 RUNNING 为 FAILED / EXECUTION_INTERRUPTED，然后启动轮询；PENDING 留在数据库中继续执行；终态不变。

该恢复算法仅适用于当前单实例嵌入式数据库。扩展多实例前需引入 worker 所有权、租约/心跳和过期恢复，不能直接复用“所有 RUNNING 均中断”的逻辑。

正常关闭给调度任务最多 70 秒完成；强制退出后依靠下次启动恢复。读取超时不是研究总截止时间，也不意味着 Python 工作被取消。运行时数据库故障可能使任务留在 RUNNING，恢复数据库并重启后会标记中断失败；当前不自动重新执行。

## 错误语义

| code | 同步聊天 HTTP | 研究任务或 API 行为 |
|---|---|---|
| INVALID_REQUEST | 400 | 创建 400，未入库 |
| AGENT_UNAVAILABLE | 502 | 任务 FAILED |
| AGENT_ERROR | 502 | 任务 FAILED |
| AGENT_INVALID_RESPONSE | 502 | 任务 FAILED |
| AGENT_TIMEOUT | 504 | 任务 FAILED |
| EXECUTION_FAILED | 不适用 | 执行出现未分类异常时 FAILED |
| EXECUTION_INTERRUPTED | 不适用 | 启动恢复遗留执行时 FAILED |
| INVALID_TASK_ID / INVALID_IDEMPOTENCY_KEY | 不适用 | 400 |
| TASK_NOT_FOUND | 不适用 | 404 |
| IDEMPOTENCY_CONFLICT | 不适用 | 409 |
| STORAGE_UNAVAILABLE | 不适用 | 数据访问异常时 503 |

上游错误正文、堆栈、SQL 参数不返回给用户。框架级 404/405/415 等错误尚未全部统一。已提供分页列表及手动重试；尚未提供任务取消、删除和自动重试。

## 后续设计（未实现）

下一条产品主线：用固定证据样例评估报告语义质量；真实供应商基础链路已验证，不代表长期稳定性或语义准确率达标。

- Evidence 已有 URL、标题、获取时间、内容片段及哈希；未获取发布时间。Report 默认确定性摘录汇总，可选模型报告已实现格式和引用 ID 校验，尚未实现语义引用评估。
- 真实长时研究需要总截止时间、并发/成本预算和取消协议。当前后台执行虽然不阻塞 HTTP，但仍为单线程顺序执行。
- 持续追踪需要主题、跨轮事件聚类和变化识别。
- 尚无鉴权、生产部署、队列配额或负载测试，不应直接作为公网服务。

## 已实现：Wikipedia 检索与证据（V2）

选择公开 MediaWiki API 作为第一个无需密钥的检索源。范围是百科条目，并非全网、新闻或事件实时索引。实现依据：[MediaWiki 搜索 API](https://www.mediawiki.org/wiki/API:Search_and_discovery) 和 [TextExtracts](https://www.mediawiki.org/wiki/Extension:TextExtracts#API)。

Python SearchProvider 接口允许后续扩展搜索源；当前实现 WikipediaSearch，默认 en，可配置 zh。一次请求使用 generator=search + prop=extracts，按搜索排名排序，去掉重复 URL 和空摘录，最多 5 条，每条截取最多 800 个 Python 字符。不再发请求抓取结果 URL，不跟随 HTTP 重定向。

每条证据含 id（E1–E5）、url、title、excerpt、retrievedAt、contentHash。contentHash 是所保存摘录的 UTF-8 SHA-256，不是整篇文章哈希，也不证明资料真实性。retrievedAt 为本次获取时间；没有伪造发布时间。摘要明确标为原文摘录，按 [E1] 等编号对应证据，不宣称进行了推理或事实核验。

Java 验证报告字段长度、来源与证据一一对应、证据 ID/URL 唯一、HTTPS URL、必填时间及内容哈希。V2 为 research_run 增加报告元数据，新增 research_evidence 表；报告、证据和任务终态在同一事务保存。证据写入失败会回滚整个结果。

V1 迁移保持原样。旧成功结果读取时标为 provider=legacy-mock、retrievedAt=null、evidence=[]，保留原回答和来源，绝不补造来源。数据库升级测试从仅有 V1 的文件库开始验证。

Python 将网络/限流/数据异常转换为 SEARCH_TIMEOUT、SEARCH_UNAVAILABLE、SEARCH_RATE_LIMITED、SEARCH_INVALID_RESPONSE；Java 只保留白名单错误码，任务标记 FAILED。不会把检索失败回退成模拟回答。零条有效摘录属于成功执行但无结果，返回空 sources/evidence 并明确说明检索范围。

搜索单次网络操作超时 20 秒，响应读取最多 256 KiB；Java 研究接口读取超时默认 60 秒，旧聊天接口仍为 10 秒。该限制不是严格总截止时间，慢速分块响应或 DNS 行为可能延长搜索整体耗时。当前未实现重试、缓存、全文抓取、查询规划或通用网页提取。常规测试用固定样例，真实外网测试需显式启用且可能受网络/上游波动影响。

## 已实现：可选模型报告与 V3 元数据

取舍：采用标准库 HTTPS 客户端实现兼容 Chat Completions 的单次非流式请求，不安装平台接入工具或新依赖。服务提供商由受信环境配置选择，不由 API 请求参数或模型输出选择。默认关闭；Agnes 中国站地址、账户模型和计费确认后才进行真实联调。

Python ReportGenerator 接受 SearchProvider 已返回的报告。只发送 query 和 evidence 的 id/title/excerpt，不发送源码、数据库、环境变量或历史记录。零证据直接返回无结果，generation=null；关闭模型仍使用原有摘录报告，不冒充模型生成。

模型输出契约为 claims[{text,evidenceIds}] 与 limitations[]。最多 8 条结论、每条 1–5 个存在且不重复的证据 ID、1–4 条局限说明；每段最多 600 字符。无结论时明确证据不足。拒绝未知 ID、额外结构字段、工具调用、非正常结束、HTML 标记、嵌入引用或 HTTP 链接。程序只生成纯文本报告，前端仍必须安全渲染；引用编号有效不等于证据支持结论。

模型没有文件、终端、数据库或任意 URL 工具。提示词声明外部内容不可信，但权限隔离由程序结构保证，而不是依赖模型遵守提示词。平台回应不能更改 evidence、sources 或工具权限。

传输边界：固定环境配置的 HTTPS 域名及 /v1 路径、443 端口、默认系统信任证书，不跟随重定向、不继承系统代理。域名白名单是本机管理员配置，不是恶意域名识别或 DNS 重绑定防护。每次执行最多一次调用，无 Python 内部重试/回退/自动切收费模型；Java 手动重试会新建执行。请求最多 32 KiB、响应最多 64 KiB，max_tokens=1200。供应商是否正确计量或遵守 token 参数无法由客户端保证。

使用可终止的 multiprocessing spawn 子进程执行 DNS、TLS 和响应读取。父进程等待 20 秒后终止子进程，另有启动与清理开销；不会仅在线程超时后让请求无限后台运行。只在模型生成期间持有进程内非阻塞互斥锁，冲突返回 MODEL_BUSY；多 worker 不共享锁，当前只支持一个 Python worker。HTTP 客户端断开不能保证上游已停止计费。

Java 继续校验证据，并检查 generation 的字段及报告中出现的引用。V3 添加 research_run.generation_json，成功结果、证据、元数据及任务状态在同一事务保存。generation 包含 model、host、promptVersion=evidence-report-v1、inputHash（完整模型请求体 SHA-256，不含鉴权头）。模型名是请求值，不是供应商模型身份认证；不存完整提示词或鉴权值。

MODEL_TIMEOUT / MODEL_UNAVAILABLE / MODEL_INVALID_RESPONSE / MODEL_RATE_LIMITED / MODEL_AUTH_ERROR / MODEL_CONFIG_ERROR / MODEL_INPUT_TOO_LARGE / MODEL_BUSY 均通过固定安全错误码传播并保存为 FAILED，不返回原始供应商错误信息。失败任务当前不保存先前检索的中间证据，未来需独立的检索阶段持久化设计。

诊断补充（2026-10-14）：MySQL 联合验证出现 MODEL_INVALID_RESPONSE 后，为 Python 增加固定类别的响应拒绝日志，区分响应 JSON、结束原因、消息结构、内容 JSON、报告字段/数量、证据编号及文本约束等检查阶段。只输出代码内固定分类，不记录供应商正文、异常详情、提示词或凭据，对外错误码不变。历史失败未保存细分原因，不能追溯断言其具体原因；新增诊断需要重启 Python 后才生效。

提示词 v2（同日 15:31）：第二次失败落在 report_limits；发现 v1 未明确局限说明 1–4 条等已有校验要求。v2 完整描述允许字段、数组类型、结论 0–8 条、局限 1–4 条、引用 1–5 个且唯一、文本长度及引用位置。校验保持严格，不默默裁剪或自动重试。generation.promptVersion 对新报告为 evidence-report-v2，Java 兼容 v1/v2；旧数据不迁移。诊断细分数组类型和条数，但原失败缺少更细数据，不能断言是哪一字段。离线联调及随后单次 Python 真实调用、MySQL 真实联合验证均通过，长期遵从率尚未评估。

离线验证包含真实子进程超时终止、结构与引用反例、并发拒绝、无重试、大小限制及 Java/Python HTTP 联调。离线联调的搜索和模型采用测试内固定样例。2026-10-14 用户授权后，Python 使用公开关键词 artificial intelligence 完成一次到 https://api.agnes-ai.cn/v1 的 agnes-2.5-flash 实际调用，结构化报告校验通过；这不是完整 Java 入库链路测试。语义准确率、实际费用和长期稳定性仍未验证。普通测试强制关闭真实模型；tests/run_offline_contract.py 可重复运行离线跨服务链路。

后续验证补充（同日 11:40）：用户账单确认上一轮调用费用为 0 分。新增显式启用的 LiveModelIntegrationTests，完成真实 Java worker → Python → Wikipedia → Agnes → 临时 H2 文件库链路；验证幂等重放不创建额外执行、证据及 generation 持久化、关闭 Java 后重新打开数据库仍能通过 HTTP 查询完全相同的任务。首次因 Wikipedia 限流失败，冷却后仅重试一次成功；限流失败保留记录，不作为产品自动重试实现。当前新请求费用及语义质量仍未核验。测试不接触开发数据库、不重启用户 Python 服务，普通离线运行默认跳过。

## 2026-10-22 搜索与回答质量补充

最新排序修正：将全局覆盖增益与来源内覆盖增益相加作为首要排序，再以来源内增益、词汇分数和来源多样性破同分。此前“全局优先、来源内仅破同分”在真实中文及复合 API 比较中仍会让个人经验/示例挤掉核心章节。相加不增加证据数、每来源上限或请求次数；仅是覆盖启发式，不识别来源可信度或版本。406 项离线测试通过，尚未真实部署验证。

报告生成增加仅供应商输出使用的 GroundedReportOutput：每个 claim 的 supportingQuotes 必须与 evidenceIds 一一对应，短摘录经空白归一后必须出现在对应证据正文中；不匹配即按固定类别拒绝，不自动追加模型调用。对外 ReportOutput 仍只有原有 Statement 字段，短摘录辅助字段不进入 HTTP/Java 持久化契约。此措施核对引用原文存在性，不等同于语义支持或事实核验；需继续人工检查限定语与推理。

本节补充当前 web-model 路径，历史章节保留。Java/Python 对外契约及数据库版本不变。

- 定义类问题的资料选择利用提取器保留的 class/exception 声明主题，对每个直接对应问题的定义分别记录覆盖（包括直接降级后的单一复合问题）。全局子问题覆盖提升相同时，再比较单一来源内部的覆盖提升，避免一个旧页面先覆盖某问题后，当前页面的对应定义被普通介绍挤掉。仍是词汇/结构启发式，不是语义证明，也不适用于所有文章类型。
- SearXNG 返回的单个明确正向 `site:domain[/path]` 查询，在截取前五个候选前进行域名及子域边界、可选路径边界过滤；过滤计入已有 rejected_count。带路径查询向上游转换为域名查询，返回后仍按原路径限制，不增加请求；裸路径查询附带文件名作为关键词。复杂 Boolean、多个 site、负向 site、完整 URL、转义路径语法暂不解释；不将此机制宣称为完整来源约束或重定向后的来源校验。
- 报告生成不再接收审核模型的 reason/coverage 等推理内容，只接收原问题、子问题、最终证据及是否补搜后未复核的布尔标志。审核结果仍保存在会话用于展示。这样避免把前一步模型的结论当作独立证据；仍不保证报告语义正确。
- 提示要求区分历史/当前版本，保留默认值、可选项等限定语；简单定义比较优先 3–5 条直接结论。不得凭模型记忆猜当前发行版本。字段及引用校验维持原有严格要求，没有新增模型调用或重试。
- 搜索源按真实公开查询探测结果配置；2026-10-22 Yahoo 可用，DuckDuckGo CAPTCHA、Brave 限流、Qwant 拒绝访问。Mwmbl 可搜索但本次结果偏旧，未启用。固定镜像将 Mojeek/Startpage 标为 inactive，不强制开启。可用性是当次结果，不保证长期稳定。
- 网页模型单次等待上限改为 45 秒，搜索/正文仍 20 秒，整次共享截止时间仍 150 秒、模型最多 3 次。每次预约取阶段上限与剩余总时间的较小值；父进程可终止超时子进程。Java 175 秒等待保持兼容；旧 Wiki 默认模型等待仍 20 秒。修改依据是实际出现规划/报告 20 秒超时而总时间尚有余量，不承诺供应商一定在 45 秒内完成。
- 同日中文质量迭代：内部 Plan 新增 evidence_needs（不改变持久化/HTTP 契约），选择器组合已有的 question/evidenceNeed 作检索提示，模型审核与报告仍收到原始问题。非英文规划的 evidenceNeed 提示加入简短英文主题对应词，允许匹配英文正文。提示本身从不作为引用或证据；无匹配正文仍无证据。章节标题覆盖作为结构相关性特征，避免包含多个关键词的个人建议挤掉前后端职责章节。真实文章本地重放从只选中文后端/个人建议，变为中文前后端及英文补充；不是新增真实模型质量验收。


## 2026-10-25 证据选择与跨语言提示

v3 每来源最多 4 段、总证据上限仍为 8；v2 保持 2 段。选择时只使用最近小节标题和正文计算词汇覆盖，避免祖先标题使无关段落虚增相关性；API 定义和小节主题分别累计覆盖。模型规划新增私有 retrievalTerms，按子问题提供中英文主题词，加入选段需求；公开 plan 不增加字段，阶段记录保留这些词以便准确回放。

报告供应商只需填写 supportingQuotes，程序据此生成 evidenceIds；旧显式列表仍验证一致性，不静默修复。允许同一证据的多个不同短引文；重复引用、未知原文编号与超界输出仍拒绝。最终公开报告与数据库字段不变。


## 2026-10-25 报告独立复核

用户已授权免费模型不限累计调用。本轮观察到原文编号正确仍可能出现否定性泛化，因此隔离 debug_agent 显式启用有界第四步 verify，单研究最多 4 次模型请求，总时限保持 150 秒；不循环修复。日常 SessionRunner 的 verify_report 默认为 false，保留最多 3 次调用。复核只接收公开问题、草稿及最终证据，不能调用工具；逐条返回 keep/revise/remove，程序验证覆盖所有断言后组装报告。失败不发布草稿。新 session-v2 与旧 session-v1 显式区分，Java 校验版本、计数及最终复核状态。阶段记录保存已验证的草稿与复核输出；报告检查只检查最终复核，完整离线回放保留 verifyReport 标识。

真实复核仍会漏过缺乏直接支持的绝对断言，不能作为事实核查。用户选择继续使用当前模型并明确展示限制；前端有报告时提示引用不保证整句话得到支持，有成功复核时另说明其非事实核查。该决定不放松原文存在性、结构、来源或预算检查。

