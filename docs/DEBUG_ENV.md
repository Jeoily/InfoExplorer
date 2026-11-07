# 第一阶段：独立调试环境

2026-10-25。仅本机 Windows 开发；日常服务及数据库不由此入口管理。

## 默认入口：无密码、无外网的固定样例

普通 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\InfoExplorer\scripts\Start-Debug.ps1"
```

看到 READY 表示管理进程就绪，服务还未启动。保留窗口。在另一窗口执行（也可以由 Codex 执行）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\InfoExplorer\scripts\Control-Debug.ps1" -Action start
```

也可以由 Codex 直接启动 `backend/agent-service/.venv/Scripts/python.exe scripts/debug_env.py serve` 并持有进程会话；不需要用户开窗口或输入凭据。不是定时任务或无人值守后台常驻服务。

| 服务 | 调试入口 | 日常入口（不改动） |
| --- | --- | --- |
| React | http://127.0.0.1:15173 | 5173 |
| Java | 127.0.0.1:18080 | 8080 |
| Python | 127.0.0.1:18000 | 8000 |
| 数据库 | 本次会话目录内 H2 | 日常 MySQL / H2 |

页面选择“模型研究”，用 `Public topic` 验证成功，用 `fail report` 验证失败后证据保留。**这里的搜索和模型是固定合成样例，不是实际搜索，也不回答任意问题。** 调试 Python 仅暴露 v3 和健康检查，没有可访问 Wikipedia/真实网页的 v1/v2 路由。无需启动 MySQL 或 Docker。

## 固定管理操作

将上述 `-Action start` 替换为：

- `status`：向活着的管理进程请求状态，不把旧状态文件当作运行证明。
- `restart-python`：停止并重启自有 Python，加载源码修改。
- `rebuild-java`：复制 Java 源码到新的会话构建目录，离线打包并重启自有 Java。
- `restart-frontend`：重启自有 Vite。
- `stop`：停止三个自有服务，保留管理进程、测试数据库和日志。
- `start`：再次启动，沿用当前会话 H2 数据库；新管理会话则使用新数据库。
- `shutdown`：停止三个服务并退出管理进程。

正常停止/重启前检查隔离 Java 中无 PENDING/RUNNING 研究任务；有任务时拒绝操作。不要自动重发超时的管理操作：结果会留在输出提示的 request/result 文件，观察超时不代表操作取消。管理窗口 Ctrl+C 或关闭属于紧急退出，Windows Job Object 清理自有进程树，不保证正在进行的任务优雅完成或远端请求取消。

已有调试端口被其他程序占用时明确拒绝启动，不杀占用者，也不接管未知服务。只允许一个调试管理会话。当前文件记录留在 `logs/debug/current.json`，关闭后可能仍存在；它不是存活证明。状态请求无回应时不要根据 PID 自动杀进程。

## 隔离边界

- 所有会话数据、临时文件、日志和 Java 构建在 `E:\InfoExplorer\logs\debug\<随机会话>`。依赖复用现有 E 盘 Maven 缓存、Python 虚拟环境和前端依赖，不安装新软件。
- Java 强制独立 H2 URL、驱动、迁移路径，禁止 Flyway clean，不使用 mysql profile；不需要 root 或项目数据库密码。编译不写日常 `java-api/target`，不触发日常 DevTools 重启。
- 子进程环境使用允许列表，剥离继承的 Spring、MySQL、模型密钥、Java/Node 注入选项及其他项目开关。密钥只给需要它的 Python，不给 Java/Vite/构建。
- 日志和测试数据库保留以便排查，不自动删除历史会话；多次构建会占用 E 盘空间。不要把这些运行目录提交或上传。
- 这不是容器或抵御同一 Windows 用户恶意代码的安全沙箱；源码、依赖和本机文件控制目录都必须可信。

## 将来需要真实模型时

本阶段未调用真实供应商。只有另行确认供应商地址、模型、计费及次数后，才显式执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\InfoExplorer\scripts\Start-Debug.ps1" -LiveModel -BaseUrl "供应商已确认的HTTPS地址/v1" -AllowedHost "供应商已确认的域名" -Model "已确认的模型" -Attempts 4
```

本机隐藏输入一次 API Key；不要把它放在参数、聊天或文件中。之后 Python 的重启沿用管理进程内存中的凭据，直到管理进程退出。新会话必须重新输入。真实模式使用现有 8888 的搜索服务，需单独准备；不自动启动 Docker。

只开放 v3 模型研究，先预约研究次数再执行，失败也占次数；本次会话次数写入无凭据的 budget.json，Python 重启或 stop/start 不重置。每研究沿用现有最多 3 模型请求。耗尽返回 DEBUG_BUDGET_EXHAUSTED，不自动重试/更换模型；新建会话不能作为绕过用户预算的办法。该计数不核验账单，无法自动探知免费政策变化，远端费用仍需用户确认。

## 验收证据

`scripts/check_debug_env.py --browser` 在自有隔离服务中额外运行 Edge 界面验收：四类模型研究样例、阶段复查按钮、刷新/历史/引用、手机宽度，保存截图和 browser-result.json，结束后清理服务。默认不加参数仍只做 HTTP/回放及生命周期验收。

第二阶段新增[阶段记录与离线回放](RESEARCH_REPLAY.md)。固定样例自动保存阶段数据；真实模式需显式 `-RecordPublic`。离线 CLI 不启动服务、不访问网络。

- `scripts/test_debug_env.py`：环境/配置隔离、端口冲突、启动失败清理、活跃任务阻断、虚构密钥只传 Python 及日志脱敏、跨重启预算不重置。
- `scripts/check_debug_env.py`：显式运行本机完整验收。须先退出既有调试管理进程；脚本创建并拥有自己的管理进程，检验前端代理、成功/失败任务、分别重启、H2 记录保留、stop/start、强制结束管理进程后服务清理及日常目录/端口未变化。
- 上述是固定样例接入真实 Java/Python/React HTTP 与 H2 的验证，不是回答质量或真实模型认证。MySQL profile、真实供应商及全新机器安装不在本阶段已验证范围。
