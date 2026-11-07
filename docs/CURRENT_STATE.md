# 当前开发状态

更新日期：2026-10-25。

## 2026-10-25 长任务执行、取消与中断恢复

本轮三项目标在单实例范围完成并加载到隔离环境：后台提交后可轮询具体阶段、刷新恢复；排队及运行取消、阶段超时；Java/Python 中断后的终态识别、手动重试资料复用与重复请求保护。接口及边界见 [执行控制 v1](contracts/EXECUTION_CONTROL_V1.md)。

Java 持久化阶段与取消意图，取消和完成以任务行锁串行决定，旧执行不能覆盖新执行；运行中取消先显示等待，观察到取消后不再发起后续步骤。Python 用本机执行控制库保存身份、终态响应和公开检索结果/正文，相同执行编号不重复调用模型。重试只复用同问题/语言/模式且输入匹配的一小时内资料；模型步骤仍重新执行，不是模型生成断点续写。新建页面保存当前标签页未确认提交的幂等键，刷新后相同输入可查回原任务。

验证：Python 全量 **467 passed / 1 skipped**（显式互联网搜索项未运行），最后边界回归 **43 passed**；Java 全量 **105 项，78 passed / 27 skipped**（需显式启用的外部或集成测试），另由用户本机运行 MySQL **16 passed / 0 skipped**，包括 V8→V9 迁移与取消/恢复。前端 **8 passed**，类型检查、ESLint、生产构建通过。

独立真实 Java/Python/React HTTP 与 H2 故障验收通过：排队取消、读取中取消、复用后重试、重复执行请求不新增调用、Java/Python 分别强制中断并恢复、截止时间，以及浏览器刷新/取消/提交响应丢失后的幂等恢复。外部工具全为合成样例，真实模型调用 **0**。证据 `logs/reliability-check-b1c2fdd363924f888ccba41f6766636a/result.json`、同目录 browser-result.json 与截图；该测试自有服务已结束。

新增 H2 V11 / MySQL V9，旧迁移未改。隔离 H2 已升级，18000/18080/15173 保持运行供使用，历史报告可读取。日常 MySQL 未升级；如需日常部署，仍须先运行备份后启动流程，同步加载 Java/Python。用户为本轮测试启动的 MySQL 服务保留运行，未替用户停止。

## 2026-10-25 实际研究质量迭代与已接受边界

完成跨语言主题词、按小节选段、弱相关资料过滤、模型模式每来源最多 4 段（总计仍 8 段）、原文编号引用及固定证据单报告调试。真实中英文示例的核心问题覆盖已改善；不能据此声称所有问题质量达标。19 次执行共 43 次模型请求，详情见 [质量验证记录](QUALITY_2026-10-25.md)。

用户明确选择继续使用 agnes-2.5-flash，并接受、要求展示其语义支持判断不稳定的限制。报告页面已显示“引用不保证整句话被资料支持”，有复核的结果另提示“模型复核不等于事实核查”。独立逐条复核仍会漏过证据不足的否定性断言，仅在隔离实验启用；日常 SessionRunner 默认关闭，保留最多 3 次模型请求。实验 session-v2 最多 4 次，复核失败不发布草稿。

验证：Python 全量 448 passed / 1 skipped（显式真实搜索项），最终开关相关回归 19 passed；Java 受影响隔离测试 9 passed；React 7 passed、类型检查和 lint 通过。三份真实结果经本机 Edge 检查质量说明、引用定位、刷新及离线报告检查，无页面错误。最新 session-v2 离线回放完成，外部请求 0；代码版本变化已如实标记。以上不是语义正确性的自动证明。

本轮未启动或升级日常 MySQL，无新增数据库迁移。运行验证使用隔离 H2 与 18000/18080/15173；日常部署需同步 Java/Python 契约。当前保留隔离服务供查看，不再自动发起真实模型调用。

## 2026-10-25 第三阶段：前端展示与整体验证

已完成隔离环境“阶段复查”页面：显示阶段状态/耗时/数量、安全失败原因，可展开公开输入输出；手动执行完整离线回放、重新选择证据、检查已保存报告。刷新和历史执行按 runId 关联；缺失/不完整/损坏记录有提示，完整回放与研究成功分别呈现。默认日常构建隐藏此功能，不新增日常业务 API 或数据库迁移。没有实时推送、断点续跑或网页真实报告重生成入口。

只读诊断接口只注册在 debug_agent，隔离 Vite 显式启用固定 18000 代理；UUID 查找当前会话，不接受文件路径，动作白名单不含真实生成。操作不写业务库和原记录。默认样例和实际公开记录标记区分，完整提示指令不返回浏览器。

验证：Python 全量 **440 passed / 1 skipped**（真实互联网搜索显式启用项未运行）；React **7/7**，TypeScript、ESLint、日常 Vite 构建通过。新增接口无路径输入、只读回放、损坏拒绝、页面按需加载/失败/缺记录/不完整记录测试。

真实本机 Edge 验收四类合成任务：成功、报告失败、补搜、无资料；覆盖页面创建、三个离线按钮、刷新、历史执行、引用定位、390px 手机无横向溢出及无页面异常。完整管理生命周期、独立重启、H2 保留、意外退出清理、日常文件/端口未变也通过。报告：`logs/debug-check-15d5e54770064660b9f1aa1ad19688ba/result.json` 和同目录 `browser-result.json`、桌面/手机截图。

三个工程调试阶段已按上述边界完成；验收服务已关闭，本轮无需用户输入凭据。真实模型请求 **0**，未再次验收回答质量、MySQL 套件或公网部署。后续质量工作可固定记录定位选段/报告问题，再单独确认有界真实验证，不再默认从搜索反复重跑。

## 2026-10-25 第二阶段：研究记录与回放

已在隔离调试环境接入本地阶段记录：规划、搜索、正文、选段、审核、报告与终态。保存公开输入及通过校验的模型输出，拒绝原文不保存。新增 inspect/session/select/report-input/report-check 离线 CLI，以及注入 completion 的固定证据报告生成函数。日常数据库和 HTTP 契约未改变，无新增迁移。见 [RESEARCH_REPLAY](RESEARCH_REPLAY.md)。

验证：Python 后端及调试脚本全量 **432 passed / 1 skipped**；随后增加写盘失败、中断、规划失败回退和选段变化测试，记录模块 **16 passed**。首次沙箱运行因临时目录权限及本机子进程限制失败；改为 E 盘独立临时目录并获工具批准运行后通过。跳过项未算通过。

本机隔离验收通过：`logs/debug-check-edf12fdc452b41918e16b7b32bae6ee6/result.json`。包括代理创建成功/失败任务、记录落盘、五种回放 CLI、独立重启后的记录与 H2 保留、停止/意外退出清理、日常文件和端口状态未变。验收服务已关闭。

边界：搜索和模型为合成样例，真实模型请求 **0**；没有重新验收中文回答质量。固定证据生成只验证注入模型，真实调用仍需确认预算。记录不是持久化检查点；前端研究过程展示留待第三阶段。本轮无需用户输入密码或重启日常服务。

## 2026-10-25 第一阶段：隔离调试环境

已完成独立调试入口（[操作说明](DEBUG_ENV.md)）：18000 Python / 18080 Java / 15173 React，随机会话目录 H2，Java 源码复制到独立构建目录，不写日常 target、不需要 MySQL/模型密码。默认是固定样例 v3，明确不是真实搜索/模型验证。支持 start/status/stop、Python 重启、Java 重编译重启、前端重启和 shutdown。

实际本机 HTTP 验收通过：端口冲突拒绝且不抢占；经 Vite 代理创建成功及失败任务；分别重启三个服务；Java 重编译及 stop/start 后 H2 记录相同；强制退出管理进程后 Windows Job Object 清理服务；日常 Java target/classes、data 文件元数据及 8000/8080/5173/3306/8888 端口状态未改变。报告 `logs/debug-check-addad24e2e1a4e1abf95248d45b58720/result.json`。验收运行结束，调试服务已关闭。

Python 业务及首批隔离测试合跑 418 通过 / 1 跳过；随后补充虚构密钥重启/脱敏及未知异常输出保护用例。PowerShell 两入口语法通过。Java 按隔离目录离线打包并真实启动，本轮未重新运行全部 Java 单测、MySQL 套件或浏览器视觉套件。可选真实模型入口的密钥路由、预算重启不重置仅离线验证，未使用真实凭据/供应商；真实模式需另行授权，不沿用已耗尽额度。

本轮没有数据库迁移、Git 操作、软件安装或日常服务启停。旧质量目标已由用户于 10 月 22 日停止，不再等待当时的追加额度问题。当前仅完成新计划第一阶段；阶段级运行记录/回放和更完整前端过程展示尚属后续工作。

## 2026-10-22 追加中文质量验证（进行中）

本节为最新状态，下面各节为历史记录。目标仍是改善实际搜索与回答质量，**尚未通过整体质量验收**。

- 追加额度已用 **6/6 次研究、18 次模型请求**，停止真实调用；正在等待用户确认是否追加最多 4 次、每次最多 3 请求及免费配置仍有效。账本 `logs/quality-20261022-round2-attempts.json`，逐次结果见 [质量记录](QUALITY_2026-10-22.md)。
- 第 1 次中文完整回答，但 PHP 错引且招聘条件泛化。新增短原文检查后，第 2/5 次中文因原文不匹配拒绝，第 3 次英文结构不合格，第 4 次中文缺字段；第 6 次英文结构和原文匹配成功，但仍用 Python 2 httplib 支撑当前模块，并误称 source_address 为安全参数。不能将引文存在性等同于语义支持，也不能称中文可用性已通过。
- 已改进 evidenceNeed 辅助匹配、章节/定义相关性、供应商专用 supportingQuotes 校验与完整输出示例。公开 HTTP/Java 报告字段不变，错误仅记录固定分类，不记录模型原文或凭据。
- 最后新增全局覆盖与来源内覆盖增益共同排序。通用复合定义回归先失败后通过，全套 Python **406 通过 / 1 跳过**。中文局部重放从个人经验+后端变为前端+后端；合并第 3/6 次已保存公开摘录的英文局部重放保留当前两类定义，但旧版本仍可能入选。两者均不是完整正文或新增真实验证，版本/来源约束仍未解决。
- **最后排序修改尚未重启加载**。Python 由用户普通 PowerShell 的 Start-WebModel.ps1 管理；旧 READY 窗口仍保留 Java，不通过旧 supervisor 管理当前 Python。待额度和配置确认后一起请用户重启，无需现在反复重启。
- 本轮未改 Java、React 或数据库结构，日常仍 MySQL V8；无新增无人值守流程、Git 操作或收费服务。

## 2026-10-22 搜索与回答质量迭代（最新）

本节优先于下面历史交接。已完成本轮代码修复与有界验证，但**搜索与回答质量尚未全面验收**，中文普通概念问题仍需继续改进。

- 搜索默认改为已实测可用的 Yahoo；DuckDuckGo 当前 CAPTCHA，Brave 限流。隔离验证备用源后已清理测试容器。单个 site 域名/路径在候选截断前过滤；路径查询做上游兼容转换但保留原路径限制，真实探测只返回指定当前官方页面。
- 选择器改善定义主题、复合问题多个实体、单个来源内部覆盖；官方文档中的两类定义现能同时入选。报告不再接收审核模型的推理文字，减少把模型判断当证据的影响；提示区分版本、限定语与逐分句引用。最后追加“不臆造来源限制、普通问题保留宽泛查询”规划提示，尚无真实验证。
- 网页模型阶段最长 45 秒，搜索/正文仍 20 秒；整次 150 秒、最多 3 次模型调用不变。Java 175 秒等待兼容，旧 Wiki 默认模型等待仍 20 秒。没有新增数据库迁移，日常仍 MySQL V8。
- Python 全套 **390 通过 / 1 跳过**，最后仅规划提示调整相关 **26/26**。Java/Python 对外字段未变，真实任务经过现有 Java/Python/MySQL 链路；本轮未重跑 Java、MySQL 隔离套件或前端浏览器套件，未改 Java/React/数据库代码。
- 用户本轮额度 **6/6 次研究，实际 16 次模型请求**，已停止真实调用。第 1/2 次接口成功但混用旧版本，质量未通过；第 3 次查询空结果后审核失败；第 4 次核心定义和区别改善，仍有历史括号说明引用不精确；第 5 次中文报告超时；第 6 次无可读取正文后审核失败。**不能称中文问答已通过，不能称 45 秒等待已验证解决超时。**
- 完整过程、任务 ID 和下一步见 [本轮质量记录](QUALITY_2026-10-22.md)。本轮未新建无人值守流程；复用原有启动窗口重载服务。无 Git 操作、凭据落盘、日常数据删除或收费服务接入。

