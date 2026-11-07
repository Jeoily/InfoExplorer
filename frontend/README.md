# InfoExplorer React 前端

React + TypeScript + Vite + React Router + TanStack Query + Ant Design。页面为研究入口、任务列表和报告详情，复用现有 Java API。Node 仅用于工具链。

2026-10-19 新增“模型研究”选择（web-model）：计划、补搜原因、停止原因、报告引用及每次执行快照已接入。需后端新版本和 H2 V9/MySQL V7；日常库升级先测试并备份。模型路径通过隔离模拟联调，真实供应商验证状态见根 docs/CURRENT_STATE.md。当前过程记录在执行结束后展示，不是实时推理流或断点恢复。

## 本机开发

本机依赖已安装。换机器或重新安装时，在本目录执行 `npm.cmd ci`（需要联网）；提交 package-lock.json，不提交 node_modules 或 dist。本轮验证 Node 24.17.0 / npm 11.13.0。

```powershell
Set-Location E:\InfoExplorer\frontend
npm.cmd run dev
```

浏览器打开 http://127.0.0.1:5173/#/research/new 。页面通过 /api 代理到本机 Java 8080；此命令不会启动 Java、Python 或数据库。只看页面布局可不启动后端，提交和查询需要 Java；真实检索还需要 Python。日常 MySQL 启动前遵守根 README 的备份与迁移说明。

可以在启动前设置非敏感变量 INFOEXPLORER_API_URL 指向受控的本机测试 Java 地址。不要把模型/数据库凭据放到任何 VITE_ 变量，前端资源可被浏览器读取。服务仅绑定 127.0.0.1。

## 构建与检查

```powershell
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd run preview
```

preview 在 http://127.0.0.1:4173 提供 dist 构建，用 hash 路由避免刷新回退配置。预览中 HTML 每次响应生成随机样式 nonce，Ant Design 动态 style 使用该 nonce；脚本只允许同源。组件布局需要行内样式属性，故仅 style-src-attr 放行 unsafe-inline，不放行行内脚本。没有 CSP 的 Vite 热更新开发环境不能等同此构建预览的安全验证。

当前未将构建产物部署进 Java；不要直接覆盖 backend/java-api/src/main/resources/static。原 Java CSP 不支持这些动态样式，后续统一部署必须单独实现 nonce 和验证。Vite preview 也不是公网生产服务器。

## 自动化浏览器联调

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File E:\InfoExplorer\frontend\Test-Frontend.ps1
```

脚本要求本机 Edge、已安装或缓存的 Maven 及 Java 测试依赖，可用 -MavenPath 指定 mvn.cmd。运行前确保 18080 和 4173 未占用；不需要关闭其他端口上的正常服务。脚本构建前端，启动 UiPreviewTests（真实 Java HTTP + 随机内存 H2 + 本机模拟 Agent），运行 Playwright，最后发出停止信号并等待关闭。无外部搜索、无真实模型、无日常数据库访问。Maven 使用离线模式，不下载 Java 依赖。

截图和失败诊断在 test-results，Java 日志在 E:\InfoExplorer\backend\java-api\target\react-ui-preview.log。测试中的 RETRY_ONCE 为一次失败后成功的专用样例，报告有刻意加入的 HTML 字符串，用来证明文本不会被执行；不是实际研究报告。每轮完整测试需要全新夹具，Test-Frontend.ps1 会安排启动。

`npm.cmd run test:e2e` 是底层命令，要求上述全新测试后端已运行；一般直接用脚本。不要将测试代理指向日常服务。

## 当前限制

仅本机单用户，无登录或生产部署。2026-10-22 新增主题/轮次/资料变化时间线与默认关闭的自动网页摘录，见 docs/contracts/TRACKING_V1.md；不自动识别现实事件或裁定矛盾。模型默认为后端配置，不由前端选择。创建键只保留在当前组件内存，离开创建页或刷新后丢失；不确定提交结果时先查任务列表。前端不自动重试写请求，任务重试由后端 failedRunId 去重并限制最多 5 次。

## 网页研究模式（2026-10-19）

创建页默认 Wikipedia。选择“网页检索”后，任务走 SearXNG 搜索与正文读取，当前不使用模型规划或报告，结果是可核对的资料摘录；可以展开检索/读取记录查看失败原因。执行失败仍可能保留已读证据，历史按钮查看各次快照。运行 ID 和页面实例共同隔离引用定位。

需要 SearXNG 8888、Python 8000、Java 8080、Vite 5173。Python 用 E:\InfoExplorer\backend\agent-service\Start-WebResearch.ps1 启动，无需 API Key。Java 日常 MySQL 已升 V6；以后出现新迁移仍先做隔离测试与备份。此模式不是无限网页搜索或完整自主研究，不能读到所有站点。

本轮后台启动的 Python/前端 PID 和日志在 E:\InfoExplorer\logs。不要直接删除进程记录或重复启动；停止时先核对端口及对应进程。Java 保留用户 PowerShell 窗口，Ctrl+C 正常停止。原 Java 8080 静态页面未升级为网页研究阅读器，请使用 React 的 5173 页面。
