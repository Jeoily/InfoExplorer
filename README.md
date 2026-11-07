# InfoExplorer

面向信息探索与事件追踪的 Web 应用。当前支持通过网页创建研究任务、查看列表和证据报告、手动重试失败任务及查看执行历史。后台可选择 Wikipedia 或公开网页检索；Wikipedia 可选模型报告默认关闭；Java → Python → Wikipedia → Agnes 中国站 → 临时数据库入库/重启查询链路已通过。Python 服务暂保留历史标题 InsightFlow；产品名称尚未统一。

## 2026-10-22 追踪功能

新增 React“持续追踪”：主题管理、手动检查、轮次历史、资料变化与上次摘录、暂停/归档、默认关闭的低频自动网页摘录。H2 V10 / MySQL V8；日常升级必须先隔离测试和备份。该时间线记录资料发现/修订，不自动认定事件发生或事实成立。最新部署与真实研究验证见 [CURRENT_STATE](docs/CURRENT_STATE.md)，接口见 [TRACKING_V1](docs/contracts/TRACKING_V1.md)。

用户一次输入凭据后可通过 [无人值守管理](docs/UNATTENDED.md) 运行固定测试、备份、部署和重启操作；所有密钥仍只在本机进程内存，默认测试不调用外部模型。

## 结构

2026-10-25：完成单实例[长任务执行控制](docs/contracts/EXECUTION_CONTROL_V1.md)：阶段显示、取消、刷新恢复、服务中断识别、手动重试资料复用及提交去重。隔离 HTTP/浏览器故障验收与 MySQL 临时库迁移通过；日常库尚未升级到本轮 V9。恢复复用搜索/正文，模型步骤重新执行。

2026-10-25：完成本轮[真实研究质量迭代](docs/QUALITY_2026-10-25.md)，改善中英文选段和原文引用。用户接受当前模型仍可能夸大证据支持范围，报告页已明确展示该限制；独立模型复核只保留为隔离实验，不宣称事实核验能力。

2026-10-25：完成第三阶段“前端展示与整体验证”。隔离网页新增阶段复查、输入输出查看及三个离线复查按钮；已验证成功/失败/补搜/空资料、历史刷新和手机布局。三阶段是开发调试能力完成，不代表真实回答质量达标。入口见[阶段复查说明](docs/RESEARCH_REPLAY.md)。

2026-10-25：隔离环境新增[阶段记录与离线回放](docs/RESEARCH_REPLAY.md)。可复查失败阶段、重选保存正文、校验或通过注入模型重生成固定证据报告。默认仅合成样例验证，不代表真实回答质量达标。

2026-10-25：新增[隔离调试环境](docs/DEBUG_ENV.md)。独立端口、会话 H2、独立 Java 构建；默认固定样例，无需密码或外网。可自动启停/重启，日常服务不受管理；不是新增质量验收或部署。

2026-10-19 新增“模型研究”（web-model）代码路径：计划→检索→缺口判断→必要时补搜→带引用报告，已完成模拟搜索/模型的 Java/Python HTTP、持久化及 React 验证。需要独立启用 v3，新增 H2 V9/MySQL V7 迁移；日常部署和真实模型验证进度以 CURRENT_STATE 为准。不要直接启动日常 Java 来跳过隔离迁移测试及备份。见 [v3 接口与启用说明](docs/contracts/WEB_RESEARCH_V3.md)。

2026-10-19：Java/React 已接入可选网页检索模式，日常 MySQL 已备份并升到 V6。网页模式通过 SearXNG 发现网页、受限读取正文并保存证据，目前只直接检索和摘录，不调用模型。默认仍为 Wikipedia；请在 React 创建页选择“网页检索”。见 [v2 契约](docs/contracts/WEB_RESEARCH_V2.md)、[运行说明](frontend/README.md) 与 [最新验证记录](docs/CURRENT_STATE.md)。

整体目标见 [docs/PROJECT.md](docs/PROJECT.md)，实施顺序见 [docs/TASKS.md](docs/TASKS.md)。新增 [工作台交互原型](docs/prototypes/workbench.html) 可直接在浏览器打开：仅使用虚构示例，不访问业务服务。

