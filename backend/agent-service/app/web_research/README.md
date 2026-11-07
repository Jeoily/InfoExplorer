# 网页研究模块：Python v2、Java 与 React 可选网页模式

2026-10-19：app/main.py 已注册 /internal/v2/research/run，默认关闭，只有显式启用才运行真实网页检索。旧 v1 Wikipedia 路径保留；Java/React 已接网页模式，日常库已备份升 MySQL V6，创建页默认仍为 Wikipedia。当前 v2 仅直接检索/摘录，模型关闭。完整契约见工程根目录 docs/contracts/WEB_RESEARCH_V2.md；下面较早记录若有冲突，以本段及 CURRENT_STATE 为准。

## 已有组成

2026-10-19 部署更新：本机 SearXNG 已运行于 127.0.0.1:8888，真实中英文公开查询及搜索→受限下载→正文提取已验证。Bing/DuckDuckGo 返回结果，Brave 限流；保留部分上游失败警告和一次正文超时记录。部署与启停见工程根目录 infra/searxng/README.md。业务路由仍未接入。

2026-10-19 更新：content.py 已将 download.py 与 extraction.py 组合为 ContentTool，共享最多 20 秒期限并统一固定错误码。Document.metadata 与 SourceAttempt.metadata 保留来源、跳转、读取时间、提取器、日期来源、截断和提取文本 hash；报告失败仍保留已读取元数据。下面 2026-10-15 的记录为历史状态。

完整测试 293 passed、1 skipped。显式 scripts/check_public_download.py --live --extract 真实读取 Python 官方公开页面成功，313 段、2 次 HTTP 请求、未截断；没有模型或数据库调用。普通测试只用离线资料与本机 HTTP 夹具。

hash 使用 UTF-8 JSON 段落数组（ensure_ascii=False，紧凑分隔符），版本 paragraph-json-v1；它不是原始 HTML 或未截断全文 hash。published_basis=extractor_unverified/unknown，不表示核验过发布日期或事件日期。保持原 candidate 身份，实际跳转地址单独记录。元数据当前只保留在内存结果，尚未入库。

| 文件 | 作用 | 边界 |
|---|---|---|
| budget.py | 单执行搜索/正文/模型次数，墙钟期限，取消标志；原子预留 | 不自动终止调用者的 HTTP 请求 |
| url_policy.py | 候选 URL 与 DNS 结果策略、规范化 | 不做 DNS、不连接网络；不是 SSRF 安全下载器 |
| candidates.py | SearXNG JSON 解析、候选去重、失败警告 | 摘要仍是候选信息，不生成证据 |
| searxng.py | 固定本机地址 POST /search、禁跳转/代理继承、有界子进程 | 本机模拟和真实公开查询已验证；尚未接业务路由，上游存在限流 |
| download.py | 公共 DNS/固定 IP 连接/TLS、逐跳检查、保守 robots、有限 HTML 下载 | 独立实现；1 个真实公开页面验证；未接运行路由，不是完整 robots 或 OS 沙箱 |
| extraction.py | 已下载 HTML → Trafilatura → 正文段落；子进程超时清理 | 已由 content.py 组合下载，验证过一个公开页面；未做 OS 内存沙箱 |
| content.py | 下载与正文提取共享期限、固定错误码、来源元数据和提取文本 hash | 独立模块，未接业务路由或数据库 |
| selection.py | 中文二元字符/英文词匹配、相关窗口、去重、子问题与域名优先、UTF-16 预算 | 词匹配不是语义覆盖或真实性判断；发布时间不参与当前排序 |
| pipeline.py | 注入工具的初次搜索、读取、一次补搜、报告/失败成果 | 没有真实模型规划/覆盖/报告适配，没有 HTTP 路由或 Java 持久化 |

Plan 由调用者提供，尚未新增模型规划器。后续若规划调用模型，必须复用同一个 ExecutionBudget 并先预留模型次数。初次最多 3 查询、每查询 5 候选、首轮读 6 个 URL；补搜最多 2 个查询、读 2 个 URL；全流程最多 8 个正文、8 段证据、每来源 2 段。搜索/正文失败不自动重试。

CoverageReviewer 和 ReportGenerator 目前为可注入函数，测试使用明确的本地夹具。覆盖通过实际编号校验，但不证明引用支持该结论；补搜后只保留 partial，不伪造第二次覆盖审核。失败结果保留内存中已读取证据；进程崩溃不保证恢复。