## 2026-10-22 本轮最终交接

**可演示交付已完成：网页研究、主题/轮次管理、跨轮资料修订时间线、有界无模型调度及工程验证。** 这是资料追踪首版，不是自动事实裁判或完整现实事件理解系统。搜索和模型仍存在下列实际限制，不据此宣称所有问题都能可靠回答。

- 日常 MySQL V8 已备份部署并再次重启验证。主题 `a4bd3bd3-2cbc-4935-aaed-2e770f965bff` 的 2 个 COMPLETED 轮次、10 条资料观察、3 条提取方式变化及先前摘录均保留；自动频率=0。Java health=UP。最后备份 `backups/mysql/unattended_448ca6296e7943018f176626f3e2c055.sql`，SHA256 `b58fa6b510a1ba67f4572482ad6e204cf1b8a616dad5f1f45a8bd285e4d9e9d1`。未做恢复演练，不自动回滚旧库。
- 验证：Java **95 总数 / 70 通过 / 25 默认跳过**；显式临时 MySQL **14/14**；Python 全套 **369 通过 / 1 跳过**，后续仅审核提示/固定错误分类改动相关 **32/32**；React 构建/lint、单测 **4/4**；隔离 Edge 浏览器 **12/12**；真实日常浏览器确认两轮、刷新、提取器变化、手机无横向溢出。
- 真实模型累计 **7 次研究尝试 / 15 次模型请求**，不再继续调用，未超过同意的 10 次/最多 30 请求。第 4、5 次三阶段通过；第 4 次的版本注释误读已定位并通过结构化正文提取修复，第 5 次保存了准确所属标题与定义。第 6 次审核一致性失败，第 7 次搜索不可用（仅规划 1 次模型调用），失败资料/历史均保留，没有报告伪装成成功。最后的排序及提示调整已离线验证，不能称第 6/7 次证明了真实报告质量改善。
- 已知限制：DuckDuckGo 上游间歇不可用；模型仍可能误读或概括不准；日期、覆盖充分性、转载独立性不自动保证。事件语义归并、矛盾裁定、通知、登录、多实例、公网部署不在已完成能力中。未在全新机器验收安装，未做备份恢复演练。
- 服务保持运行：Java 8080、Python 8000、前端 5173、搜索 8888、MySQL 3306。用户保留 READY 窗口即可，不需再次输入凭据。没有建立 Git 仓库、上传数据或删除日常数据。

操作入口：[演示与启停](DEMO.md)、[固定管理操作](UNATTENDED.md)、[追踪接口与边界](contracts/TRACKING_V1.md)。网页 http://127.0.0.1:5173/#/topics 。以下为过程与历史记录，不覆盖本节最终状态。

## 2026-10-22 14:18 真实部署与证据上下文修复

日常 MySQL 已完成 V7→V8。受控部署先通过 Java **95 总数 / 70 通过 / 25 跳过**、临时 MySQL **14/14**，再备份 `backups/mysql/unattended_c8a684b016804a90ba3a52170a7dc8f6.sql`，SHA256 `72ea6b5d814d463b227d741a5b4ff365bfb85f12ee06f3c066dba29db88550fa`，随后 Java 健康正常。未恢复备份演练。前端 lint、构建、单测 4/4；隔离浏览器 12/12。

真实追踪主题 `a4bd3bd3-2cbc-4935-aaed-2e770f965bff` 自动检查关闭。第 4、5 次模型研究均完成计划/审核/报告，每次 3 模型请求；两轮报告、来源、变化入库。真实浏览器刷新确认两轮及 3 条“提取方式变化”，手机无横向溢出。截图 logs/tracking-desktop.png、tracking-mobile.png，仅本机演示。

人工核对第 4 次报告发现方法版本注释被误读为类新增时间。修复 extraction.py：采用 Trafilatura XML 结构保留段落和标题/定义列表上下文，不按软换行切断；每个有界块带所属主题，提取器标记 `trafilatura-2.3.1-context-v2`，不把提取变化当网站内容更新。第 5 次实际资料包含正确的类定义上下文，未再出现该版本误读；仍不能保证模型逐句事实正确。选择器排除常见英文虚词、按子问题词汇覆盖提升选择，域名多样性仅作相关性同分条件，避免普通词或无关来源挤掉直接资料。完整 Python **369 passed / 1 skipped**。

第 6 次公开官方资料任务规划成功、审核一致性失败，已保留资料，报告为空。追加固定原因分类和审核动作自检提示，32 项相关离线测试通过。第 7 次使用同一任务 failedRunId 显式重试进行中；账本是 logs/goal-model-attempts.json，总上限仍 10。没有自动重试、没有放宽校验或新收费服务。

## 2026-10-22 持续目标进展（进行中）

用户已完成 READY，无人值守管理进程保留一次性输入的凭据，不落盘真实值。真实连接检查、Python 重启、Java 全量测试、临时 MySQL 测试、备份及打包运行均已验证。Maven 依赖缓存复制到 E:\InfoExplorer\.cache\maven-repository，未删除 C 盘旧缓存；本机忽略的 .mvn/maven.config 指向 E 盘。此前日常运行 MySQL V7，最新 V8 部署正在通过固定测试→备份→启动流程执行，尚不能称升级完成。

研究可靠性：修复内层固定 10 秒与外层 20 秒超时不一致；父进程预算包含启动耗时。只兼容完整单层 JSON Markdown 围栏，其他多余文本、重复字段、结构/引用错误仍拒绝。模型提示携带校验用 JSON Schema 和字段长度，诊断仅固定错误类别。Python 全套 **365 passed / 1 skipped**；不记录模型原文或凭据。

本目标真实模型使用 **3/10 次研究尝试**（约 6 次模型请求，预算每轮最多 3 次）：
- 01：流程 SUCCEEDED，但规划围栏被拒后降级，报告混有镜像/二手资料，不能称“仅官方来源”约束通过。
- 02：规划成功，审核文本规则失败；添加精确类别与 Schema 长度提示。
- 03：规划成功，3 次定向搜索均未取得资料，只有 1 次模型请求，没有审核/报告。不是研究成功。
- 最新公开 Python 文档搜索/正文探测通过，但 DuckDuckGo 仍曾验证码/暂不可用，不保证长期稳定。未增加付费搜索源。

新增追踪代码：H2 V10 / MySQL V8，主题/不可变配置版本/轮次/来源修订/变化时间线；手动幂等、同主题单活跃轮、失败重试、暂停归档、分页历史、独立低频调度与错过时槽合并。模型研究仅手动，自动检查默认关闭。Java 负责持久化与调度，Python 契约不变。变化类型区分首次发现、正文更新、未变、提取器变化与可能同文来源；保留上次及本次摘录。时间是发现时间，不冒充现实事件时间；事件语义归并、矛盾裁定未实现。

验证：首轮 Java 全套 **94 总数 / 69 通过 / 25 跳过**；真实临时 MySQL **14/14**，包括 V7→V8 保留旧任务、并发幂等、修订比较、重启和调度恢复。后续新增 API 校验及上次证据展示，正在部署流程重跑 Java/MySQL。React 构建/lint 通过，真实 Java HTTP + 隔离 H2 + 模拟 Agent 的 Edge 浏览器 **12/12**，覆盖追踪两轮、刷新、暂停、手机布局及拒绝自动模型检查；这些是离线夹具，不是真实研究结果。日常真实追踪验证尚待部署后执行。

详见 [持续计划](CONTINUOUS_PLAN.md)、[无人值守准备](UNATTENDED.md)、[追踪契约](contracts/TRACKING_V1.md)。目标仍 active，无 Git 操作、无公网部署、无日常数据删除。

## 当前交接：模型研究接入 Java、数据库与 React（日常 MySQL V7 已启动，待真实模型验证）

### 19:05 搜索源调整与无模型真实链路通过

绕过 SearXNG 的容器内 urllib 直接访问 Bing，页面标题保留 `site:docs.python.org http.client`，正文结果却是无关知乎条目，说明异常无需项目解析器即可复现；具体上游/出口根因仍未确认。临时启用 Google 实测 access denied，已撤销。DuckDuckGo 恢复返回官方 Python 文档；Brave 仍 too many requests。

修改 infra/searxng/settings.yml：默认仅启用 DuckDuckGo，Bing/Brave 保留但 disabled=true；已重启既有搜索容器加载，不更换镜像、不读取容器环境密钥。真实 check_local_search.py --live --extract 通过：5 个候选、warnings 为空、仅 DuckDuckGo，官方 http.client 页面提取 320 段，未截断。

创建单次公开 web 摘录任务 `09e816a8-9549-4fce-8c0f-75cbfc1269fa`（固定幂等键 search-recovery-20261019-01），runId=7329f76c-5f4f-4e57-9694-b6fabb1e713b：Java→Python→真实搜索/正文→日常 MySQL 保存后 GET 返回 SUCCEEDED/COMPLETED；6 条证据、1 次搜索、5 次读取尝试、0 次模型调用。含官方 Python 资料，也混有 HTTPX 资料，不代表所有证据精准或已完成语义核验。本轮未重复浏览器测试、未运行代码回归（仅搜索配置及文档调整），未升级数据库，未改 Python/Java 接口。

仍待解决：DuckDuckGo 曾验证码，当前可用不保证持续稳定；只有一个默认来源，暂无可用冗余。模型规划超时和报告 JSON 失败仍未修复，本轮未再调用模型。用户服务保持打开，无需重启 Python/Java。

### 17:21 携带 Schema 的真实重试：审核通过，报告仍失败

用户再次重启 Python 后，同一公开任务重试一次，runId=5fae8cd2-2c88-41f2-bce2-abe7f8cf44b7。规划 MODEL_TIMEOUT；审核通过并正确指出空气净化器租赁资料无关，提出两条 docs.python.org 定向查询；报告失败，固定诊断为 json_syntax，尚不能区分 Markdown 包装、截断或其他非法 JSON。3 次模型尝试、3 次搜索、7 次读取尝试；保存 2 条与问题无关的摘录，不是成功研究。不再自动重试模型。

独立直接请求本机 SearXNG（未经过 Java/Python/模型），公开关键词 `site:docs.python.org http.client`，响应 query 与提交一致，但结果来自 Bing 的 Teams 网页；DuckDuckGo 报 CAPTCHA，Brave 报 Suspended: too many requests。因此不相关检索可在搜索服务层复现，不能归因于模型编造关键词。已读容器内 Bing 引擎源码，q 参数按查询构造；尚未定位到上游、出口网络或解析层具体原因，不断言 VPN 导致。当前需要先恢复可靠的检索，再排查模型超时/报告格式；没有修改搜索配置、关闭用户服务或要求再次重启。Java/MySQL V7、Python、Docker 仍保持运行。

### 17:17 诊断重试仍失败

