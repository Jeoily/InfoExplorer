# 事件追踪设计

日期：2026-10-15。状态：方案，未实现；以网页研究首版可用为前提。不新增迁移、不启动定时任务。

## 1. 从研究到追踪

研究任务解决一个问题，追踪主题反复执行同一范围的研究，并比较新旧信息。一个主题可以关联很多研究任务，每次研究仍有自己的失败重试和执行历史。不能用研究任务的 retry 代替“下一轮追踪”，否则会混淆失败恢复和时间演进。

首版目标是技术/产品公开进展的追踪。创建主题时记录主题说明、关注问题、语言偏好、允许/排除域名、时间范围策略和是否启用模型。没有用户登录时仅在本机运行。

先交付手动“检查更新”，验证跨轮去重和时间线，再开启每日等低频调度。首版不向邮箱/聊天软件发消息；应用内更新列表足够。

## 2. 数据模型草案

以下都是未来表，不声明已在数据库存在。使用 UUID、UTC 时间和可回溯的配置版本。索引和长度在实际迁移时对齐 MySQL/H2。

| 表 | 关键字段 | 约束/作用 |
|---|---|---|
| tracking_topic | id、name、question、status、current_config_version、created_at、updated_at | status=ACTIVE/PAUSED/ARCHIVED；归档不是删除 |
| tracking_config | topic_id、version、language、scope_json、schedule_json、budget_json、created_at | UNIQUE(topic_id,version)，旧版本不可变 |
| tracking_cycle | id、topic_id、config_version、slot_key、trigger、research_task_id、baseline_cycle_id、status、started_at、completed_at | UNIQUE(topic_id,slot_key)，每轮最多关联一个新研究任务 |
| tracked_source | id、topic_id、canonical_url、first_seen_at、last_seen_at | 按 topic + URL 的规范化哈希唯一，碰撞须核对原文 |
| source_revision | id、source_id、content_hash、evidence_snapshot_json、published_at、retrieved_at | 来源修订记录，不覆盖旧正文摘录 |
| event | id、topic_id、created_at、current_revision_id | 事件稳定身份，当前展示指向一个版本 |
| event_revision | id、event_id、revision_no、kind、summary、event_time_json、created_at、supersedes_id | UNIQUE(event_id,revision_no)，变更类型与说明可审计 |
| event_evidence | revision_id、research_run_id、evidence_id、relation | 指向实际保存证据，relation=supports/contradicts/context |
| cycle_event | cycle_id、event_revision_id、change_kind | 标记本轮 NEW/UPDATED/CONFLICTING/UNCHANGED 的判断 |

最小落地时可合并纯展示字段，但 topic/cycle/run、source revision/event revision 必须保持概念区别。全文不永久保存，只保留实际用于判断的段落和必要元数据；事件的证据不能因下一轮去重而失去关联。

查询与约束按实际访问路径设计，以下仍是待迁移验证的方案：

- 到期扫描使用 topic(status,next_due_at,id)；轮次列表使用 cycle(topic_id,created_at,id)。分页采用稳定的时间加 ID 游标，避免同一时间的记录重复或遗漏。
- tracked_source 保留规范化 URL 原文与固定长度哈希，哈希索引用于定位；命中后比较原文，不能默默把碰撞当成同一网页。
- source_revision 的 hash 对应一次提取器版本下的规范化正文。保存 extractorVersion/normalizationVersion；算法版本改变时不能直接宣称网页内容发生了变化。
- event_evidence 使用复合唯一键去重，并验证 research_run 与 topic/cycle 的归属。仅验证 evidenceId 字符串存在不够，因为每次执行都会重新使用 E1 等编号。
- 事件修订、证据关联、cycle_event 和 current_revision_id 在一个短事务中保存；模型调用在事务外。保存前重新检查目标事件版本，冲突则重新读取并报告冲突，不覆盖另一修订。
- 事件处理失败与研究失败分别记录：已有研究成果仍可查看；重新处理同一 run 的事件不能再触发一次搜索。使用 (cycle_id, research_run_id, processor_version) 标识处理尝试，成功结果幂等。

真实索引选择须在临时 MySQL 上用代表性的分页/到期查询检查 EXPLAIN，再决定是否增加索引；此处不预先承诺性能数据。

## 3. 调度与幂等

Java 是唯一调度和持久化责任方。Python 不持有数据库连接，也不自行定时创建任务。

1. 保存配置时预计算下一次 UTC dueAt，显示时转换为用户时区。首版提供固定每日时刻或固定间隔，不开放任意 cron 字符串。
2. 调度器在短事务内锁定主题、检查 ACTIVE 与 dueAt，生成稳定 slot_key，插入 cycle 和 research_task，再推进 dueAt。
3. 唯一约束防止同一主题同一时槽重复入队。冲突后查询既有 cycle，不创建第二个任务；接口重发同理。
4. HTTP/搜索/模型调用都在事务外进行，不长时间占据数据库锁。
5. 调度循环与研究执行不要共享一个会被网络请求阻塞的调度线程。保持单实例，但拆分“到期入队”和“任务执行”的有界执行资源。

手动刷新必须携带幂等键，slot_key=manual:<key>，重复键复用原轮次；新键仍受到主题并发/冷却限制。自动轮次 slot_key 由计划版本和原定到期时刻生成，不能使用实际启动时刻，否则重启会绕过去重。