- `backend/java-api`：Java 21、Spring Boot 4.1.1，业务 API、后台任务、Spring JDBC 持久化、Flyway 迁移及 Agent 调用。
- `backend/agent-service`：Python / FastAPI，Wikipedia 检索与摘录服务；旧聊天路径保留模拟回答。
- `backend/java-api/src/main/resources/static`：原生 HTML/CSS/JavaScript 任务网页，由 Java 同源提供，无需安装前端依赖。
- `docs/architecture/BACKEND.md`：当前接口和后续后端设计。
- `docs/architecture/WEB_RESEARCH.md`：通用网页研究设计；网页摘录已接入业务接口，模型规划/覆盖补搜尚待接入。
- `backend/agent-service/app/web_research`：预算、URL 策略、候选解析、段落筛选、离线协调器、本机 SearXNG 客户端、受限下载器和本地 HTML 提取；已接默认关闭的 v2 路由，详见该目录 README。
- `docs/architecture/EVENT_TRACKING.md`：长期追踪设计；已实现的资料追踪 v1 边界见 docs/contracts/TRACKING_V1.md。
- `docs/architecture/DELIVERY.md`：可靠性、测试、迁移和部署边界。
- `frontend`：React / TypeScript 前端，启动与隔离联调见 [frontend/README.md](frontend/README.md)。
- `docs/architecture/FRONTEND.md`：正式前端的页面、技术选型与验收设计。
- `docs/CURRENT_STATE.md`：实际完成状态、验证记录及下一步。
- [开源工程调研报告](docs/research/InfoExplorer_开源工程调研与实施建议_20261015.docx)：10 个重点项目的前后端、Agent、搜索与追踪实现比较；[文本版](docs/research/OPEN_SOURCE_REVIEW_20261015.md)。

2026-10-15 当前日常库已升级 MySQL V5，并完成过真实 Agnes 规划与 Wikipedia 报告验证。2026-10-19 日常库已升 V6 并接入网页摘录模式；最新验证见 docs/CURRENT_STATE.md。下文 V1–V4 描述为历史记录，不代表当前数据库版本。

## 可选检索规划（部署与验证状态见 CURRENT_STATE）

2026-10-15 已在日常 MySQL V5 完成一次真实 Agnes 规划、三关键词 Wikipedia 检索及模型报告验证，保存五条证据，刷新查询一致。本次资料不足以完整回答对比问题；流程通过不代表回答质量达标。

设置 INFOEXPLORER_PLANNING_ENABLED=true 且启用模型后，会先生成最多三个同语言关键词，检索后合并最多五条证据。计划不合格或模型不可用时退回直接检索，页面说明原因。默认规划关闭，不自动调用供应商。Start-Model.ps1 的 -EnablePlanning 参数可显式启用，需先核对供应商当前计费并在本机隐藏输入密钥；每次任务最多规划和报告各一次模型调用。新增迁移需先停止 Java、备份并验证，不能直接启动日常库。计划只在结果返回后显示，失败任务暂不保存中间计划。

## 网页使用

新版 React 页面已在独立 frontend 目录实现。进入该目录执行 `npm.cmd run dev`，打开 http://127.0.0.1:5173/#/research/new 。通过代理调用本机 Java 8080，真实检索仍需 Python。此命令只启动前端，未自动启动后端或升级数据库。新版未覆盖下述 Java 原生网页；本轮通过隔离数据库与模拟 Agent 的真实 Java HTTP 浏览器联调，未重复进行真实模型调用。

Java 启动后打开 `http://127.0.0.1:8080/`。网页提供创建、每页 10 条的列表、状态筛选、详情、报告、证据和执行历史；每 5 秒刷新，切到其他标签页时暂停轮询。失败任务可确认后手动重试，每任务最多 5 次执行。报告和外部标题按纯文本显示。

查看已有记录只需要 Java 和对应数据库；创建研究任务或重试还需要 Python。默认摘录模式无需模型密钥。无需另外启动前端服务器，也无需 npm 安装。创建请求失败后，在本页保留相同问题再次提交会复用幂等键；刷新或关闭页面会丢失该临时键，此后应先检查列表再决定是否重新创建。

2026-10-15 已在用户本机备份后将日常 MySQL 库从 V1 升级到 V3，Java 健康检查通过，并从 React 网页完成一次真实 Wikipedia 检索、5 条证据入库与刷新查询。本轮模型关闭。未来新增迁移前仍需停止访问该库的 Java 应用并备份；备份导出成功不等于恢复演练通过。