用户重启 Python 后，同一公开任务手动重试一次，runId=f49f2490-f20b-4a69-b648-429b0f890c66。结果 FAILED/MODEL_INVALID_RESPONSE：规划再次 MODEL_TIMEOUT，审核阶段安全诊断为 schema（JSON 结构不符合约定），未进入报告阶段。1 次搜索、5 次读取尝试、2 次模型尝试、0 条可用证据；返回的 Weqas 网页与 Python 文档问题无关。不能据此判断供应商模型能力或将端到端验证标为通过。

已把校验所用 Pydantic JSON Schema 同步加入各阶段系统提示，明确嵌套结构及必填空数组；仍严格拒绝不合格响应，不增加自动重试。调整后相关离线测试 41/41 通过（首次沙箱执行遇到临时目录/本机 HTTP 限制，获准本机执行后通过，临时目录位于 E 盘）。该调整尚未加载到用户运行的 Python，也尚未真实验证。检索相关性及规划超时仍待排查。

### 17:11 首次真实网页模型联调：失败已保留

用户手动打开 Docker Desktop 后引擎恢复，工具启动既有 infoexplorer-search-searxng-1，未下载镜像。Java/Python 健康正常，前端 5173 可用。用户已确认 Agnes 原配置和当前免费额度。提交一次公开 Python http.client 文档问题，taskId=4e8afa85-83f4-412a-a628-d963e4d236fd，runId=5de60350-2d6a-46a2-beb0-65087be7806d，固定幂等键 live-web-model-20261019-01。

结果 FAILED/MODEL_INVALID_RESPONSE，实际预算记录 3 次模型尝试、3 次搜索、7 次正文读取尝试、6 条证据。规划 MODEL_TIMEOUT 后退回原文检索；审核成功发现初始数学资料不相关并请求定向补搜；报告输出未通过校验。网页刷新确认失败原因、补搜理由和证据保留正常，不得将此记录称为研究成功或相关性达标。保留日常任务记录，不自动删除。

已增加可选安全诊断：logs/web-model-diagnostics.log 仅记录固定阶段/错误类别，单文件 64KiB、一个轮转副本，不记录问题、正文、模型原文或凭据。Start-WebModel.ps1 启用诊断；相关 41 项离线测试通过。已请用户仅重启 Python 加载诊断，Java/Docker/前端保持运行；尚未重试真实任务。

### 17:06 日常升级确认

后续状态：Python 用户启动后 /health 返回 UP；Java 健康与前端 5173 已确认。工具启动 Docker Desktop 后再次弹出 settings-store.json 临时文件 rename “The system cannot move the file to a different disk drive”，引擎未启动。只读检查 Roaming/Docker 与 settings-store.json 未显示符号链接/目录联接，不能确认是 C/E 盘迁移导致，也未修改 Docker 配置或权限。此前记录显示手动启动曾成功，现请用户 Quit 后从开始菜单手动启动；不要恢复出厂设置。搜索未就绪，尚未提交真实研究请求或调用模型。

用户重跑修复后的 Start-MySql.ps1，日志确认 infoexplorer 从 V6 成功迁移至 V7，Java 8080 启动，健康接口返回 UP。已有 17:03 备份大小与 SHA256 校验通过，未做恢复演练。前端已启动于 127.0.0.1:5173（PID 42948，日志 logs/model-frontend.*.log），未创建研究任务。用户再次确认 Agnes 地址 https://api.agnes-ai.cn/v1、模型 agnes-2.5-flash、当前账户免费；已请用户新开终端通过 Start-WebModel.ps1 隐藏输入密钥，尚待 Python 启动。Docker Desktop 已尝试启动，但引擎暂未就绪；本轮尚未调用真实模型。

### 17:03 启动问题与修复

用户运行 Backup-And-Start-MySql.ps1，备份成功：E:\InfoExplorer\backups\mysql\infoexplorer_20261019T090301Z_fe261f113a73441582db03db4c7602f4.sql，94577 字节，SHA256 复核一致（未做恢复演练、未读取备份内容）。Java 随后启动失败，原因是 Spring Boot ApplicationTemp 检查 C 盘既有临时目录所有者与 BUILTIN\Administrators 不匹配；日志无成功迁移记录，不能确认日常 V7。Maven 的 BUILD SUCCESS 是 DevTools 启动失败后仍正常返回，不能据此判断服务启动。

已修改 Start-MySql.ps1：每次使用 E 盘 target/runtime-temp/<随机ID>，并关闭本次 JVM 的 DevTools 自动重启，使启动错误正常反映退出状态；没有修改共享 TEMP 权限或删除旧目录。PowerShell 语法检查通过；相同 JVM 临时目录/DevTools 设置下，隔离 Java/Python HTTP、H2 重启/幂等验证通过（六种模拟结果）。待用户重跑 Start-MySql.ps1，输入 infoexplorer_app 密码；已有刚完成的备份可保留，本轮真实模型未调用。

- 新增 `web-model` 模式与 Python `/internal/v3/research/run`，原 wikipedia/web/v2 行为保留。网页模型独立开关，不因启用 v3 顺带启用 Wiki 模型；v2/v3 共用执行门控。见 [v3 契约](contracts/WEB_RESEARCH_V3.md)。
- Java 有界 HTTP、严格 JSON/重复键校验、会话结构及证据/引用/答案一致性校验；按任务/运行保存 model_session_json，失败保留已读证据，重试保留历史，保存失败不重调外部模型。新增历史 model-session 读取接口，任务返回 modelSession。
- 新增 H2 V9/MySQL V7 迁移，仅新增模式与会话字段，旧迁移不改。临时 H2 已验证；2026-10-19 17:02 用户本机运行 MySQL 测试 10/10 通过，0 失败/错误/跳过，已核对 mysql-live-test.log；包含 V6→V7 旧数据保留、失败/重试/重启读取场景。随机临时库由测试清理，未升级日常库。**日常 MySQL 已于 17:06 备份后升到 V7，Java 正常运行。**
- React 新增“模型研究”，展示计划、缺口判断、补搜理由、停止原因、报告/引用、实际查询与历史快照；失败仍显示证据。无证据不称生成了模型回答。当前是返回后保存/显示过程，没有实时进度或断点恢复。
- 验证：Python **349 passed / 1 skipped**；Java 全量 **87 总数、66 通过、21 跳过、0 失败/错误**（真实 MySQL/模型及显式联调测试默认跳过）。另外 `check_session_java.py --offline` 显式通过六种结果的真实 Java→Python HTTP→临时 H2→重启查询/幂等重放；搜索/模型均为模拟数据，外部调用为 0。
- React lint/build 通过、单元测试 4/4；Edge 浏览器隔离联调 10/10，包括模型补搜、失败证据、引用定位、刷新和历史。浏览器采用真实 Java/H2 加本机模拟 Agent；最终补充无报告提示后再次通过构建/lint/单测，浏览器未重复运行该文案分支。
- 新 `Start-WebModel.ps1` 要求显式传供应商 BaseUrl/AllowedHost/Model，密钥仅隐藏输入，启动时只校验配置结构。脚本已保存但未带真实凭据运行；真实使用前仍需核对供应商和当前计费。Start-WebResearch.ps1 显式关闭 v3，防止继承环境意外启用。
- 本轮未安装依赖、读取真实凭据、调用真实搜索/模型、执行 Git 或升级日常数据库。临时测试服务已停止，日常服务未启动。末次端口检查 8000/8080/5173/18080/4173/3306 均无监听；不能以此声称操作过 MySQL 服务。
- 用户协助待办：17:00 首次测试因 MySQL84 停止而连接被拒绝；用户启动服务后于 17:02 重跑 10/10 通过。用户随后完成备份；修复临时目录归属问题后，日常库已升级 V7 并启动 Java。下一步等待 Python 模型服务启动及搜索引擎就绪，真实模型联合验证仍未执行。
- 仍未实现：语义引用支持性核验、模型供应商信息随每次会话持久化、逐阶段落库/恢复、实时事件/取消传播、多实例、事件追踪和公网部署。

## 前序完成：模型研究会话设计与离线实现

- 已完成 [详细设计](architecture/RESEARCH_LOOP.md)：计划/缺口/报告契约、共享预算、停止原因及后续数据库/页面接入方案。
- 新增 research_session.py、model_completion.py。规划/审核/报告共享最多 3 次模型调用；足够即停、缺口补搜一轮，拒绝重复查询及伪造引用；失败保留证据。认证/配置失败直接停止，规划格式错误可降级原文搜索。
- JsonCompletion 显式创建才工作，无环境自动启用；现有 v2 路由不导入它。既有 bounded_request 增加可选剩余超时，默认调用行为兼容。
- 新增 30 项离线场景，全 Python 340 passed、1 skipped。包含合成提供商响应→规划→搜索/正文夹具→审核/补搜→报告；不是实际模型或网页质量评测。
- 尚未接新 HTTP 契约、Java、数据库和 React；本轮未运行这些层的测试，未调用真实模型/外部搜索、重启日常服务、升级数据库、安装依赖或执行 Git。测试临时本机 HTTP 服务结束后关闭。
- 下一步定稿显式模型研究模式与版本化接口，接双端验证/持久化/页面，再由用户本机输入凭据验证真实链路。语义引用复核、实时进度、取消、检查点恢复和多 Agent 尚未实现。

前序调研：已核对 Anthropic/OpenAI/Google 的公开研究 Agent 策略，形成 [设计建议](research/RESEARCH_AGENT_STRATEGIES_20261019.md)，并写入 BACKEND。当时仅更新文档；本轮新增的离线实现见上方。用户此前要求停止服务：Java、Python、前端、搜索容器和 Docker Desktop 已停止；MySQL 停止因工具权限不足交由用户管理员窗口操作，尚未收到停止结果确认。下方运行状态为当时联调记录。

## 前序完成：网页模式接入 Java、MySQL 与 React（2026-10-19）

- 新任务 researchMode 可选 wikipedia/web；省略仍为 wikipedia，旧任务迁移为 wikipedia。幂等重放同时比较问题、语言和模式；重试继承原模式，不自动重新发送外部请求。
- Java WebAgentClient 限制成功响应 512 KiB/错误 2 KiB，175 秒总等待，拒绝重定向、未知/缺失字段、错误运行身份与证据 hash/关联。当前只接受 direct/web-extract、modelCalls=0、无覆盖审核的 v2 子集。旧 v1 仍只发送 question/language。
- 新迁移 H2 V8/MySQL V6：任务模式与每次运行的完整网页 JSON 快照。成功正文/来源同时写原有列以满足旧状态约束，API 的旧 result 对 web 保持 null；FAILED 的已读资料留在快照，旧迁移未修改。独立历史读取接口 /api/v1/research-tasks/{id}/runs/{runId}/web-result 按任务与运行双重限定。
- React 新增检索方式选择、网页资料/来源、失败和跳过读取记录、上游警告、引用定位与每次历史快照；不会将摘录称为模型报告。默认保留 Wikipedia，用户需选择“网页检索”。仍无实时阶段推送或模型自主补搜。
- Java 普通离线测试 79 总数、61 执行通过、18 跳过（新增真实网页测试前）；随后完整 Java/Python 离线 HTTP 回归 80 总数、67 执行通过、13 跳过。MySQL 用户本机运行 9/9 通过，随机临时库已清理。React lint/build 通过，单元测试 3/3；浏览器隔离联调 8/8，通过真实 Java HTTP/H2 与离线 Agent，不冒充模型测试。
- 新 scripts/check_web_java.py --live：真实 Java HTTP→Python HTTP→SearXNG→受限读取/Trafilatura→临时 H2 文件库→重启查询及幂等重放通过，公开固定关键词 Python http.client documentation，2 个已读来源、4 段证据、模型 0。测试只确认链路，不代表回答质量全面达标。
- 日常 React→Java→Python→SearXNG→MySQL 也已通过一次公开示例：任务 da7e944e-bb89-45f9-aac6-f4b4510d011f，SUCCEEDED，2 已读来源/4 段证据/5 次读取尝试/0 模型调用；刷新和历史快照可读取。另有 2 CONTENT_DISALLOWED、1 CONTENT_ROBOTS_UNSUPPORTED 和搜索部分不可用警告，未绕过限制；coverage=unknown。保留该公开示例任务，不清理日常数据。
- 用户已运行 Backup-And-Start-MySql.ps1：日常库从 V5 升到 V6，启动日志已核对。备份 E:\InfoExplorer\backups\mysql\infoexplorer_20261019T035210Z_e8b617b4fae5482e99148fe0292b7457.sql，82860 字节，SHA256 复核一致；没有执行恢复演练或读取备份内容。
- 运行：Java 8080 由用户窗口维护，Python 8000 与 Vite 5173 由本轮后台启动，SearXNG 8888 保持运行；模型关闭。后台 PID 记录在 logs/web-services.json，日志在 logs（不提交）。没有安装依赖、读取凭据或执行 Git。
- 后续：真实模型规划/基于证据报告及一次覆盖补搜尚未接到网页 HTTP；取消传播、跨实例协调、实时进度、事件追踪和生产部署仍未完成。不要用已有离线执行器测试冒充这些功能已经上线。

