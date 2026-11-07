# 持续追踪 v1

本机单用户、单 Java 实例。H2 V10 / MySQL V8。部署状态以 CURRENT_STATE 为准。

## API

路径前缀 `/api/v1/tracking-topics`，请求和响应 JSON。

| 操作 | 路径 | 约定 |
|---|---|---|
| 创建 | POST / | Idempotency-Key 必填；name、question、language、researchMode、scheduleMinutes |
| 列表 | GET / | page 0..10000、size 1..100；items/page/size/hasNext |
| 详情 | GET /{id} | 配置、状态、version、nextDueAt |
| 修改 | PUT /{id} | expectedVersion、config、status；版本冲突 409 |
| 历史配置 | GET /{id}/configs/{version} | 不可变配置快照 |
| 手动检查 | POST /{id}/cycles | Idempotency-Key 必填；相同键返回同一轮 |
| 轮次列表/详情 | GET /{id}/cycles、/{id}/cycles/{cycleId} | 包含 taskId、runId、baselineCycleId、配置版本、错过时槽数 |
| 重试 | POST /{id}/cycles/{cycleId}/retry | failedRunId；仅最新失败轮次，保留原轮身份及执行历史 |
| 变化列表 | GET /{id}/changes | 分页，当前及上次摘录、taskId、修订关系、发现时间 |

配置的 language 为 en/zh；researchMode 为 web/web-model；scheduleMinutes=0 表示手动，自动检查范围 60..10080 分钟且仅 web。主题 ACTIVE/PAUSED/ARCHIVED，归档可恢复，不删除历史。变更问题、语言或研究方式需要没有进行中轮次；单纯改名、暂停不会重置相同关注范围的比较依据。

## 轮次、修订与恢复

主题行锁保护排队、调度、归档、结果处理。任务和轮次同事务创建；一个主题最多一个 PENDING 轮次。轮次完成与来源修订/变化同事务保存，重复处理不重复插入。业务层研究重试也经过追踪规则，不能绕过轮次约束。

任务成功且有正文证据才参与比较；失败保留在研究记录中，空结果标 EMPTY，不宣称“没有变化”。比较以最终 URL、本次保留的提取正文哈希及提取器版本为依据；记录 FIRST_SEEN、UPDATED、UNCHANGED、EXTRACTOR_CHANGED。不同 URL 的相同哈希只标可能重复，不把转载当成独立证据，也不直接丢弃其来源。未再次搜到的旧 URL 不标删除。未变的页面也保存本轮观察，以便核对。

时间线是资料发现/正文修订时间，不是现实事件发生时间。摘录只覆盖保存的段落；保留正文哈希变化不保证选中的摘录也变化。来源发布时间与事件时间不自动推断。事件语义归并与矛盾判断仍是后续能力，不将哈希比较包装成理解事实。

调度与研究执行使用独立单线程调度器；每 2 秒扫描至多 20 个待汇总轮次和 10 个到期主题。全局研究队列达到 50 时不新增追踪任务。错过的时槽合并一轮；已有进行中轮次则推进时钟，不积压补跑；下次到期不会立即追赶所有历史时槽。停机恢复把正在执行的研究标为失败，追踪器随后更新对应轮次；待执行任务保留。默认不启用自动检查，无自动模型调用。

暂不支持多实例、鉴权、通知、永久删除、全文存储或无限历史读取。数据库故障会延后汇总；不会因为保存失败重新调用外部模型。前端查询显示服务错误，不能把失败当成空列表。
