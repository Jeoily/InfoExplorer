# 网页模型研究 v3 契约

2026-10-19。代码已接入 Python/Java/React，外部搜索与模型的模拟响应已通过真实本机 HTTP 联调。真实供应商效果、日常 MySQL 升级与真实网页模型联合运行需独立验证。

## 模式与边界

- 创建任务的 researchMode 新增 `web-model`；既有 `wikipedia`（默认）和 `web` 不变。模式参与幂等比较，手动重试继承模式。
- Python `POST /internal/v3/research/run`；请求为 runId/question/language，沿用严格 UUID、4000 UTF-16 字符和 en/zh 限制，不允许客户端提供工具、供应商地址、预算或提示词。
- `INFOEXPLORER_WEB_MODEL_ENABLED=true` 才启用 v3 并读取本机 MODEL_* 配置。该开关与旧 Wikipedia 的 INFOEXPLORER_MODEL_ENABLED 独立。v2 仍保证不调用模型；v2/v3 共用进程内执行门控。
- 响应 schemaVersion=`web-research-v3`，mode=`web-model`，language 与请求一致；session.version=`web-model-session-v1`。详见同目录 request/response JSON Schema。

## 会话字段

session 包含 runId、planMode、planReason、plan、decision、report、stopReason、events、usage、outcome。plan/decision/report 是经过验证的模型结构化输出，不是原始模型回复或私有推理。outcome 沿用网页证据、查询和来源结构，审核快照保留审核当时的证据集合。补搜后证据可能变化，不能将补搜前的覆盖判断解释为最终事实核验。

- 规划前预算耗尽或认证失败：outcome 可以为 null，保存安全的停止原因。
- 规划格式错误：可降级原文检索，planMode=direct，保留 planReason。
- 审核/报告错误：outcome.status=FAILED，answer=null，保留已读取的资料及已成功阶段。
- 未取得证据：可能为 SUCCEEDED/NO_USABLE_EVIDENCE，但 report=null；界面显示未生成模型回答。
- 形成报告：claims 分资料陈述/推断，引用最终 evidence ID；limitations 必填。程序重建带引用的答案并在 Java 核对，不能据此声称语义支持性已验证。

统一上限：150 秒、每次操作 20 秒、5 次搜索、8 次正文读取、3 次模型调用；最多一次补搜，无自动重发。Java 175 秒有界等待，最多读取 512 KiB 成功响应、2 KiB 错误响应，拒绝重定向、未知/缺失字段、重复 JSON 键和非法数值；验证运行 ID、来源 hash、证据 hash、审核前后引用身份、计划/决策/调用次数及报告一致性。

## 持久化与查询

新增迁移 H2 V9、MySQL V7：放宽 research_mode 枚举，新增 research_run.model_session_json。不修改旧迁移、不自动搬迁旧数据。

Java 在事务外请求 Python；会话快照和运行/任务终态在同一事务提交。ResearchTask 增加可空 modelSession 字段。历史接口：

`GET /api/v1/research-tasks/{taskId}/runs/{runId}/model-session`

按任务和运行双重限定，无快照返回 404；旧 web-result 仍返回 v2。保存失败不重复调用模型。运行被中断时沿用原单实例启动恢复逻辑；未收到最终会话时不能保证保留中间阶段，不支持断点恢复或跨实例恰好一次。

## 本机使用与验证

1. 先运行 Test-MySql.ps1 在随机临时库验证 V6→V7；日常 Java 保持停止。
2. 通过后由用户运行 Backup-And-Start-MySql.ps1，本机输入密码，先备份再升级日常库。
3. 启动本机 SearXNG，并核对当前供应商地址、模型及计费规则。使用 Start-WebModel.ps1 的 BaseUrl/AllowedHost/Model 参数启动服务；密钥只在隐藏交互中输入。脚本不会下载依赖、写入密钥或启用旧 Wiki 模型。
4. 前端显式选“模型研究”，使用公开示例进行真实联调。

离线跨服务：在 agent-service 目录配置现有 PYTHONPATH（.web-deps 和项目目录），运行 `.venv\Scripts\python.exe scripts/check_session_java.py --offline`。该脚本启动临时 Python HTTP，运行 Java 的 SessionHttpIntegrationTests，再关闭临时服务；搜索与模型均为夹具，H2 临时库与日常库隔离。

静态 JSON 夹具位于 Java 测试资源 model-sessions，来自 Python 会话序列化，仅用于双端契约兼容性检查，不是真实研究记录。

## 2026-10-25 证据容量

v3 模型研究允许同一来源最多 4 段互补证据，总计仍最多 8 段、12800 UTF-16 单位；v2 摘录仍为每来源最多 2 段。Python 选择器与 Java 校验同步。此容量不是来源可信度或语义支持保证。无数据库迁移。


## 2026-10-25 独立报告复核

隔离真实研究实验使用 web-model-session-v2 会话，日常 SessionRunner 默认仍为 session-v1，不把未验收的复核默认投入使用。实验仍由 /internal/v3/research/run 返回 web-research-v3 外层。阶段顺序为 plan → review → report → verify；最多 4 次模型请求（无重试循环），总时限仍 150 秒。report 是草稿，verify 对每条 claim 判定 keep/revise/remove，程序组装最终 report/outcome.answer。复核失败时保留失败阶段和证据，不发布草稿。

Java 同时读取旧 session-v1（最多 3 次）和新 session-v2（最多 4 次）；新版本有最终报告必须有成功 verify 与 report 事件。React 显示复核阶段，公开报告结构和数据库迁移不变。部署须同时更新 Java 与 Python；本轮只运行隔离环境。复核仍由同一供应商模型执行，不等于独立事实核查或必然正确。

