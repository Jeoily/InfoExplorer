# 持续目标的本机准备

2026-10-22：目标为完成 PROJECT.md 的 A/B/C 层次，不将模拟通过当真实验收。

## 用户一次准备

1. 管理员 PowerShell 执行 `Start-Service MySQL84`；随后可关闭该管理员窗口。
2. 从开始菜单手动打开 Docker Desktop，等 Engine running。不从工具反复启动有跨盘报错的桌面程序。
3. 普通 PowerShell 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File "E:\InfoExplorer\scripts\Start-Unattended.ps1"`。
4. 隐藏输入 root 密码、infoexplorer_app 密码、Agnes API Key。等待 READY，保留窗口。

用户已确认 https://api.agnes-ai.cn/v1、agnes-2.5-flash 当前免费，同意本目标最多 10 次真实研究尝试，每次最多 3 次模型调用。调用由 agent 计数并记录，supervisor 本身不拦截 HTTP 或强制此总配额；运行期间不要额外从网页发起模型任务。出现计费变化、额度错误停止真实调用。普通测试仍不访问外部。

准备阶段仅 SELECT 1 校验两个账户、检查模型配置结构；不调用模型、不升级数据库。凭据仅在本机管理进程内存中保留，按用途传给子进程环境，不写命令参数或文件。root 只供测试及备份，Java 日常服务用项目账户，Python 只有模型密钥。运行日志过滤已知凭据原值；不记录完整环境、请求正文或模型原文。

这不是抵御同一 Windows 用户恶意进程或恶意源码的安全隔离：本地工具运行的项目代码本来就获得必要环境凭据。不要把请求目录或项目授予不可信用户。

## 固定操作与恢复

入口 scripts/unattended.py，只轮询本次随机 logs/unattended/<session>/，无 HTTP 控制端口，不接受任意命令/路径/参数。current.json 保存会话路径及状态，无秘密。提交 UTF-8 JSON 文件 <uuid>.request.json，内容恰为 id（32位小写十六进制）及 action，读取相应 result.json。旧会话请求不重放。

- check：验证本机凭据及模型配置，无外网调用。
- python-start/python-stop：管理自有 Python 子进程；不抢占其他进程端口。
- mysql-test：仅执行 MySqlIntegrationTests；须 8080 空闲，测试只创建/清理其随机临时库。
- java-deploy：停止自有空闲 Java→普通离线 Java 测试→显式 MySQL 测试→离线打包→备份固定日常 infoexplorer 库并计算哈希→用项目账户启动打包产物，应用迁移。任一步失败停止，不自动重试/恢复/repair；备份校验不等于恢复演练。
- java-stop/shutdown：检查 Java 无 PENDING/RUNNING 任务后停止自有进程；不停止 MySQL/Docker。

启动器杀进程树仅针对它仍持有的存活子进程，是 Windows 强制停止；显式正常操作先检查无活跃研究任务。用户 Ctrl+C 紧急退出会停止自有服务，若任务进行中，下次启动应按中断恢复，不承诺优雅完成。管理窗口关闭后，凭据不能供新管理进程继承，需要用户重新输入。服务健康失败不称启动成功。

不主动安装软件、修改系统权限、删除日常数据、恢复备份、Git 初始化或上传。安装/数据尽量 E 盘。无日常迁移前必须核对当前迁移设计和真实隔离测试结果；java-deploy 操作由执行 agent 在完成检查后提交，不自动在窗口 READY 时运行。

## 当前验证

scripts/test_unattended.py：7 项离线测试通过，均使用虚构凭据，覆盖请求限制、子进程环境隔离、输出打码、失败测试/备份阻断部署、服务运行时阻断编译、状态写入。PowerShell 启动器语法通过。本机真实凭据检查、Python 重启、普通/临时 MySQL 测试、备份打包与日常 V8 启动均通过。管理窗口仍需用户一次输入凭据；搜索服务和前端另行管理，不声称系统重启后无需准备。固定控制入口 scripts/Control-Unattended.ps1 已通过语法检查及真实 status/python-start 验证。