正文位置是规范化提取段落的 paragraph_index + offset_utf16，不是 HTML DOM。长段落按重叠窗口检查，不只取开头。全文 hash/来源版本关系仍需接入后完善，当前 passage hash 只针对保存摘录。

## 离线运行测试

在 E:\InfoExplorer\backend\agent-service 下执行：

```powershell
.\Test-WebResearch.ps1
# 已准备隔离提取依赖时：
.\Test-WebResearch.ps1 -WithExtraction
```

测试包含本机随机端口的 HTTP 模拟服务，不调用搜索引擎、模型或数据库。普通 pytest 没有 Trafilatura 时提取测试会明确跳过；WithExtraction 使用项目内 .web-deps，并在脚本退出时恢复进程环境。

本轮已在 .web-deps 安装可选提取库，现有 .venv 依赖未替换。新机器准备可选目录的命令（运行会联网下载依赖）：

```powershell
.\.venv\Scripts\python.exe -m pip --isolated --disable-pip-version-check install --no-input --only-binary=:all: --target .web-deps -r requirements-web-lock.txt
```

requirements-web.txt 固定直接依赖；requirements-web-lock.txt 记录本轮 Windows/Python 3.13 下解析到的全部版本，尚非带哈希的跨平台锁。不要提交 .web-deps；已有忽略规则。

## 后续接入门槛

搜索和提取的等待预算包含子进程启动耗时，并在接收结果后再次检查截止时间。终止/回收进程需要额外清理时间；这不是操作系统级硬实时保证，也不限制进程峰值内存。执行器传入剩余预算，未来下载器和模型适配器也必须实际执行这一约束。

1. 部署本机 SearXNG 并启用 JSON，验证可达上游；当前适配器只接受 http://127.0.0.1:<高位端口> 或 IPv6 回环，不接受用户指定服务地址。
2. 下载器已具备公共 DNS 与实际连接 IP 绑定、TLS 主机名校验、每跳验证和有界读取；接入前核对下述限制及统一错误映射。不得绕过它把候选 URL 交给普通 requests/urllib 或提取库下载接口。
3. ContentTool 组合已完成；后续业务接入时持久化 requested/resolved URL、读取时间、日期来源、截断和提取文本 hash。提取库里的下载/爬虫接口不能绕过上述策略。
4. 新模型适配器严格解析计划、覆盖、报告对象；默认关闭，供应商和计费沿用原项目约束。
5. 完成 Java/Python v2 契约、迁移、前端和真实联调后，才可启用新 researchMode。旧任务仍走现有 Wiki 路径。

Python v2 可用 Start-WebResearch.ps1 显式启动，仅监听本机 8000；Java/React 未切换，不是完整应用启用命令。详细目标见 docs/architecture/WEB_RESEARCH.md（从工程根目录读取）。

## 2026-10-15 下载器验证与限制

完整 Python 回归 279 passed、1 skipped（真实搜索未启用），其中下载器 36 项离线测试覆盖恶意跳转、混合 DNS、固定连接/TLS、robots、超大/歧义响应及创建进程失败后释放锁。没有访问搜索上游、模型或数据库。

显式真实验证脚本 scripts/check_public_download.py --live 仅访问固定 Python 官方文档。2026-10-15 14:02 成功取得 97286 字节 HTML，共 2 次 HTTP 请求（robots 与正文）；这是下载验证，不是搜索/提取/模型/Java 全链路验证。

- HTML 上限 2 MiB，robots 上限 512 KiB；只接收 identity 编码，拒绝 gzip 等压缩，不执行 JavaScript，不下载 PDF/附件，不使用 cookie/代理/浏览器状态。
- 最多 3 次跳转，每跳验证，禁止 HTTPS 降级；每篇包括 robots 最多 12 次 HTTP 请求。默认 20 秒上限覆盖父进程启动、DNS 与网络等待；终止回收仍有额外耗时。
- robots 使用保守子集：UTF-8 text/plain，合并所有组的非空 Disallow，不应用 Allow 例外；遇到通配符、结束锚点、crawl-delay/request-rate 会拒绝。404/410 可继续，其他错误停止。不宣称完整 RFC 9309 支持，可能过度阻止本可访问的页面。
- 本进程串行下载，每篇结束后间隔 0.5 秒，每次内部请求间隔 0.25 秒；不是跨进程或跨服务的按域限流。未实现 OS 内存隔离。
- DownloadedPage 只返回实际 URL、HTML、读取时间、类型和请求数；2026-10-19 已在 ContentTool 补充提取文本 hash、日期来源及统一失败映射，业务路由和持久化仍待接入。现有业务仍使用 Wikipedia。