## 历史交接：稳定引用、审核快照与 Python v2 HTTP 通过

- 新增 EvidenceRegistry：runId + 来源/段落位置/摘录 hash 生成 evidenceKey，首次选中分配 E 编号；补搜排序变化不重新绑定。有效覆盖审核保存当时的完整证据与判断快照，最终报告拒绝引用已移除证据。
- 新增 /internal/v2/research/run（默认关闭）、Start-WebResearch.ps1、请求/响应 JSON Schema 与 docs/contracts/WEB_RESEARCH_V2.md。此版本只做直接检索与摘录，固定本机 SearXNG，modelCalls=0；不启用模型规划/报告。请求不能覆盖工具或预算，进程内单请求门控，输出上限 512 KiB。旧 v1 未切换。
- 失败 outcome 仍可携带已有证据，HTTP 200 不代表研究成功；明确空结果、局部来源失败和 unknown 覆盖。runId 由调用方提供但不提供幂等缓存，禁止自动重发。
- 完整 Python 离线回归 310 passed、1 skipped；没有安装新依赖。使用工程原有 Uvicorn/HTTP 测试方式。新增启动脚本语法检查通过。
- scripts/check_web_api.py --live 的真实 HTTP→SearXNG→下载→正文提取通过：固定公开关键词，3 已读来源、6 段证据、11921 字节，搜索 1、读取尝试 5、模型 0。另 2 来源 robots 不支持，保留上游部分不可用警告，coverage=unknown。不是质量评测或真实模型联调。
- 临时 Python 服务已关闭，SearXNG 保持运行。未启动 Java/React，未改数据库、迁移或 Git；Java/MySQL/React 测试未运行。实际业务页面仍使用 Wikipedia。
- 下一轮按 v2 契约接 Java 模式/幂等/有界解析/失败成果持久化及 React 展示；模型适配仍待后续。当前只完成 Python 接入基础，不宣称整个应用切换完成。

## 历史交接：SearXNG 本机部署与真实搜索通过

- WSL 3.0.3、Docker Desktop 4.95.0 已由用户配合完成安装及重启，Docker Engine 29.8.2 可用；此前 WSL 未安装的记录已过时。
- Docker 程序在 E:\Applications\Docker；实际虚拟磁盘核实为 E:\DockerData\disk\docker_data.vhdx、E:\DockerData\main\ext4.vhdx；WSL swap 实际位于 E:\WSL\swap.vhdx。系统组件和用户配置仍部分留在 C 盘。后续安装继续优先 E 盘。
- 新增 infra/searxng/compose.yml、settings.yml、Start-Search.ps1、README.md：固定官方镜像摘要、仅 127.0.0.1:8888、限定三搜索源、资源限制及日志轮转；不挂载源码或凭据。实例密钥随机生成并通过环境传入，不输出实际值。
- 真实公开英文 JSON 搜索 10 条；Python 适配器中文查询 5 候选；Bing、DuckDuckGo 可用，Brave 返回限流，结果保留部分上游不可用警告。新增 scripts/check_local_search.py 为显式联网检查，不属于普通测试。
- 宽泛查询候选首次正文读取 CONTENT_TIMEOUT；明确关键词 Python http.client documentation 的真实搜索→受限下载→Trafilatura 成功，取得 5 候选，选中官方文档提取 320 段、未截断。旧固定官方页面复核 313 段也通过。不声称所有网页可读或结果质量全面通过。
- 离线搜索/ContentTool 回归 32 passed；本轮没有改业务模块/接口、Java/React、数据库迁移，没有调用模型或数据库，未运行 Java/MySQL/React 测试；无 Git 操作。搜索容器保持运行，Java/Python/前端未启动。
- 下一步：稳定证据编号与审核快照、网页研究模型适配及 v2 契约，再做 Java 持久化和前端接入。业务页面仍使用 Wikipedia；搜索工具部署通过不等于应用已切换。
- 启停和详细限制见 ../infra/searxng/README.md。Docker 首次由工具启动曾配置重命名失败，用户从开始菜单启动后恢复；根因未证实，没有恢复出厂或删除配置。

## 历史交接：下载与正文提取组合通过

- 新增 app/web_research/content.py，作为现有独立执行器的 ContentTool。下载与提取共用最多 20 秒预算，下载耗尽后不启动解析；内部错误映射为固定 ToolFailure，不重试，不把搜索摘要当正文。
- Document/SourceAttempt 可携带来源元数据：原地址、实际跳转地址与主机、读取时间、HTTP 请求数、提取器、截断、未核验日期及其来源类型、规范化提取文本 hash。hash 使用 UTF-8 紧凑 JSON 段落数组（paragraph-json-v1），只代表保留的提取结果，不冒充完整网页 hash；旧离线 Document 构造仍兼容。
- Python 完整测试 293 passed、1 skipped（真实 Wikipedia 测试未启用），新增 14 项组合测试，含共享截止、错误分类、无重试、重定向信息、日期未知、段落边界 hash、报告失败保留元数据，以及真实 Trafilatura 处理离线 HTML 的执行器测试。
- 2026-10-19 10:08 中国时间，scripts/check_public_download.py --live --extract 对固定 Python 官方公开文档实际验证成功：313 段、未截断、2 次 HTTP 请求、Trafilatura 2.3.1。没有模型、搜索服务或数据库调用；不是 Java/React/真实搜索全链路验证。
- 现有 app/main.py、Java/Python HTTP 契约、数据库迁移与 React 均未改变；新模块未接业务页面。没有安装依赖、读取密钥、启动常驻服务或执行 Git；未运行 Java/MySQL/React 测试。8000/8080/5173 查询无监听。
- 下一步：准备真实 SearXNG 环境，并继续稳定证据编号、审核快照与 v2 契约；来源元数据尚未入库，取消传播及跨进程限流仍未实现。wsl.exe --status 返回 50 并明确提示 WSL 未安装；Docker/Podman 未在 PATH 找到（未据此断言磁盘上不存在安装）。本轮未安装系统组件。

## 历史交接：受限下载器与开源工程调研报告

2026-10-15 13:55 起连续工作，用户已停止服务。本节优先于下面的历史记录。

- 新增 app/web_research/download.py、tests/test_web_download.py 和 scripts/check_public_download.py。仅独立模块与文档改动，没有修改 app/main.py、Java、React 业务实现或迁移；现有运行链路仍是 Wikipedia。
- 下载器校验全部 DNS 结果并连接固定数字 IP，核对对端地址，保留 TLS 主机名校验；逐跳检查、禁止 HTTPS 降级、最多 3 次跳转、最多 12 次 HTTP 请求、HTML 2 MiB/robots 512 KiB、有界子进程。不带本机代理/cookie/认证，不执行网页脚本。
- robots 是保守子集，合并各组非空 Disallow，不处理 Allow 例外；通配符/结束锚点/等待规则拒绝，404/410 可继续，其他失败停止。不支持压缩内容；仅进程内串行与间隔，没有跨进程按域限流、OS 内存沙箱或完整业务取消连接。完整限制见模块 README。
- 最终完整 Python 回归 279 passed、1 skipped（真实 Wikipedia 未启用），下载器 36 项离线测试。含实际流大小/截断、重复传输头、恶意跳转、DNS/连接/TLS、robots 以及子进程创建失败后的锁释放。测试使用 .web-deps 可选提取依赖和本机模拟服务，不访问模型或数据库。
- 14:02 显式真实下载验证：固定 https://docs.python.org/3.13/library/http.client.html，取得 97286 字节 HTML，2 次 HTTP 请求（robots 与正文）。仅证明这个公开页面的下载路径，不是 SearXNG、正文提取、模型或跨服务联调；后续收尾修改只加固清理/歧义响应检查，离线回归已通过。
- 使用 GitHub 插件仓库搜索、代码搜索、文件读取及互联网搜索，审阅 10 个重点项目 README 和相关核心实现，补充 2 个项目文档。报告见 research/InfoExplorer_开源工程调研与实施建议_20261015.docx；可检索文本为 research/OPEN_SOURCE_REVIEW_20261015.md；来源路径和文件 SHA 见 research/source_manifest_20261015.json。未运行外部项目或复现其性能声明，不宣称穷尽 GitHub。
- Word 报告覆盖前后端、研究循环、工具授权、稳定引用与变化追踪；建议保留现有技术分工。报告生成与逐页排版检查记录在 research/README.md，渲染产物放在被忽略的 frontend/test-results 下。
- 本轮没有读取凭据、调用真实模型、访问日常/测试数据库、安装系统组件、修改依赖、执行 Git 或上传操作。用户服务保持停止；Java/MySQL/React 测试未运行，不能称全系统验证。
- 下一批可自主实施：下载与提取组合成 ContentTool，统一失败状态和时间预算；固定证据编号及审核快照；明确 v2 序列化契约。真实 SearXNG 需要运行环境准备，先不以公共共享实例替代自托管验证。日常库迁移仍先临时库验证和备份。
- 收尾检查：Word 最终 15 页、33 个外部 HTTPS 链接，已渲染并逐页核对；7 份入口/交接文档的本地链接无缺失，9 个网页模块语法检查通过。8000/8080/5173 无监听，未启动常驻服务。新增可恢复阶段事件与稳定证据身份的设计约束，仍明确标为待实现。

## 历史交接：全项目设计与网页研究独立模块完成，运行服务尚未切换

2026-10-15 13:07 起的连续工作。本节优先于下面的历史记录；“已验证”仅指注明的验证层级。