2026-10-15 新增备份后启动脚本：在自己的 PowerShell 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File E:\InfoExplorer\backend\java-api\Backup-And-Start-MySql.ps1`。第一次隐藏输入 root 密码，只导出本机 infoexplorer 至 backups/mysql；成功后第二次隐藏输入 infoexplorer_app 密码启动 Java 和待执行迁移。备份失败不会启动 Java。备份期间不要让其他应用写库或修改表结构。备份与校验值只留本机，导出成功不代表恢复演练已通过。迁移异常时不要自动修复或覆盖恢复，先检查日志。本脚本实际完成状态见 CURRENT_STATE.md。

本轮浏览器验证使用隔离 H2 和本机模拟 Agent，覆盖创建、状态更新、失败重试、分页筛选、移动布局及文本安全展示；未重新调用真实模型，也未修改日常数据库。当前无登录和用户隔离，仅供本机使用。

## 本地启动（PowerShell）

在第一个终端启动 Python，仅监听本机：

```powershell
Set-Location E:\InfoExplorer\backend\agent-service
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

在另一个终端启动 Java（要求 Java 21 可用）：

```powershell
Set-Location E:\InfoExplorer\backend\java-api
.\mvnw.cmd spring-boot:run
```

Java 默认端口 8080。Maven 首次使用可能下载构建依赖。当前虚拟环境使用 Python 3.13.5；在新机器上需要创建自己的虚拟环境并安装 `requirements-dev.txt`，不要复制 `.venv`。依赖文件固定了直接依赖，尚不是包含传递依赖的完整锁文件。

在第三个终端调用：

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8080/api/v1/chat/ask' `
  -ContentType 'application/json' -Body '{"question":"hello"}'
```

预期 JSON 内容：

```json
{"answer":"Python Agent received: hello","sources":[]}
```

Python 健康接口为 `http://127.0.0.1:8000/health`；Java 为 `http://127.0.0.1:8080/actuator/health`。Java 的健康接口目前不检测 Python 是否可用。停止服务使用各终端的 Ctrl+C。

## 创建并查询研究任务

启动两个服务后，在 PowerShell 执行：

```powershell
$headers = @{ 'Idempotency-Key' = [guid]::NewGuid().ToString() }
$task = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8080/api/v1/research-tasks' `
  -Headers $headers -ContentType 'application/json' -Body '{"question":"artificial intelligence"}'
