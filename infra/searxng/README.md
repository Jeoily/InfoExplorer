# 本机 SearXNG

2026-10-19 已部署并接入可选 web/web-model 模式；默认模式仍是 Wikipedia。最新真实验证及限制见 docs/CURRENT_STATE.md。

## 存储与边界

- Docker Desktop 位于 E:\Applications\Docker，实际虚拟磁盘位于 E:\DockerData\disk\docker_data.vhdx 和 E:\DockerData\main\ext4.vhdx。WSL 交换文件已核实为 E:\WSL\swap.vhdx。Windows 配置、组件及少量日志仍可占用 C 盘。
- 仅发布 http://127.0.0.1:8888，未向局域网或公网开放。无需登录 Docker Hub。
- 镜像固定为 compose.yml 中的 SHA256 摘要；不会随 latest 自动升级。配置只读挂载，缓存使用 Docker 命名卷（位于 E 盘虚拟磁盘内）。不挂载源码、用户目录或 Docker socket。
- 当前默认仅启用 Yahoo；Bing/Brave/DuckDuckGo 配置保留但禁用，最新探测见本文末尾 2026-10-22 记录。查询会发送给外部搜索源，不能提交私人资料；单次可用不保证持续可用，不自动绕过验证码或轮换出口。
- 本机单用户实例不启用 limiter/Valkey；这不是公网部署方案，也不提供全局请求限流。日志轮转上限 2 × 5 MiB，容器内存上限 768 MiB、CPU 2、进程上限 128。
- 不自动随 Docker 重启。Start-Search.ps1 每次生成随机实例密钥，仅以进程环境变量传给 Compose，随后清理；不写源码或日志。Docker 保存容器环境，因此有 Docker 管理权限的人仍能访问它，禁止输出完整 inspect 或展开后的 compose config。

## 启停

先从 Windows 开始菜单打开 Docker Desktop，等待 Engine running。此前经工具启动出现过配置保存错误，用户手动打开正常；根因未证实，不需要恢复出厂设置。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File E:\InfoExplorer\infra\searxng\Start-Search.ps1
```

停止此容器，保留缓存（不需要密钥）：

```powershell
& 'E:\Applications\Docker\resources\bin\docker.exe' stop infoexplorer-search-searxng-1
```

首次安装需联网获取固定镜像；普通测试不会自动启动或联网搜索。

## 验证记录

- Docker Engine 29.8.2 正常；端口实际绑定 127.0.0.1:8888。
- 公开查询 Python documentation：JSON 返回 10 条，Bing/DuckDuckGo 有结果、Brave too many requests。
- Python 适配器中文查询 Python 官方文档：5 个候选，保留部分上游不可用警告。
- 初次从宽泛查询读取 docs.python.org 候选发生 CONTENT_TIMEOUT；未放宽下载安全或超时策略。
- 更明确的 Python http.client documentation 查询经真实适配器取得 5 个候选，再读取搜索返回的 https://docs.python.org/3/library/http.client.html，提取 320 段，未截断，Trafilatura 2.3.1。不是人工拼接候选。
- 固定旧公开页面另行复核：313 段，2 次请求，通过。离线 test_web_searxng.py + test_web_content.py：32 passed。
- 没有调用模型或数据库，没有 Java/React 全链路联调，也不代表任意网页可读或搜索质量已全面验证。

显式联网验证，在 E:\InfoExplorer\backend\agent-service 中执行：

```powershell
$env:PYTHONPATH="$PWD\.web-deps;$PWD"
.\.venv\Scripts\python.exe scripts/check_local_search.py --live --language zh-CN
.\.venv\Scripts\python.exe scripts/check_local_search.py --live --extract
```

仅使用脚本固定的公开示例关键词，打印计数、失败码和来源，不打印完整正文或凭据。退出码非零表示空结果、失败或提取未完成；不得只看搜索 status 判断提取成功。

依据：[官方容器安装](https://docs.searxng.org/admin/installation-docker.html)、[默认配置与引擎筛选](https://docs.searxng.org/admin/settings/settings.html)、[服务设置](https://docs.searxng.org/admin/settings/settings_server.html)。
## 2026-10-22 当前搜索源

当前 settings.yml 默认启用 Yahoo；DuckDuckGo 因验证码、Brave 因限流暂禁用，Bing 保持禁用。在临时隔离容器中，Yahoo 的公开英文文档、中文全栈概念、MySQL 文档及 site 定向查询均返回相关候选；不能据此保证所有查询或长期可用。Mwmbl 本次可用但结果偏旧，未切入默认链路。Qwant 拒绝访问；固定镜像中的 Mojeek/Startpage 默认 inactive，因此没有强制启用。临时容器已停止并删除，日常端口仍为 127.0.0.1:8888。

接口参数依据：[SearXNG Search API](https://docs.searxng.org/dev/search_api.html)；可用引擎最终以项目固定镜像的实际配置为准。上述旧验证记录为历史，不覆盖本节。