- 产品与分期见 PROJECT.md、TASKS.md。新增事件追踪设计 architecture/EVENT_TRACKING.md，以及运行、可靠性和交付设计 architecture/DELIVERY.md。覆盖研究证据、部分失败、主题/轮次/事件修订、幂等调度、备份恢复与单实例边界；这些设计不等于已实现事件追踪或公网部署。
- 通用网页研究设计 architecture/WEB_RESEARCH.md 已补全开源方案与 v2 跨服务契约草案。新增 Python app/web_research：共享预算、URL/DNS 结果纯策略、SearXNG 候选解析、本机 SearXNG HTTP 适配器、Trafilatura 本地 HTML 提取、相关段落筛选，以及可注入工具的一轮补搜执行器。该目录尚未被 app/main.py 的运行路由调用；现有 Java/Python/前端仍为 Wikipedia 路径。
- SearXNG 适配器仅通过本机模拟 HTTP 服务验证。未部署真实 SearXNG、未访问搜索上游。环境检查未在 PATH/常见安装位置发现 Docker/Podman，WSL 状态命令报告未安装；这不是对整机所有目录的穷尽检查。没有安装系统组件。
- Trafilatura 2.3.1 及其依赖安装在项目内被忽略的 .web-deps，未替换现有 .venv 依赖。requirements-web-lock.txt 记录本机 Python 3.13 的解析版本，不是带哈希的跨平台锁。提取测试使用本地合成 HTML，无网页下载。
- 离线验证：新增网页模块测试 143 项通过；含隔离提取依赖的完整 Python 测试 243 passed、1 skipped（真实 Wikipedia 测试未启用）。本机 HTTP 夹具需要允许回环连接的执行环境；最初受限环境的测试已中止，随后在允许环境完整通过。没有真实模型、搜索业务或数据库调用。
- 收尾修正：搜索/提取超时预算计入子进程启动时间，接收结果后再次校验截止；修正后完整 Python 回归仍为 243 passed、1 skipped。进程回收有额外清理耗时，不宣称硬实时或内存隔离。9 份入口/架构文档的本地 Markdown 链接检查无缺失，8 个新增 Python 模块语法检查通过。
- 隔离兼容复核：不加载 .web-deps、仅使用原 .venv 的完整测试为 236 passed、8 skipped（7 项可选提取测试 + 1 项真实搜索）；证明新增模块不要求原运行环境立即安装提取库。两组测试均未调用真实搜索或模型。
- 新增 docs/prototypes/workbench.html 独立交互原型，包含报告/证据/过程、四类结果、引用跳转与追踪预览；所有内容为合成示例，不连接业务 API。Playwright/Edge 7 项检查通过，含键盘操作、390px 布局与无脚本异常；截图在被忽略的 frontend/test-results/prototype。原型不是已发布的 React 功能。
- 已识别但未修复：ResearchExecutor 成功结果保存发生在上游调用异常处理之外，保存失败可能遗留 RUNNING；恢复逻辑仍假定单实例；AgentClient 成功响应反序列化前缺少字节上限；当前 Java 契约不支持无答案的部分成果。具体处理顺序见 DELIVERY.md 和 TASKS.md 的 R1/W5。
- 尚缺安全下载器（DNS 与实际连接绑定、TLS、逐跳检查、robots、传输/解压限制）、真实规划/覆盖/报告适配、审核证据快照持久化、Java v2 契约与迁移、React 接入及真实跨服务验证。现有 URL 策略不能单独宣称已防住 SSRF；子进程超时也不等于 OS 内存沙箱。
- 本轮未编译或修改 Java、未改数据库迁移、未访问或升级日常库、未重启用户服务、未读取凭据、未执行 Git 操作。仅关闭了本轮自己启动的原型临时服务器和测试进程。Java/MySQL/现有 React 回归未运行，因为未改它们的实现；不能把本轮 Python 测试说成全系统验证。
- 下一批：先实现并验证安全下载器，同时解决 SearXNG 运行环境；之后接工具适配与审核快照，再成批修改 Java/Python v2 与前端。涉及用户服务停止、系统交互安装、凭据或日常库迁移时单独交接；其他代码和离线验证可连续执行。

## 历史方向记录：通用网页研究设计阶段

- 用户确认不再将 Wikipedia 作为唯一信息入口，并明确不建立问题集比较结果；此前评测集建议不再作为下一步前置条件。必要契约、迁移、安全与功能测试仍保留。
- docs/architecture/WEB_RESEARCH.md 已按用户要求调整为开源优先：SearXNG + 受控 HTTP 下载 + Trafilatura；Crawl4AI 为后续动态页面候选。取消 Tavily 账户/付费 API 前置要求。直接下载的 DNS/实际连接目标/跳转校验、大小限制为首版必需项；搜索上游可达性及运行成本尚未验证。
- 先实现网页检索基本链路，再实现覆盖判断与一轮补搜；事件追踪另行设计。当前程序仍是既有 Wikipedia 版本，设计中的数据表、API 和预算未实现。
- 本轮只修改文档，没有修改运行代码、数据库或依赖，没有调用模型/搜索业务接口，没有运行测试或 Git 操作，没有停止服务。已查阅公开官方供应商接口文档。
- 后续先检查本机部署环境与 SearXNG 上游可达性，再部署和接入；不假定已安装 Docker/WSL，不要求申请 Tavily Key。本轮核对 SearXNG、Trafilatura、Crawl4AI 官方文档，仅修改设计与状态文档，未安装或验证组件。进入涉及 Java 编译/迁移的实现前通知用户停止 Java，日常库新迁移仍先备份。

## 最近完成验证：真实 Agnes 规划 → Wikipedia → 模型报告 → 日常 MySQL 已跑通

- 2026-10-15 11:23–11:24，用户以 -EnablePlanning 启动 Python 后，提交唯一公开示例“全栈开发和后端开发有什么区别？”，任务 dacfdcfd-d39d-4cd5-861b-826138ed669d，固定幂等键 planning-live-20261015-first。没有自动重试，执行历史仅 1 条。
- SUCCEEDED；plan.mode=model，规划元数据 agnes-2.5-flash / api.agnes-ai.cn / search-plan-v1。实际生成“全栈开发”“后端开发”“前后端分离”三个中文关键词，三个查询均成功、各得到 5 条候选资料，轮流选取并去重后保存 5 条证据。查询与 E1–E5 对应关系保存成功。
- 报告 generation 为同供应商模型、evidence-report-v2，说明本次规划与最终报告均走真实模型。浏览器核对计划、关键词及报告可见；重新加载后任务 JSON 完全一致，无新增执行。没有重启 Java/MySQL，因此不称为本次日常库应用重启验证。
- 质量限制：报告明确说明现有证据没有直接给出全栈定义及与后端的对比，无法完整回答问题。规划 intent 返回英文，关键词和报告为中文。链路验证通过，不等于语义质量、事实准确性或长期稳定性通过。当时提出的固定问题集建议已被用户后续明确取消，不作为当前实施前置条件。
- 本次只创建一个公开示例任务；未读取凭据、未做 Git 操作、未改源码。真实请求账单没有另行读取，实际费用以用户账户为准。Java/Python/前端继续运行，Python 当前已启用规划和报告，后续新建/重试任务可能产生最多两次模型请求。

## 上一阶段状态：日常 MySQL V5 已升级，待真实规划模型启动

- 2026-10-15 11:19:35 完成备份 backups/mysql/infoexplorer_20261015T031925Z_f166fb96568d4093aabad057d86050e2.sql，63022 字节。文件大小和 SHA256 与元数据一致；未读取正文、未做恢复演练。
- 11:19:45 Java 日志确认日常 infoexplorer 从 V4 升级到 V5，健康 UP。没有改写旧报告计划。
- 加载新 Python 代码且明确关闭模型/规划后，公开关键词“软件工程”任务 de583804-d2d0-43ee-8272-a8006bfde73d SUCCEEDED，wikipedia-zh、5 条证据；plan.mode=direct、reason=PLANNING_DISABLED，query 的 E1–E5 对应关系已入库，generation=null。这是实际 Wikipedia 与日常 MySQL 的直接检索验证，不是真实模型规划。
- 验证后已停止 Agent 启动的 Python 进程 72076，腾出 8000 供用户以 Start-Model.ps1 -EnablePlanning 隐藏输入密钥启动；Java 与前端保持运行。真实模型调用尚未发生。
- 已核对脚本供应商 https://api.agnes-ai.cn/v1、模型 agnes-2.5-flash。官方国际站 https://wiki.agnes-ai.com/zh-Hans/docs/pricing 当前列 Flash 输入/输出免费，但中国站定价页通过检索工具无法访问；不能用国际站价格代替中国账户核验，账户此前当天免费账单由用户确认。下一次调用仍以中国账户当前优惠/账单为准。

## 上一阶段：检索规划离线与真实 MySQL 测试通过，待日常库升级及真实模型验证

- 新增可选模型规划：最多三个当前所选语言的关键词，严格结构校验；规划关闭/失败时可见地退回原始问题检索。最多两次模型请求（规划和报告各一次），无自动重试。默认关闭，已有模型启动脚本增加显式 -EnablePlanning。
- 多查询顺序执行、按 URL 去重及轮流选取，最多保存五条证据；每个查询记录成功/失败、资料数量、证据编号。React 和原生页面展示结果中的计划与降级提示。全检索失败或最终报告失败时，暂不保存中间计划，仅保留失败码；尚无实时阶段展示与历史计划查看接口。
- Java/Python 契约新增可空 plan，Java 验证引用/语言/数量/元数据后同事务保存；H2 V7/MySQL V5 增加 plan_json，旧报告不补造计划。Java 已由用户停止，未升级日常 MySQL（仍 V4）；Python 旧实例也未切换新代码，暂不要使用前端提交。
- Python 最终 100 passed、1 skipped（真实搜索未运行）。Java/Python 离线真实 HTTP 与全套 Java：76 tests、0 failures/errors、11 skipped（65 通过），日志 target/planning-offline.log。覆盖模型计划校验/降级、跨服务去重和引用保存、H2 应用重开计划一致性；MySQL opt-in 测试随后通过，见下一条记录。
- 前端类型检查、构建、ESLint、2 项组件测试通过；隔离 Java/H2/模拟 Agent 浏览器 7 项测试通过，包含计划/证据关系和刷新，Java 夹具随后正常关闭。原生页面新增计划展示仅做语法检查，没有单独浏览器验证该展示。
- 2026-10-15 11:18:42：用户执行 Test-MySql.ps1，已核对 mysql-live-test.log 和 Surefire 文本报告：8 tests、0 failures/errors/skipped，BUILD SUCCESS。真实 MySQL 临时库 V4→V5 迁移、旧报告保留、计划持久化及应用重开一致性、既有事务与并发回归通过；测试自建随机库清理无报错。日常 infoexplorer 尚未升级；真实 Agnes 规划输出与规划质量尚未验证。
- 本轮未调用外部搜索或模型，未读取密钥、未安装依赖、无 Git 操作。需要后续 MySQL 临时库测试、日常库备份升级，以及确认供应商/模型/计费后显式真实模型验证。

## 上一阶段结论：语言功能已在日常 MySQL V4 完成真实检索验证

- 2026-10-15 10:59:49 用户脚本完成日常库备份：backups/mysql/infoexplorer_20261015T025934Z_3041eef3a8194463bbcbe38cbd407207.sql，18878 字节。Agent 核对文件存在、大小与 SHA256 一致，未读取备份正文；未进行恢复演练。
- 11:00:00 本地日志确认 infoexplorer 从 V3 成功升级到 V4；Java 8080 健康 UP。重启原 Agent 管理的 Python 8000（新 PID 42000），明确模型关闭；前端 5173 保持运行。
- 浏览器创建中文“人工智能”：eef717f7-581c-4e53-9be6-90490e6f455a，SUCCEEDED、language=zh、provider=wikipedia-zh、5 条证据、generation=null。重新加载详情后语言与 5 条来源链接正常，执行记录仍为 1。
- 经前端同源 API 创建英文 artificial intelligence：e6fd2988-5051-4d38-9b28-71a4ae695708，SUCCEEDED、language=en、provider=wikipedia-en、5 条证据、generation=null。两次检索均经过 Java → Python → 真实 Wikipedia → 日常 MySQL，未调用模型。
- 抽查此前用户无结果任务 a5e6844e-c734-4a7a-9c70-e2f44c6b2904，仍可查询，保留 en / wikipedia-en / 零证据。没有重跑或改写其报告；未对全部旧记录做升级前后逐条比对。
- 本次修改为状态文档更新与服务重启；日常库迁移由用户授权脚本执行，另新增上述两条公开示例任务。没有 Git 操作、凭据读取或模型调用。未重启 Java/MySQL 进行本次日常库持久化测试；临时 MySQL 应用重开测试此前通过。

## 上一阶段：按任务选择检索语言（离线与 MySQL 验证通过）