$task
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/research-tasks/$($task.id)"
```

创建返回 HTTP 202 和 `Location` 查询地址，不等待 Agent 完成。再次执行最后一行可查看最新状态：`PENDING` → `RUNNING` → `SUCCEEDED` 或 `FAILED`。成功结果位于 `result.answer` 和 `result.sources`；失败原因位于 `errorCode`。

`result.evidence` 保存各条证据的 id、url、title、excerpt、retrievedAt 和 contentHash；`result.provider` 与 `result.query` 记录实际检索源及关键词。摘要中的 `[E1]` 对应证据 id。获取时间不是文章发布时间；内容哈希仅校验保存的摘录，不代表事实经过验证。

当前搜索范围仅为 Wikipedia，默认英文版，最多 5 条、每条最多 800 个 Python 字符的纯文本摘录。使用主题关键词，不会自动拆解复杂研究问题。默认摘要是原文摘录汇总；显式启用模型后生成带证据编号的报告。两者均不能作为全网或新闻搜索。零条可用摘录不会调用模型，不回退成模拟成功。

创建页可选择中文或英文 Wikipedia；API 创建请求增加 language（zh/en），省略或 null 时兼容旧客户端默认 en。页面新建默认中文，语言随任务保存且重试沿用。原 SEARCH_WIKIPEDIA_LANGUAGE 环境变量不再控制任务检索。规划关闭时不会自动翻译或改写问题；启用后仅在所选语言内生成关键词。是否可用取决于本机网络。研究任务会将所填问题发送给公开 Wikipedia API；不要填写凭据或私人业务内容。仅任务研究路径访问外网，旧聊天路径不访问。

来源内容及标题属于不可信外部文本，当前网页使用 textContent 按文本显示，不作为 HTML 执行。所有 HTTP 抓取均指向固定 Wikipedia API，不跟随返回的网址抓取任意网页。

同一个请求重发时复用 `$headers`，会返回原任务；想创建新任务才生成新键。相同键用于不同问题返回 409。未提供键时，每次 POST 都会创建新任务。当前没有用户账户，键在整个应用内唯一。

旧聊天接口仍可使用，但不会保存为研究任务。研究任务查询成功返回 200，即使任务本身已经 FAILED；这与查询请求失败是不同概念。

## 任务列表、分页与筛选

只需启动 Java 和对应数据库，不依赖 Python 或模型。查询示例：

```powershell
Invoke-RestMethod 'http://127.0.0.1:8080/api/v1/research-tasks?page=0&size=20'
Invoke-RestMethod 'http://127.0.0.1:8080/api/v1/research-tasks?page=0&size=20&status=FAILED'
```

响应为 `{"items":[],"page":0,"size":20,"hasNext":false}`（空库示例）。items 每项包含 id、question、status、createdAt、updatedAt；报告和证据通过原有详情接口查询。page 从 0 开始，范围 0–10000；size 默认 20、范围 1–100。status 可省略，或为大写 PENDING / RUNNING / SUCCEEDED / FAILED。空值、重复参数、未知参数及不合法值返回 400 / INVALID_QUERY。

固定按 createdAt、id 倒序排列，hasNext 表示本次查询时还有下一页；不返回总数。翻页时 page 加 1，保持 size/status 不变。多个请求之间新增任务或状态变化可能导致重复/遗漏；此 OFFSET 分页不是快照，尚不适合大量深分页。当前无用户隔离，仍仅供本机使用。

H2 新增 V4、MySQL 新增 V2，仅增加 `(created_at,id)` 索引；按状态筛选复用既有 `(status,created_at,id)` 索引。下一次启动对应 profile 自动应用迁移，不搬迁数据、不修改旧迁移。大数据量环境建索引耗时与锁影响尚未评估。

## 失败任务手动重试与执行历史

新增接口：`POST /api/v1/research-tasks/{id}/retry`，请求体 `{"failedRunId":"当前失败执行的 UUID"}`。仅对当前 FAILED 执行接受新的重试，返回 202 和 Location。必须从任务详情取得 runId，不能只传任务 ID 盲目重试。

```powershell
$taskId = '替换为失败任务的 ID'
$failed = Invoke-RestMethod "http://127.0.0.1:8080/api/v1/research-tasks/$taskId"
$retryBody = @{ failedRunId = $failed.runId } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/research-tasks/$taskId/retry" -ContentType 'application/json' -Body $retryBody
Invoke-RestMethod "http://127.0.0.1:8080/api/v1/research-tasks/$taskId/runs"
```

同一个 failedRunId 重复提交只返回任务最新状态，不新增重试；即使后续执行又失败，旧请求也不会重试那次新失败。新的失败必须取得新的 runId 后再操作。不需要额外 Idempotency-Key，失败执行 ID 就是本次操作的去重标识。

成功、运行中、排队中的执行不能接受新的重试请求；冲突返回 409 / RETRY_CONFLICT，无效失败 ID 返回 400 / INVALID_RETRY。每任务最多 5 次执行（首次 + 4 次手动重试），达到上限返回 409 / RETRY_LIMIT_EXCEEDED。新建任务不受此单任务上限限制，故这不是账户级成本控制。

重试排队后详情为 PENDING、runId/errorCode/result 等当前执行字段为空；后台领取时才创建新执行。历史接口返回按 attempt 升序的数组，每项含 id、attempt、status、startedAt、completedAt、errorCode、retryAccepted，不删除原失败记录。没有自动重试或自动修改模型输出，每次重新执行仍可能访问搜索源和模型；重试前应确认问题不含隐私及供应商计费，修复配置错误或等待限流结束。

H2 V5 / MySQL V3 为新增 Java Flyway 迁移：为任务和执行添加次数，将“每任务只能一条执行”改为“每任务每次执行唯一”。旧记录归为第 1 次，证据仍关联原 runId。旧迁移不修改、不搬迁数据库。H2 升级、离线服务联调及真实 MySQL 新迁移与重试测试已通过（2026-10-14 15:58:42）；日常开发库尚未应用新迁移。迁移涉及约束变更，数据库 DDL 失败可能留下部分变更，正式使用前应备份并停掉访问该库的应用。

## 数据保存与重启

可选 MySQL 8.4 接入已完成，6 项真实数据库集成测试全部通过（含分页筛选、手动重试、历史保留及 V3 迁移），详细验证范围见 docs/CURRENT_STATE.md。默认仍为 H2，不会因测试通过自动切换日常数据库；详见下方 MySQL 小节。

- 默认使用 H2 文件数据库，无需安装独立数据库服务。从上述 Java 目录启动时，文件位于 `E:\InfoExplorer\backend\java-api\data`。
- 可设置 `$env:INFOEXPLORER_DATA_DIR = 'E:/InfoExplorer/data'` 固定存储目录，避免不同启动目录创建不同数据库。修改目录不会自动搬迁已有数据。
- Flyway 在启动时执行版本化迁移；已应用的迁移文件不要直接改写，后续建新版本。
- 重启后，已完成结果保留；PENDING 继续执行；遗留 RUNNING 标记为 FAILED / EXECUTION_INTERRUPTED，不自动重新调用 Agent。
- 当前单实例、单后台执行线程；H2 文件锁禁止第二个进程同时打开同一文件。支持失败任务手动重试，未支持多实例部署、自动重试或取消。
- 数据库包含原始问题和结果，应作为本地业务数据保护；忽略规则已覆盖。当前没有登录鉴权，不应直接暴露到公网。

## 配置

### MySQL 8.4（显式启用）

运行 MySQL 时使用 `--spring.profiles.active=mysql`，不要同时启用 test profile。连接变量：MYSQL_HOST（默认 127.0.0.1）、MYSQL_PORT（3306）、MYSQL_DATABASE（infoexplorer）、MYSQL_USER、MYSQL_PASSWORD。密码没有源码默认值。该配置要求 TLS 加密（sslMode=REQUIRED），但不校验服务器身份；只适用于当前本机开发，远程部署需配置信任证书和 VERIFY_IDENTITY。

MySQL 数据库必须预先创建，建议为项目建立独立数据库和仅有该库权限的账户。可在本机 MySQL 客户端登录后执行：

```sql
CREATE DATABASE infoexplorer CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
```

如果已存在同名库，先确认用途，不要删除或覆盖。运行账户需要 Flyway 建表/变更权限及业务读写权限，仅限该库；后续生产部署应分离迁移账户和运行账户。不要把 root 密码写入配置文件。2026-10-14 已验证 Java 通过下述脚本使用 infoexplorer_app 连接本机 infoexplorer 开发库，Flyway V1 建表成功，健康接口返回 UP；未指定 mysql profile 时仍默认使用 H2。

本机便捷启动：新开终端执行 `powershell -NoProfile -ExecutionPolicy Bypass -File E:\InfoExplorer\backend\java-api\Start-MySql.ps1`，隐藏输入项目账户密码。该脚本固定连接本机 3306 的 infoexplorer 库，用 mysql profile 启动 Java，日志写入 target/mysql-startup.log；不保存密码，退出时移除脚本进程内的连接变量。首次运行 Maven 可能下载启动插件的依赖。启动会执行 Flyway 迁移及恢复遗留任务，不能与另一个连接相同库的 Java 实例同时启动。Python 可保持关闭以先检查数据库启动，不要在 Python 关闭时提交研究任务。

在用户自己的 PowerShell 设置非敏感连接变量，并通过隐藏输入配置密码后启动：

```powershell
$env:MYSQL_USER = '你的项目数据库用户名'
$dbSecret = Read-Host 'MySQL password' -AsSecureString
try { $env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new('', $dbSecret).Password }
finally { $dbSecret.Dispose(); Remove-Variable dbSecret }
.\mvnw.cmd spring-boot:run '-Dspring-boot.run.profiles=mysql'
# Java 停止后移除本终端中的密码
Remove-Item Env:MYSQL_PASSWORD
```

MySQL 迁移独立放在 db/mysql；H2 的 V1–V3 保持原样。不自动把 H2 文件中的数据导入 MySQL，不共用 Flyway 历史表。表使用 InnoDB、utf8mb4_0900_bin，幂等键区分大小写；CLOB 改为 MEDIUMTEXT，并使用显式 FOREIGN KEY。两种数据库共用 LIMIT 1 领取查询。

真实数据库验证在新开的 PowerShell 运行 `powershell -NoProfile -ExecutionPolicy Bypass -File E:\InfoExplorer\backend\java-api\Test-MySql.ps1`。脚本只在当前子进程隐藏输入凭据，执行后清除；Maven 使用已缓存依赖离线运行。测试连接仅限 127.0.0.1，每项创建唯一 infoexplorer_test_<uuid> 库，完成后删除自己创建的库。测试账户需有创建和删除这些临时库的权限；root 可用于这次本机测试，不建议作为应用日常账户。测试不调用搜索或模型，因此 Python 服务可保持关闭。

覆盖真实外键/CHECK 约束、中文 emoji、区分大小写的幂等键、8 路并发幂等与领取、事务回滚、应用重启后读取及中断恢复。日志为 backend/java-api/target/mysql-live-test.log。若进程被强制终止，可能留下随机测试库；不得用通配符批量删除，应先核对本次创建的具体库名。

### Java 通用配置

在启动 Java 的终端设置环境变量即可覆盖默认值：

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `AGENT_SERVICE_BASE_URL` | `http://127.0.0.1:8000` | 固定的内部 Agent 地址，不接受用户提供的任意 URL |
| `AGENT_CONNECT_TIMEOUT_MS` | `3000` | 建立连接超时，必须为正数 |
| `AGENT_READ_TIMEOUT_MS` | `10000` | 等待读取超时，必须为正数；不是研究任务的总耗时预算 |
| `AGENT_RESEARCH_READ_TIMEOUT_MS` | `60000` | 研究专用读取超时，容纳搜索及可选模型调用；不是总任务截止时间 |
| `INFOEXPLORER_DATA_DIR` | `./data` | 相对 Java 启动目录的数据库目录，建议固定绝对路径 |

