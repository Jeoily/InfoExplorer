# 本机演示与日常操作

这是本机单用户项目，不是公网服务。所有网址中的 127.0.0.1 都指本机，不需要购买域名。

## 已经准备好的电脑

先确认 MySQL84 已启动、Docker Desktop 左下角 Engine running。搜索服务通过 `infra/searxng/Start-Search.ps1` 启动；已在运行时不要重复创建。

无人值守方式：普通 PowerShell 运行 `scripts/Start-Unattended.ps1`，依次在本机隐藏输入 root、项目账户密码和模型 Key，保留 READY 窗口。不能把密码或 Key 发到聊天或填到命令参数。配置与当前供应商费用仍需本人确认。

另一个窗口可运行固定控制命令：

```powershell
Set-Location E:\InfoExplorer
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Control-Unattended.ps1 -Action python-start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Control-Unattended.ps1 -Action java-deploy
```

java-deploy 会先做隔离测试、备份，再启动日常 Java；失败会停止，不应反复重试或自行 Flyway repair。仅在准备升级且已核对修改时使用，不是每次刷新网页都要执行。备份成功不等于恢复演练完成。详细安全与恢复边界见 UNATTENDED.md。

前端普通窗口：

```powershell
Set-Location E:\InfoExplorer\frontend
npm.cmd run dev
```

打开 http://127.0.0.1:5173 。服务不具备登录和公网权限隔离，只监听本机。

## 五分钟演示

1. “开始研究”选择网页摘录，输入公开主题。说明摘录不调用模型；搜索失败和无证据会如实显示。
2. 选择模型研究前核对费用。成功后查看计划、实际检索、缺口判断、引用段落、读取失败及限制。接口成功不代表所有事实已核实，读者仍需核对原文。
3. “持续追踪”新建同一主题，默认手动；保存不会立即执行。点击“现在检查”后，从检查轮次跳转完整报告。
4. 再检查一次，展示同 URL 正文哈希比较、来源修订及上次摘录。可能出现正文未变、变化、提取方式变化、首次发现；失败不伪装成无变化。时间线是发现时间。
5. 暂停并刷新页面确认状态保留；自动检查仅允许网页摘录，至少一小时。本机服务停止时不执行，重启后合并错过时槽。模型研究不定时运行。

历史测试样例在隔离测试库，日常演示记录来自真实公开搜索。不要把含 fixture/offline 字样的内容当真实资料。

## 验证命令

- `frontend/Test-Frontend.ps1`：真实 Java HTTP、随机 H2、模拟 Agent 的浏览器测试，不访问外部。
- Java `mvnw.cmd -o test`：默认隔离测试；真实 MySQL/模型测试默认跳过，不能据此说已通过。
- `backend/java-api/Test-MySql.ps1`：本机输入 root，创建并清理本次随机临时库，不修改日常库。
- Python 在项目虚拟环境设置 `.web-deps` + 项目目录为 PYTHONPATH 后 `python -m pytest -q`：离线测试。
- 显式搜索检查 `scripts/check_local_search.py --live --extract`：仅固定公开关键词，实际访问外部搜索与文档，不调用模型。

## 停止

先等研究任务结束。运行 `Control-Unattended.ps1 -Action shutdown` 停止管理进程拥有的 Java/Python 并清理内存凭据；有活跃任务会拒绝。前端窗口 Ctrl+C，Docker 中停止本项目搜索容器。MySQL 可保留；确需停止则管理员 PowerShell 执行 `Stop-Service MySQL84`。管理窗口直接关闭属于中断，正在运行的研究下次启动会标失败。

## 换电脑

需要 Java21、Python、Node.js、MySQL8.4、Docker/WSL 和浏览器。按各 backend/frontend/infra README 安装固定依赖，首次联网下载依赖不等于普通测试要联网。不要复制旧虚拟环境、node_modules、数据库或凭据。安装/缓存/数据尽量选择 E 盘；本机 `.mvn/maven.config` 是忽略的绝对路径配置，换机器需自行配置正确缓存位置。

当前尚未在全新电脑做安装验收，也未做日常备份恢复演练；不能承诺零配置部署。搜索上游有验证码/限流，部分网页不可读，模型可能误读证据。无多实例、通知、登录或公开部署。