- 2026-10-15：创建请求新增 language=en/zh，省略或 null 默认 en；React 和原生页面新建默认中文。语言持久化、重试沿用，并参与幂等冲突判断。Python 每请求选择固定 Wikipedia 站点，不再依赖 SEARCH_WIKIPEDIA_LANGUAGE；不会翻译或改写完整问句。
- 新增 H2 V6 / MySQL V4。旧报告不改写；已有 wikipedia-zh 执行记录的任务设为 zh，其余设为 en。旧迁移未修改，日常 MySQL 仍停留 V3，尚未应用 V4。
- React 无证据任务显示“检索完成，未找到可用资料”，可带回主题和语言重新创建；执行状态仍 SUCCEEDED，表示流程完成，不表示找到资料。旧原生页补齐语言选择和无结果提示。
- Python 86 passed、1 skipped；Java 离线回归 73 tests、0 failures/errors、10 skipped（63 通过），包含真实 Java/Python HTTP、中英文、空结果、幂等冲突、重试语言以及 H2 历史数据升级保留检查。日志 target/language-offline.log。初次沙箱内本机测试服务启动受限，使用允许本机服务的执行环境后通过。
- 前端类型检查、构建、ESLint、2 项组件测试通过；隔离 Java/H2 浏览器 6 项测试全通过，包含语言保存、刷新、无结果返回编辑。夹具随后正常退出。真实 MySQL 验证于 2026-10-15 10:58:31 完成：用户交互执行 Test-MySql.ps1，已核对 mysql-live-test.log 与 Surefire 文本报告，7 tests、0 failures/errors/skipped、BUILD SUCCESS。包含 V3 到 V4 的历史语言迁移、旧报告保留、非法语言约束，以及中文任务保存和应用重开查询；既有并发、重试和事务回归通过。仅使用随机临时测试库，清理未报错；日常数据库尚未升级。
- 本轮未调用真实 Wikipedia 或模型，未访问/迁移日常数据库，未读取凭据，无 Git 操作。用户已停止 Java；日常库后续必须先备份再启动迁移。旧 Python 运行实例尚需重启加载新契约，不能直接使用新前端连接旧后端。

## 上一阶段结论：日常 MySQL V3 与 React 真实检索验证通过

- 用户本机执行 Backup-And-Start-MySql.ps1。10:36:42 备份完成，文件位于 backups/mysql/infoexplorer_20261015T023633Z_3c8ef5a83bb04becb400f2f410713bd0.sql，7231 字节；仅核对存在、大小与 SHA256 匹配，未读取备份正文。未做恢复演练。
- 10:37:29 Java 使用 mysql profile，在本机 infoexplorer 成功执行 V2、V3，日志明确由 V1 升级到 V3；10:37:30 启动完成，健康 UP。此前“日常库尚未升级”的记录为历史状态。未声称旧数据逐条比对完成：升级前未读取业务记录，升级后首次列表为空，不能反推升级前一定为空。
- 10:38:45 从 React 页面真实提交公开主题 artificial intelligence，任务 39ee70cb-95b4-41dc-bfb1-cf8adbbab662 于 10:38:48 SUCCEEDED。链路为浏览器 → Java → Python → 英文 Wikipedia → 日常 MySQL。保存 5 条证据，provider=wikipedia-en，generation=null，执行历史只有 1 次。报告为原文摘录，不是模型报告；没有供应商 API 调用。
- 核对证据定位、HTTPS 来源链接、执行历史；完整刷新页面后任务 JSON 一致、5 张证据卡正常显示，刷新未新增执行。本轮没有重启 Java/MySQL，因此不称为重启持久化测试。
- 修正 Ant Design Modal 废弃的 maskClosable 属性为 mask.closable，添加前端 favicon。类型检查/构建、ESLint、2 项组件测试通过。未在日常库运行自动化测试；未重复全套后端测试或付费模型测试。
- 截图 target/react-live-mysql.png 为本轮真实公开资料页面。Java 由用户的 PowerShell 保持运行；Python 8000（模型关闭）、React 5173 由 Agent 启动并保持运行，便于用户体验。备份、数据库、日志不上传；无 Git 操作。
- 尚未验证：备份恢复、升级前后旧记录逐条一致性、此次运行下服务重启、模型报告、长时稳定性及公网部署。下一步先体验页面和摘录质量，再确定中文检索/报告或事件追踪需求。

## 当前阶段：日常 MySQL 与 React 真实检索联调（等待本机凭据）

- 已确认 MySQL84 服务运行。新增 backend/java-api/Backup-And-Start-MySql.ps1：用户在原生客户端隐藏输入 root 密码，mysqldump 导出仅 infoexplorer（含例程、事件、触发器），成功并生成 SHA256 后再调用既有 Start-MySql.ps1，使用项目账户隐藏输入密码启动迁移。8080 已占用时拒绝继续，备份失败不启动 Java；不自动恢复、清理数据库或修复 Flyway。
- 备份位置为 backups/mysql，已加入 .gitignore；备份含本地业务数据，不上传、不展示正文。target/mysql-backup-status.json 只记录路径、大小、哈希和时间；导出成功不等于恢复演练通过。脚本语法检查通过，尚待用户交互执行，未声称备份或迁移完成。
- 本轮已启动本机 Python 8000，明确 INFOEXPLORER_MODEL_ENABLED=false、英文 Wikipedia；已启动 React 5173，代理 Java 8080。未提交研究请求。Java 启动和日常库升级等待用户执行脚本，之后核对备份元数据、Flyway 日志、健康状态和真实浏览器流程。
- 没有读取密钥、备份正文或执行 Git 操作；未运行会改动日常库的自动测试。最终真实检索、报告持久化和旧记录保留尚待验证。

## 最新阶段：React 前端实现与隔离联调完成

- 新增 frontend 独立工程：React 19.3.0、TypeScript、Vite 8.3.4、React Router、TanStack Query、Ant Design 6.6.6；固定直接依赖并生成 package-lock.json，安装时 npm audit 报告 0 vulnerabilities（仅代表当时已知漏洞检查）。未全局安装软件。
- 三个页面已实现：研究创建、分页/筛选列表、报告详情与历史/失败重试。hash 路由支持刷新恢复，页面懒加载；接口查询键隔离不同任务，取消信号传递，终态详情停止轮询。创建键同组件内重发复用，写操作不自动重试；刷新/离开创建页后键不保留。
- 证据引用可定位，外部文本按文本渲染，外链限制无凭据 HTTPS；新页使用 noopener/noreferrer。本机构建预览每响应生成样式 nonce，Ant Design 动态样式兼容 CSP，同源脚本不放行 unsafe-inline。组件布局属性单独放行 style-src-attr。Vite 热更新服务没有同样 CSP；Java 原安全头未修改，统一生产部署仍未实现。
- 类型检查、生产构建、ESLint 均通过；Vitest 2 项安全/证据定位测试通过。页面拆分后最大单个构建 JS 约 336 kB（gzip 112 kB），没有大 chunk 警告；未据此宣称实际加载性能提升比例。
- Test-Frontend.ps1 完整运行通过：自动启动真实 Java API + 随机内存 H2 + 本机模拟 Agent，Playwright 使用本机 Edge，5 项浏览器测试全部通过；覆盖响应丢失重发去重、报告/证据、刷新、重试确认取消/重复点击、历史保留、分页筛选、无效地址、404、重试上限、迟到详情、空列表和 390px 布局。其中异常场景部分通过浏览器拦截模拟，其余通过真实 Java HTTP。并非真实 Python 或供应商联调。
- Java 夹具 17:10:16 正常退出，1 test、0 failures/errors/skipped、BUILD SUCCESS，日志 backend/java-api/target/react-ui-preview.log。最后仅修正按钮文字颜色的 CSS 作用范围，重新构建并单独运行页面导航/截图测试通过。桌面与移动截图已目视检查。
- 截图保存在 backend/java-api/target/react-home-desktop.png、react-report-desktop.png、react-report-mobile.png，报告为离线样例。测试服务已关闭。日常数据库未访问、未迁移，未调用外部搜索/模型，未读取凭据；Java/Python 源码接口未变，未重复运行无关后端全套测试，未做 Git 操作。
- 启动说明见 frontend/README.md。新版本机入口为 5173（开发）或 4173（构建预览），后端默认代理 8080；旧 Java 原生页面保留。下一步由用户体验界面并反馈，再处理日常库备份升级及真实链路体验。登录、事件追踪、Java 合并发布和公网部署仍未实现。

## 最新阶段：正式前端环境核对与第一版设计

- 已验证 Node.js v24.17.0、npm 11.13.0 可运行，PATH 中存在 VS Code 和 Git 命令，无需用户重复下载。未安装依赖或初始化 Git。
- 新增 docs/architecture/FRONTEND.md，明确研究入口、任务列表与报告详情流程，React/TypeScript/Vite 等技术选择、接口状态与测试标准。事件追踪仅保留后续方向，不标记为已实现。
- 此轮为设计与环境检查；React 工程尚未创建，现有原生网页仍是可运行入口。未启动服务、未访问数据库或模型、未运行代码测试。
- 下一步按设计创建独立前端工程并验证依赖、构建与接口适配，再做隔离浏览器联调；旧页面在验收前保留。需核对 Ant Design 样式与现有 CSP 的兼容性。日常 MySQL 升级另行处理。

## 最新阶段：任务管理网页（实现与隔离浏览器验证完成）

- 新增 Java static 下的 HTML/CSS/JavaScript 和图标，无新增依赖或独立前端服务。支持创建、分页筛选、状态轮询、报告与证据、执行历史及确认后手动重试；复用已有 API，Python 与数据库迁移未改。
- 创建请求在本页按相同问题保留幂等键，网络失败可重发，按钮防止重复点击；重试绑定失败 runId。轮询暂停于隐藏页面，使用请求版本避免迟到响应覆盖新选择，未变化的详情不重建 DOM，保留证据展开状态。
- 外部内容均按纯文本显示，证据链接限无凭据 HTTPS 并设置 noopener/noreferrer。新增浏览器安全响应头，包括同源 CSP、nosniff、no-referrer 和 no-store；不替代鉴权，仍仅供本机使用。
- 16:05:30 Java 离线全套：69 tests、0 failures/errors、13 skipped，56 通过，日志 backend/java-api/target/web-test.log。跳过真实 MySQL/模型/Python 可选联调及需显式启用的网页预览测试。JavaScript 语法检查通过。
- 16:10:37 隔离网页预览测试正常退出：1 test、0 failures/errors/skipped，日志 target/ui-preview.log。浏览器连接真实 Java API、随机内存 H2 和本机模拟 Agent，验证创建到完成、失败后重试、确认取消、重复点击、分页与筛选、已入库但响应丢失后幂等重发、恶意 HTML 文本不执行、390px 移动布局及轮询保留展开项。模拟 Agent 不是真实 Python 或供应商验证。
- 截图保存在 target/ui-desktop.png、target/ui-mobile.png，仅包含离线测试数据。临时预览服务与内存库已关闭；日常 MySQL 未修改，真实模型未调用。无 Git 操作，未安装依赖或读取凭据。
- 下一步：备份并升级日常开发库，再启动本机 Java/Python，通过网页体验真实检索。现有日常库最后确认 V1，V2/V3 尚未在该库应用；本轮完成不代表日常服务已经上线。登录、事件追踪、报告语义评估及生产部署仍未实现。

## 最新阶段：失败任务手动重试（离线与真实 MySQL 验证完成）