默认摘录模式不需要 API Key。Java 默认绑定 127.0.0.1；Python 应按上述命令绑定本机。此阶段尚无认证和生产部署配置。

## 可选模型报告（默认关闭）

仅在 Python 服务进程配置以下环境变量，重启服务生效；不需要修改 Java 或数据库密码。未确认中国站模型和收费规则前保持关闭。不要把密钥贴到聊天、源码、截图或终端历史中；可用 PowerShell 7 的 `Read-Host -MaskInput` 在本机交互输入后赋给进程环境变量。

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `INFOEXPLORER_MODEL_ENABLED` | `false` | 仅 `true` 启用，其余非法值返回配置错误 |
| `MODEL_BASE_URL` | 无 | 经确认的 HTTPS 地址，路径须为 `/v1`，端口为 443；不接受凭据、查询参数或片段 |
| `MODEL_ALLOWED_HOST` | 无 | 与地址完全对应的受信域名，不接受请求或模型输出覆盖 |
| `MODEL_NAME` | 无 | 固定模型名称，不自动切换模型 |
| `MODEL_API_KEY` | 无 | 项目专用密钥，只供后端读取，禁止记录日志 |

请求采用兼容 `/v1/chat/completions` 的非流式文字接口，不安装平台接入工具，也不开放 tools。是否支持请求参数与 JSON 输出，仍需实际供应商验证。网络请求保持证书校验，不继承系统代理，不跟随重定向。