每主题最多一个未完成轮次（排队或运行）。到期时已有活跃轮次，则记录跳过/合并原因并推进下一时槽，不无限堆积任务。单实例通过 topic 行锁检查活跃 cycle；以后若支持多实例，须另行设计可回收租约和 fencing token。

应用停机错过多个时槽后，只生成一次补查，覆盖上次成功之后到现在的范围，并显示“错过 N 个时槽，已合并”；不自动补跑 N 次模型。首版到期检查应有每轮最大入队数量和全局队列上限。

## 4. 暂停、归档、修改、失败

- 暂停：停止新调度。已经运行的轮次默认允许完成，界面明确说明，不假装已取消外部请求。
- 归档：停止调度并从活跃列表移除；保留报告和时间线。恢复时不自动回放所有错过时槽。
- 修改范围：生成新 config_version；后续轮次采用新版本，旧轮次保持快照。若实体/范围发生实质变化，提示新建主题，避免直接比较不可比的数据。
- 执行失败：记录阶段、错误和可用证据；不推进“上次成功基线”。用户手动重试仍属于该 cycle 对应的研究任务，不再创建 cycle。
- 重启恢复：当前单实例把遗留 RUNNING 研究任务标为失败；关联 cycle 同步标为中断。不能将搜索失败记作“没有新事件”。
- 删除：首版只归档。后续清理必须检查证据引用关系、保留策略和用户明确操作，不直接级联删光历史。

## 5. 基线与变化算法

基线选择“同一主题兼容配置版本下最近一个达到可比较覆盖条件的成功轮次”。首次执行没有基线，标记首次采集，不声称所有内容刚刚发生。部分覆盖轮次可展示新增证据，但不能据此得出“已无其他更新”，也不自动替换完整基线。

第一层是确定性资料比较：

1. URL 规范化、去追踪参数，保留会改变正文的查询参数。
2. 对提取的正文/段落计算 hash，识别同 URL 未变、同 URL 修订、不同 URL 完全相同。
3. 标题和段落相似度只标记疑似重复；默认不因模型猜测直接丢弃来源。
4. 同源转载不能作为独立验证，记录 possibleDuplicateOf 和依据。

第二层是事件候选：从新/变更证据提取实体、行动、对象、时间和证据编号。模型仅给出建议；验证编号存在、时间格式和字符串长度，不能由模型直接写库。没有模型时仍可展示“新增资料”，不伪造事件聚类。

第三层是与已有事件匹配：先用主题、实体、时间窗口筛候选，再由规则或受约束模型判断 new/update/possible_duplicate/conflict。无法确定归属时保留独立候选并标记待核对，不强制合并。首版可提供人工“关联已有事件/保留独立”操作，记录修订日志。

## 6. 时间线语义

事件时间结构：rawText、start、end、precision(day/month/unknown)、timezone、basis(evidence/inferred/unknown)、evidenceIds。缺时间时按 firstSeenAt 排列并标注“发现时间”，不能编造 eventAt。

发布时间来自网页元数据或正文，可能是最后更新时间或错误数据，应保存提取方式；不能自动当作事件发生时间。晚发现的旧事件仍显示原始时间，不插入成今天的新发生事项。

时间线卡片显示：事件摘要、发生/发现时间、变化类型、来源数量、证据入口、存疑说明。来源数量不是可信度。发生冲突时并列展示不同说法及来源，不自动挑一个写成定论。

## 7. API 与前端草案

| 操作 | 候选 API | 要点 |
|---|---|---|
| 创建主题 | POST /api/v1/tracking-topics | 幂等键、范围校验；默认手动，不自动开始付费模型 |
| 列表/详情 | GET /api/v1/tracking-topics[/{id}] | 仅状态摘要，不一次返回全部证据 |
| 修改 | PATCH /api/v1/tracking-topics/{id} | expectedVersion 乐观并发检查；冲突 409 |
| 暂停/恢复/归档 | POST /api/v1/tracking-topics/{id}/actions | action + expectedVersion，重复动作安全 |
| 手动检查 | POST /api/v1/tracking-topics/{id}/cycles | 幂等键；活跃轮次冲突明确返回 |
| 轮次 | GET /api/v1/tracking-topics/{id}/cycles | 关联研究任务、基线、覆盖和错误 |
| 时间线 | GET /api/v1/tracking-topics/{id}/events | 游标分页；默认排序稳定，未知时间单独说明 |
| 修订详情 | GET /api/v1/tracking-topics/{id}/events/{eventId}/revisions | 包含引用快照、变化依据；校验从属关系 |

以上是草案，不得提前在前端放置调用不存在 API 的按钮。先做手动轮次与资料差异，再做事件提取，最后做调度。每一步接口与类型同时落地。

## 8. 必要验收

- 同一时槽/幂等键并发请求只产生一个 cycle 与 task；重复失败重试不会创建新 cycle。
- 暂停/归档不产生新调度，运行中轮次行为与界面提示一致。
- 服务重启不补跑全部历史时槽；中断轮次保留错误而非无更新。
- 两轮内容相同不重复创建事件；来源修订保留旧证据；矛盾信息不被静默覆盖。
- 日期未知、发布日期与发生日不同、中文日期、时区转换和跨日边界有明确测试。
- 模型返回不存在的引用、试图修改预算或要求系统命令时拒绝；已获得资料仍可阅读。
- MySQL/H2 迁移兼容旧研究记录；前端刷新不触发研究；预算停止不伪装成信息完整。

不承诺模型聚类的自动正确率，不建立固定问题评测集。使用确定性测试夹具验证上述行为，再用少量公开资料做真实路径验证。