- 新增 POST /api/v1/research-tasks/{id}/retry，请求 failedRunId。按失败执行去重；事务锁定任务，同一失败并发重复提交只排队一次。旧请求不会再次触发后续失败的重试，已成功/运行/排队的执行不能发起新重试，每任务最多 5 次执行。
- 新增 GET /api/v1/research-tasks/{id}/runs，保留最多 5 条执行历史。详情只关联当前次数，重试 PENDING 时清空当前执行字段；旧失败、错误码和时间保留。迟到结果及新一轮证据写入异常不能破坏历史。
- 新增 H2 V5 / MySQL V3 Java 迁移，旧 SQL 不改；添加 attempt_no/retry_accepted 并替换原单列唯一约束，保留外键。修正了 H2 旧外键共享唯一索引导致第二次执行插入失败的问题，隔离测试通过；日常库未应用迁移。
- 15:55:16 离线跨服务全套验证通过：67 tests、0 failures/errors、8 skipped，59 通过。覆盖重试 HTTP、8 路并发重复提交、失败执行去重、5 次上限、事务回滚、旧失败迁移、排队重开、中断恢复和历史重开；真实本机 Python HTTP 使用固定样例验证失败→重试→成功，未访问外网或真实模型。日志 target/retry-offline.log。
- 真实 MySQL 验证于 15:58:42 完成：核对 mysql-live-test.log 与 Surefire 文本报告，6 tests、0 failures/errors/skipped，BUILD SUCCESS，测试耗时 4.437 秒。并发重试、失败历史、5 次上限、重开持久化及含旧失败记录的 V2→V3 迁移通过；既有约束、分页和业务事务回归通过。
- 6 个随机临时库的清理钩子均未报错，未修改日常开发库；日常库仍需在实际启用时应用新增迁移。未读取密钥、未安装依赖、未操作 Git。Python 生产代码未修改，仅扩展离线联调样例；未进行真实模型重试调用，执行计划、负载、多个 worker 及真实模型重试计费未验证。

## 最新阶段：任务列表（实现、离线及真实 MySQL 验证完成）

- 新增 GET /api/v1/research-tasks，支持 page（0–10000）、size（默认 20，上限 100）、status（四种任务状态）。固定创建时间/id 倒序，返回概要 items/page/size/hasNext，不加载报告和证据、不调用 Python 或模型。
- 参数化查询，严格校验空值、重复、未知及越界参数，错误统一为 400 / INVALID_QUERY。OFFSET 分页不提供跨请求快照或总数，数据变化可能造成跨页重复/遗漏。
- 新增 H2 V4 与 MySQL V2 索引迁移；旧迁移未修改。本轮未启动日常应用、未向日常数据库应用迁移，未做 Git 操作。
- Java 离线回归于 15:43:29 完成：58 tests、0 failures/errors、9 skipped（49 通过）。包含 22 项新增 HTTP 测试；验证空列表、默认参数、越界空页、稳定排序、四种筛选、错误参数及概要响应，现有 H2 历史库迁移回归通过。日志 target/task-list-test.log。
- 真实 MySQL 验证于 15:46:02 完成：核对 mysql-live-test.log 及 Surefire 文本报告，4 tests、0 failures、0 errors、0 skipped，BUILD SUCCESS，测试耗时 2.961 秒。新增 V2 索引迁移、分页/筛选/同时间排序/空页及索引存在性检查通过，原约束、并发、事务及重开持久化回归通过。
- 4 项测试各自建立随机临时库并清理，清理钩子未报错，未修改日常开发库。验证的是临时库中从 V1 到 V2 的连续建库迁移，未单独验证含大量既有数据的 V1 库升级、执行计划或性能。Python 契约与实现未变，未重复调用模型或运行 Python 测试。
- 本阶段完成；下一阶段建议单独设计失败重试，本轮未实现重试、前端、鉴权或生产性能优化。

## 上一阶段验证结论（15:34:41，Asia/Shanghai）

MySQL + 真实模型联合验证已通过。核对本地 mysql-model-test.log 与 MySqlLiveModelIntegrationTests 文本报告：1 test、0 failures、0 errors、0 skipped，BUILD SUCCESS，测试耗时 8.883 秒。

- 实际链路：Java HTTP 创建任务 → 后台 worker → Python → Wikipedia → Agnes agnes-2.5-flash → MySQL 临时库。成功保存 5 条证据、报告及 evidence-report-v2 模型元数据。
- 幂等重放返回相同任务，数据库仅 1 条任务、1 条执行记录；关闭并重新打开 Java 应用上下文、连接同一 MySQL 库后，HTTP 查询结果完全一致。没有重启 MySQL 服务器或操作系统。
- 测试仅使用本次随机生成的 infoexplorer_test_ca70dfa84a9c47de9bdbf089a7fd2e0a 库；清理钩子执行 DROP 且未报错。未向日常开发库写入测试数据，未读取凭据，未做 Git 操作。
- 之前两次失败保留为历史记录。v2 补齐提示词约束后本次联合验证成功，不代表长期稳定性、语义准确率或并发性能已验证；本次实际账单未另行核对。

下文按阶段保留过程记录，“待验证/未通过”等表述描述当时状态，以本节最新结论为准。

## 最新阶段：MySQL 8.4 适配

用户已安装并配置 MySQL。只读检查确认 MySQL84 服务运行，客户端版本 8.4.11；未读取配置文件中的密码或执行密码猜测。

- 已新增 MySQL JDBC / Flyway MySQL 依赖、mysql profile 和专用 db/mysql 迁移；默认仍是 H2，既有 V1–V3 未修改，未自动迁移旧数据。
- 领取查询改为兼容两种数据库的 LIMIT 1。MySQL 使用 InnoDB、utf8mb4_0900_bin、MEDIUMTEXT、显式外键和 CHECK。
- 新增 MySqlIntegrationTests：随机独立测试库，验证约束、Unicode、幂等大小写、8 路并发、事务回滚、持久化重开与中断恢复。
- 新增 Test-MySql.ps1，由用户在本机隐藏输入密码并执行；密钥/密码不进入聊天、源码或命令参数。脚本日志位于 backend/java-api/target/mysql-live-test.log。
- 编译与普通回归已通过：34 tests，0 failures/errors，7 skipped（3 个 MySQL 测试及 4 个已有可选外部联调），退出码 0。日志 target/mysql-adaptation-test.log。本轮 Python 代码未变，未重复运行 Python 单测。
- **真实 MySQL 验证已通过（2026-10-14 14:55:54，Asia/Shanghai）。**用户在自己的终端运行交互脚本；Agent 核对本地 mysql-live-test.log 与 Surefire 文本报告，3 tests、0 failures、0 errors、0 skipped，BUILD SUCCESS，构建耗时 4.246 秒。
- 已验证真实 MySQL 8.4：Flyway 建表与重复启动校验；外键/CHECK/唯一约束；中文与 emoji；幂等键大小写区分；8 路相同请求只创建一个任务、8 路竞争只领取一次；证据插入失败整笔业务事务回滚；应用关闭重开后报告与模型元数据一致；中断恢复后拒绝迟到结果。
- 3 个测试各自创建随机测试库，AfterEach 关闭连接池并删除本次创建的库，清理阶段无错误。没有重启 MySQL 服务器，不能把应用重启测试称为数据库服务器重启测试；也没有进行 MySQL + Python + 真实模型的联合端到端测试或性能压测。
- 用户已创建开发库 infoexplorer、账户 infoexplorer_app@localhost 并授予库级权限。2026-10-14 15:08 的本地启动日志确认 Java 激活 mysql profile、建立 MySQL 连接，Flyway 在该开发库成功执行 V1 迁移。随后实际查询 http://127.0.0.1:8080/actuator/health 返回 UP。当前运行实例已使用 MySQL；未指定 profile 的默认配置仍为 H2。
- Start-MySql.ps1 已由用户本机隐藏输入项目账户密码后实际运行，项目账户建表权限和健康检查验证通过，日志 target/mysql-startup.log。本次核验未提交研究任务，未验证 MySQL + Python + 真实模型联合链路。未读取或保存密码，没有 Git 操作。

以下为此前模型阶段记录。

### MySQL + 真实模型联合验证过程（最终结果见顶部）

- 新增 Start-Model.ps1，本机隐藏输入 Agnes Key 后以已确认的中国站地址和 agnes-2.5-flash 启动 Python；不保存密钥。
- 新增 Test-MySqlModel.ps1 与 MySqlLiveModelIntegrationTests：复用已有真实 HTTP/worker/模型元数据/幂等/应用重开查询检查，仅创建并清理本次随机 MySQL 测试库。不会连接日常开发库，不停止用户 Java 服务；测试账户需可创建和删除临时库。
- 两个 PowerShell 脚本语法检查通过。新增 Java 测试编译成功，默认运行 1 项、跳过 1 项，证明未显式启用时不执行；尚未运行真实联合链路，不能记作通过。等待用户在本机启动 Python 并输入数据库测试凭据。
- 后续实际运行于 2026-10-14 15:20:22 结束：1 test、1 failure、0 errors、0 skipped。MySQL 连接及临时库 V1 迁移成功；研究任务返回 FAILED / MODEL_INVALID_RESPONSE，未进入成功报告入库及重开校验。测试清理阶段未报错，未操作日常开发库。
- 原代码未记录校验失败细分原因，无法从这次日志确定是响应格式、截断还是内容约束。现补充固定类别 MODEL_RESPONSE_REJECTED reason 日志，不记录原始回复、请求、异常详情或凭据；同时将非对象 message 等异常结构统一为原有安全错误码。未放宽引用校验、未增加重试、未修改模型提示词或接口契约。
- Python 离线测试 70 passed、1 skipped（真实搜索未运行）。首次沙箱内临时 HTTP 服务启动受限，允许本机测试服务后重跑通过。等待用户重启 Python 使诊断生效；本轮尚未再次调用真实模型。
- 用户随后重启 Python，Agent 对公开主题 artificial intelligence 进行一次直接 Python HTTP 诊断调用，成功返回 wikipedia-en、5 条证据、非空报告，以及 agnes-2.5-flash / api.agnes-ai.cn 元数据。没有写入数据库，没有自动重试。这次未复现 MODEL_INVALID_RESPONSE，不能认定原问题已修复或断言其具体原因；MySQL 联合验证及重开查询仍待重新运行。
- 15:29:53 第二次 MySQL 联合验证仍为 1 failure、0 errors，用户 Python 窗口诊断为 report_limits。这只能定位到 claims/limitations 的类型或条数，不能确认具体哪一字段不合格。核对发现原提示词未明确 limitations 必须为 1–4 条，也遗漏部分已存在的文本约束。
- 已补齐提示词约束并升级 evidence-report-v2；Java 接受 v1/v2 元数据保留旧版本兼容，真实模型测试期待 v2。未放宽解析规则、未截断模型结论、未增加重试；将报告限制诊断拆为 claims_type/claims_count/limitations_type/limitations_count。
- 验证：Python 77 passed、1 skipped；Java/Python 固定样例真实 HTTP 联调 35 tests、0 failures/errors、5 skipped（30 通过，真实 MySQL/模型相关测试未运行），日志 target/prompt-v2-offline.log。这是离线样例联调，不是供应商验证。等待用户重启 Python 加载 v2；本轮未调用真实模型，MySQL 联合验证仍未通过。

## 当前阶段：可选模型报告（2026-10-14）

最近补充：用户重启 Python 后，Agent 单次直接调用公开主题 artificial intelligence 成功，返回 5 条 wikipedia-en 证据、非空报告及 agnes-2.5-flash / api.agnes-ai.cn / evidence-report-v2 元数据。已确认新提示词实际生效且本次回复通过校验；没有写数据库或自动重试。这不证明长期稳定性，MySQL 联合链路仍需用户本机输入测试凭据后验证。

目标：在已检索证据上生成带引用的报告。离线开发验证已完成；随后在用户授权下，通过用户自行配置密钥并启动的 Python 服务完成一次真实模型测试，Agent 未读取密钥值。