每次执行最多一次模型调用，Python 不自动重试；Java 手动重试会发起新的执行。每 Python 进程同时最多一个模型调用，超出返回 MODEL_BUSY。请求体上限 32 KiB，响应体上限 64 KiB，max_tokens=1200；该参数依赖供应商遵守，不能代替账户收费控制。模型网络阶段在可终止子进程中执行，等待上限 20 秒，另有少量启动/清理开销；整个检索任务尚无严格总截止时间。

模型返回结构化结论及证据 ID；程序检查引用存在性，生成带 `[E1]` 的报告。此检查不证明结论受证据支持，不是事实核验。无证据不调用模型，证据不足可以明确拒答。模型失败时任务 FAILED，不静默回退成功；当前失败任务不保存检索中间证据。

成功报告的 `generation` 保存 model、host、promptVersion、inputHash；provider 仍表示检索源。未使用模型及历史报告的 generation 为 null。V3 迁移增加该元数据列，V1/V2 不变。模型名称是请求名称，不能据此独立证明供应商实际使用的模型。

## 离线跨服务联调

在 Python 服务目录运行 `.\.venv\Scripts\python.exe tests/run_offline_contract.py`。脚本启动本机真实 Python HTTP 服务，再执行 Java 全套测试；搜索和模型传输使用固定样例，覆盖报告入库、超时、限流及未知引用失败，所有数据库均隔离。可传入本机已安装的 Maven 可执行文件路径作为第一个参数。脚本使用 Maven 离线模式，不下载依赖；如依赖未缓存需另行准备。

## 测试

```powershell
Set-Location E:\InfoExplorer\backend\agent-service
.\.venv\Scripts\python.exe -m pytest -q

Set-Location E:\InfoExplorer\backend\java-api
.\mvnw.cmd test
```

常规测试使用本机临时 HTTP 服务和独立内存数据库；文件持久化测试在临时目录中关闭、重新打开应用上下文，验证结果保留和遗留任务恢复。不接触日常开发数据库，不调用外部搜索或模型。Java 默认跳过三项可选 Python 联调测试；离线联调脚本启用全部三项，使用固定搜索/模型样例。

Python 常规测试也不访问外网，默认跳过一项 live 检索测试；在 Python 终端设置 `$env:INFOEXPLORER_LIVE_SEARCH = '1'` 可启用，用完移除该环境变量。

执行完整联调：先按上文启动 Python，然后在 Java 终端运行：

```powershell
$env:INFOEXPLORER_TEST_AGENT_URL = 'http://127.0.0.1:8000'
.\mvnw.cmd test
Remove-Item Env:INFOEXPLORER_TEST_AGENT_URL
```

该环境变量仅用于测试；上述外网联调启用两项测试，分别验证旧聊天接口，以及研究任务通过 Python 真实检索 Wikipedia 后保存证据。后者需要访问外网，并要求 Python 使用默认英文搜索源且保持模型关闭；第三项模型故障测试仅由离线脚本启用。测试报告在 `backend/java-api/target/surefire-reports`。只有测试进程实际结束且退出码为 0 才算通过。

## 可选真实模型端到端测试

先在持有密钥的终端启用模型并启动 Python（本机 8000 端口），保持该窗口运行。在 Java 目录另开 PowerShell：

```powershell
$env:INFOEXPLORER_TEST_AGENT_URL = 'http://127.0.0.1:8000'
$env:INFOEXPLORER_TEST_AGENT_MODE = 'live-model'
try {
    .\mvnw.cmd -o '-Dtest=LiveModelIntegrationTests' test
} finally {
    Remove-Item Env:INFOEXPLORER_TEST_AGENT_URL -ErrorAction SilentlyContinue
    Remove-Item Env:INFOEXPLORER_TEST_AGENT_MODE -ErrorAction SilentlyContinue
}
```

此测试固定验证中国站 agnes-2.5-flash：仅创建一个公开问题 artificial intelligence，通过真实后台 worker 执行，检查模型元数据、证据入库、幂等重放，以及关闭应用后重新打开临时文件库的查询结果。启用 test profile、随机本机端口和 JUnit 临时目录，不使用开发数据库。测试结束关闭自己启动的 Java 应用，不停止用户的 Python 服务。普通测试及离线联调均跳过这一项；外部限流可能导致失败，不自动重试。

## MySQL 与真实模型联合验证（显式启用）

已确认 Agnes 中国站地址、agnes-2.5-flash 及本账户计费后，可在独立 PowerShell 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File E:\InfoExplorer\backend\agent-service\Start-Model.ps1`，隐藏输入 API Key，保持 Python 窗口运行。已有 Python 占用 8000 时不要重复启动。

另开 PowerShell 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File E:\InfoExplorer\backend\java-api\Test-MySqlModel.ps1`，输入有临时库创建/删除权限的本机 MySQL 账户密码（默认 root）。测试只用公开问题 artificial intelligence，最多一次模型调用，不自动重试；随机创建 infoexplorer_test_<uuid> 库，自动关闭/重新打开独立 Java 应用并核对结果，再清理该库。日常 Java 窗口可以保持运行，因为使用不同数据库与随机 HTTP 端口。强制终止可能留下测试库，禁止通配清理。

日志为 backend/java-api/target/mysql-model-test.log；成功要求 1 test、0 failures/errors/skipped。脚本不保存凭据。2026-10-14 15:34:41 真实联合验证已通过：5 条证据与 v2 模型报告保存至临时 MySQL 库、幂等重放、应用重开查询均通过，清理无错误。此前 MODEL_INVALID_RESPONSE 失败及提示词修订记录见 docs/CURRENT_STATE.md。Python 若拒绝模型响应，会在服务窗口输出 MODEL_RESPONSE_REJECTED reason 及固定分类，不输出原始回复或凭据。一次成功不代表长期稳定性或报告语义质量已验证。

## 版本管理

工程尚未初始化 Git。根目录忽略规则已准备，但不代表完成敏感信息审计；初始化、提交及上传需要用户另行授权。