- Python 新增可替换 ReportGenerator，默认关闭，开启时使用环境变量中的 HTTPS 域名、模型和密钥；每任务一次请求，无重试或工具调用。
- 仅发送问题及证据 ID、标题、摘录。请求 32 KiB / 响应 64 KiB、输出 max_tokens=1200，单进程最多一个并发模型调用。模型网络工作在独立子进程执行，20 秒等待预算到期后终止；不继承系统代理或跟随重定向。
- 结构化输出逐条检查证据编号、数量和长度；拒绝未知引用、工具调用、截断和畸形响应。引用存在性不是语义事实核验。零证据不调用模型；支持有证据但不足以形成结论时拒答。
- Java 保存 generation 元数据（请求模型名称、域名、提示词版本、请求体哈希），继续保持 provider 为检索源；V3 增加元数据列，V1/V2 原样保留。历史结果 generation=null。
- Java 白名单接收 MODEL_* 安全错误码并保存 FAILED；模型失败不会伪装成功，当前失败任务不保存检索中间证据。
- Java 默认只监听 127.0.0.1，研究读取超时调整为 60 秒、正常关闭等待 70 秒；旧聊天仍为模拟实现。
- 新增离线跨服务脚本 tests/run_offline_contract.py，真实运行 Java/Python HTTP 链路和隔离数据库，外部搜索及模型使用固定样例。

### 当前阶段验证

| 范围 | 结果 |
|---|---|
| Python 离线全套 | 66 passed，1 skipped（显式跳过真实 Wikipedia 外网测试），退出码 0 |
| Java 全套，启用离线 Python 联调 | 30 tests，0 failures，0 errors，0 skipped，退出码 0 |
| 跨服务 | Java → 真实 Python HTTP 服务 → 固定搜索/模型样例 → H2 保存和查询；模型超时/限流/未知引用均保存安全失败 |
| 持久化 | 临时文件库重启保留 generation 和证据；V1 升级到 V3 后历史结果仍可读取 |
| 超时隔离 | 实际启动测试子进程，预算到期后终止并确认无遗留子进程 |

Java 最终日志：backend/java-api/target/model-contract-test.log；测试报告：backend/java-api/target/surefire-reports。临时 Python 服务与测试子进程已结束。

最初沙箱内测试遇到本机服务启动及 Maven 缓存访问限制；获准扩大执行权限后使用已缓存 Maven 离线执行成功，无新增依赖。H2/Flyway 版本兼容提醒与 Mockito 动态 Agent 提醒仍存在，未导致失败。

### 真实模型验证补充（2026-10-14 11:35，Asia/Shanghai）

用户提供中国站价格页截图，agnes-2.5-flash 输入及输出当前标价均为 ¥0，并授权试调用。用户在自己的 PowerShell 进程配置密钥、启用模型并启动服务；Agent 未读取密钥值，仅通过 127.0.0.1:8000 的研究接口提交 artificial intelligence。

- Python → Wikipedia → Agnes 中国站真实请求成功，工具整次请求约 4.94 秒（包含本机请求和检索，不是模型单独耗时）。获得 5 条证据和 7 条带引用结论，通过结构与引用 ID 校验。
- 返回 generation：model=agnes-2.5-flash、host=api.agnes-ai.cn、promptVersion=evidence-report-v1；inputHash=7c7058529c98bcabaccaec8a63460cc869f1758d81c06c19a0572eb4740a1936。
- 本次只验证 Python 真实供应商链路，未调用 Java 或写入数据库；未验证账户实际扣费、token 用量、质量准确率或长期稳定性。模型名称是配置的请求名称，并非独立验证的实际模型身份。
- 初次沙箱内调用因套接字权限失败，未到达服务；扩大执行权限后的一次请求成功，没有自动重试模型。用户启动的服务保持运行，本轮不停止它。
- 检索包含一条同名电影结果，提示后续需要相关性筛选；报告未引用该条。引用校验通过不代表事实核验通过。

本轮没有源码修改、依赖安装、日常开发数据库操作、Git 初始化、提交或上传；仅更新项目说明和验证状态。

### 下一步（未完成）

1. 固定证据样例评估结论与引用的语义一致性；当前只检查格式和引用 ID 存在性。
2. 改进检索相关性与外部限流体验，独立设计缓存、重试预算及失败证据保存；目前均未新增。

### 完整真实链路验证（2026-10-14 11:40，Asia/Shanghai）

用户提供上一轮实际账单截图：agnes-2.5-flash 消费金额 0 分，输入 1050 tokens、输出 364 tokens、缓存命中 0，状态成功。该截图验证的是上一轮调用，不是永久免费保证，也不是本轮新请求的账单核对。

新增 LiveModelIntegrationTests，仅在 INFOEXPLORER_TEST_AGENT_MODE=live-model 和本机 Agent URL 同时设置时启用；使用 test profile、JUnit 临时 H2 文件库、随机 Java 端口。复用用户已启动的 Python 服务，不读取其密钥或改动进程配置。

- 首次测试因 Wikipedia 返回限流而 FAILED / SEARCH_RATE_LIMITED，未进入模型生成；失败日志 target/live-model-test.log 保留。没有修改代码掩盖该失败。
- 离线回归：31 项，30 通过、1 跳过（真实模型专用测试），0 failures/errors，退出码 0；日志 target/live-stage-offline-test.log。
- 冷却超过一分钟后人工编排重试一次：真实模型专用测试 1 项通过，0 failures/errors/skipped，退出码 0；日志 target/live-model-retry-test.log。
- 通过 HTTP 创建公开问题 artificial intelligence；真实后台 worker 自动领取执行；任务 SUCCEEDED、5 条证据及 agnes-2.5-flash / api.agnes-ai.cn 元数据成功入库和查询。
- 相同幂等键重放返回同一完整任务；数据库仅有 1 条任务和 1 条执行记录。关闭 Java 应用后重开同一临时数据库，关闭 worker 的情况下查询结果与关闭前完全相同。
- 本轮 Python 源码未修改，未重跑无变更的 Python 单测；上次离线记录仍为 66 passed / 1 skipped。模型语义准确率、长期稳定性及本轮请求账单尚未验证。
- 测试启动的 Java 应用已关闭，临时文件库由 JUnit 管理清理；用户的 Python 服务保持运行。未操作日常开发数据库，未安装依赖，未初始化 Git、提交或上传。

本轮修改范围仅为新增真实联调测试与项目说明/状态文档，业务源码与已应用数据库迁移未修改。

### 当前边界

没有前端、鉴权、任务队列容量限制、严格整任务截止时间、取消、失败中间证据保存、平台账单硬限额或生产隔离。模型网络预算不包含前面的检索；Wikipedia 仍采用单次网络操作超时。并发限制仅适用于一个 Python 进程；当前只支持单 Java 实例和单 Python worker。输出应按纯文本渲染，不能当作可信 HTML。未验证打包或新机器环境复现。

以下保留上一阶段的历史记录，时间与超时配置以当前阶段和 README 为准。

## 上一阶段完成情况：Wikipedia 检索

研究任务已经从模拟回答推进到真实 Wikipedia 检索。Java 继续管理任务和持久化，Python 负责检索及正文导言提取；尚未接入模型。

- Python 新增 /internal/v1/research/run，使用公开 MediaWiki API，一次检索最多 5 条，提取最多 800 字符/条的纯文本摘录，按排名排序、去重。
- 当前默认英文 Wikipedia；可通过 SEARCH_WIKIPEDIA_LANGUAGE=zh 切换中文。并非全网或新闻搜索，不自动拆解研究问题。
- 研究结果新增 provider、query、retrievedAt、evidence；证据保存 id、url、title、excerpt、retrievedAt、contentHash。摘录汇总使用 [E1] 等编号引用。
- Java 校验证据完整性、来源对应关系、ID/URL 唯一性、HTTPS 地址和 SHA-256 摘录哈希。
- 新增 Flyway V2 迁移：报告元数据、research_evidence 表；证据、报告和任务成功状态在同一事务保存，写入失败会整体回滚。
- V1 保持原样。旧结果继续可读，标为 legacy-mock，证据为空、获取时间为空，不编造来源。
- 失败任务可保存 SEARCH_TIMEOUT、SEARCH_UNAVAILABLE、SEARCH_RATE_LIMITED、SEARCH_INVALID_RESPONSE；不会把搜索失败回退为模拟成功。
- 零条有效摘录返回明确的无结果说明，不推断“相关资料不存在”。
- 原同步聊天接口仍保留模拟回答，不访问搜索源、不保存任务。

## 最终验证

| 范围 | 结果 |
|---|---|
| Java 全套，启用真实 Python 联调 | 28 tests，0 failures，0 errors，0 skipped |
| Python 全套，INFOEXPLORER_LIVE_SEARCH=1 | 32 passed，0 skipped |
| 真实外网链路 | Java → Python → Wikipedia → H2 证据入库 → 按任务 ID 查询，通过 |
| 数据兼容 | 从仅含 V1 的文件数据库升级至 V2，原结果仍可读取，通过 |
| 事务与恢复 | 证据写入异常整体回滚、重启保留结构化结果、既有幂等及领取竞争测试，通过 |

Java 测试报告位于 backend/java-api/target/surefire-reports，最终完整日志为 backend/java-api/target/evidence-final-test.log。Python 测试退出码为 0。

所有数据库测试使用独立内存库或临时文件库；未创建或打开日常开发数据库。真实检索仅使用 artificial intelligence 这一公开示例关键词。本轮临时服务均已关闭，没有提交私人业务数据。

### 本轮发现并处理的问题

最初采用的 7 秒外网超时在完整联调中出现 SEARCH_TIMEOUT。调整为 Python 搜索网络操作超时 20 秒、Java 研究专用读取超时默认 30 秒；旧聊天仍为 10 秒，新增测试验证二者独立。正常关闭等待调度任务最多 40 秒。最终全套测试通过，但外网及上游波动仍可能导致任务失败，不保证每次检索成功。

第一次外网探测曾遇到自动权限审批超时；按工具允许重试后成功，无遗留授权阻碍。

## 已知边界

- 当前是百科检索和确定性摘录汇总，非 LLM 分析报告、事实核验或实时事件追踪。
- 获取时间不是文章发布时间；摘录哈希只校验保存内容，不证明来源真实性。未抓取完整网页、未固定条目历史版本。
- 外部内容是不可信数据；前端必须文本显示或转义，不能直接当 HTML。抓取只指向固定 Wikipedia API，不跟随重定向或抓取结果中的任意 URL。
- 搜索网络超时及 Java 读取超时都不是严格的总执行截止时间。暂未实现取消、重试、缓存、并发检索和成本预算。
- 当前单实例、单后台工作线程、H2 文件模式，无鉴权、分页任务列表或生产部署。
- 数据库故障可能留下 RUNNING，需要恢复数据库并重启后标记为中断失败；没有分布式 exactly-once 保证。
- H2/Flyway 版本提示和 Mockito 动态 Agent 提示仍存在，未导致测试失败；未做负载测试、断电测试或生产数据库适配。
- 未单独验证打包、spring-boot:run 或新机器环境复现。未新增 Python 第三方依赖。

## 下一步建议（未实施）

1. 选择并配置模型服务，以现有证据生成带引用的报告，确保每项结论能回到具体证据。
2. 建立固定问题与资料样例，评估引用正确率、无证据拒答、耗时及成本。
3. 按产品方向增加通用网页/新闻搜索适配器；Wikipedia 不能替代这些来源。
4. 后续再增加主题订阅、跨轮事件归并与变化识别。

## Git 与命名

仍未初始化 Git、提交或上传。InfoExplorer 目录/Java 包与 InsightFlow Python 标题保持原样。

## 2026-11-07 GitHub 托管准备

用户授权初始化 Git 并创建独立私有仓库 Jeoily/InfoExplorer。上传源码、测试、文档及可复现配置；按 .gitignore 排除密钥、本机数据库、备份、日志、依赖与历史本机目录快照。首次推送结果以远端核验为准；本次不修改业务实现、不启动服务或迁移数据库。

