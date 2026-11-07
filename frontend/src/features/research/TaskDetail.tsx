import { useRef, useState } from "react";
import { Alert, Button, Modal, Spin } from "antd";
import { Link, useLocation, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  explain,
  request,
  retryTask,
  type Task,
  type Run,
  type WebResult,
  type ModelSessionResult,
} from "../../api/research";
import { StatusBadge, labels } from "../../components/StatusBadge";
import { Report } from "../../components/Report";
import { WebResearchResult } from "../../components/WebResearchResult";
import { ModelResearchResult } from "../../components/ModelResearchResult";
export default function TaskDetail() {
  const { id = "" } = useParams();
  return <Detail key={id} id={id} />;
}
function Detail({ id }: { id: string }) {
  const location = useLocation(),
    client = useQueryClient(),
    [target, setTarget] = useState<string | null>(null),
    [snapshotId, setSnapshotId] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    lock = useRef(false);
  const valid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
  const task = useQuery({
    queryKey: ["task", id],
    enabled: valid,
    queryFn: ({ signal }) => request<Task>("/" + id, { signal }),
    refetchInterval: (q) =>
      q.state.data && ["SUCCEEDED", "FAILED"].includes(q.state.data.status)
        ? false
        : 5000,
  });
  const runs = useQuery({
    queryKey: ["runs", id, task.data?.updatedAt, task.data?.status],
    enabled: valid && !!task.data,
    queryFn: ({ signal }) => request<Run[]>("/" + id + "/runs", { signal }),
  });
  const progress = useQuery({
    queryKey:['progress',id,task.data?.runId,task.data?.status],
    enabled:valid && !!task.data,
    queryFn:({signal})=>request<{runId:string|null;stage:string;cancelRequested:boolean;reused:number;updatedAt:string}>(`/${id}/progress`,{signal}),
    refetchInterval:task.data?.status==='RUNNING'?1500:false,
  });
  async function cancel() {
    if(lock.current || !task.data) return;
    lock.current=true; setBusy(true); setError('');
    try {
      const result=await request<Task>(`/${id}/cancel`,{method:'POST',body:JSON.stringify({expectedRunId:task.data.runId})});
      client.setQueryData(['task',id],result);
      await progress.refetch();
      await refresh();
    } catch(e) { setError((e as Error).message); await refresh(); }
    finally {lock.current=false;setBusy(false);}
  }
  async function refresh() {
    await Promise.all([task.refetch(), runs.refetch()]);
  }
  const snapshot = useQuery({
    queryKey: ['web-snapshot', id, snapshotId, task.data?.researchMode],
    enabled: valid && !!snapshotId,
    retry: false,
    queryFn: ({signal}) => request<WebResult | ModelSessionResult>(`/${id}/runs/${snapshotId}/${task.data?.researchMode === "web-model" ? "model-session" : "web-result"}`, {signal}),
  });
  async function retry() {
    if (!target || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await retryTask(id, target);
      client.setQueryData(["task", id], result);
      void client.invalidateQueries({ queryKey: ["runs", id] });
      void client.invalidateQueries({ queryKey: ["tasks"] });
      setTarget(null);
    } catch (e) {
      setError((e as Error).message);
      setTarget(null);
      await refresh();
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  if (!valid) return <Alert type="error" title="任务地址无效" />;
  if (task.isPending)
    return (
      <div role="status">
        <Spin /> 正在读取任务…
      </div>
    );
  if (!task.data)
    return (
      <Alert
        type="error"
        title={task.error?.message || "暂时无法读取任务"}
        action={<Button onClick={() => void task.refetch()}>重新读取</Button>}
      />
    );
  const data = task.data;
  const empty = data.status === 'SUCCEEDED' && !!data.result && data.result.evidence?.length === 0 && data.result.provider !== 'legacy-mock';
  const capped = (runs.data?.length || 0) >= 5;
  return (
    <>
      <Link
        to={
          "/tasks" +
          (location.state?.listSearch ? "?" + location.state.listSearch : "")
        }
      >
        ← 返回研究任务
      </Link>
      <header className="page-heading detail-heading">
        {data.errorCode==='EXECUTION_CANCELLED'?<span className="status">已取消</span>:<StatusBadge status={data.status} />}
        {empty && <span className="status">未找到资料</span>}
        <h1>{data.question}</h1>
        <small>创建于 {new Date(data.createdAt).toLocaleString("zh-CN")}</small>
      </header>
      {task.isError && (
        <Alert type="warning" title="刷新失败，当前显示上次读取的记录" />
      )}
      <section className="paper progress">
        <div>
          <strong>
            {data.status === "SUCCEEDED"
              ? empty ? "检索完成，未找到可用资料" : data.researchMode === 'web' ? "网页检索结果已保存" : data.researchMode === 'web-model' && !data.modelSession?.session.report ? "研究结束，未生成模型回答" : "报告已保存"
              : data.status === "FAILED"
                ? explain(data.errorCode)
                : data.status === "PENDING"
                  ? "任务已排队"
                  : progress.data?.cancelRequested ? '正在取消，等待当前请求结束…' :
                    ({starting:'正在连接研究服务',plan:'正在规划研究',search:'正在搜索资料',read:'正在读取网页正文',review:'正在判断资料缺口',report:'正在生成报告',verify:'正在复核报告',finished:'正在保存结果'}[progress.data?.stage || 'starting'] || '研究正在执行')}
          </strong>
          <p className="muted">{data.errorCode || "任务 ID · " + data.id}</p>
          {progress.data && progress.data.reused>0 && <p>已复用 {progress.data.reused} 项保存的检索结果或正文。</p>}
          {progress.isError && data.status==='RUNNING' && <p>阶段更新暂不可用，任务状态以刷新结果为准。</p>}
        </div>
        <div className="actions">
          <Button onClick={() => void refresh()}>刷新状态</Button>
          {['PENDING','RUNNING'].includes(data.status) && <Button loading={busy} disabled={busy || progress.data?.cancelRequested} onClick={()=>Modal.confirm({
            title:'取消本次研究？',content:'取消后不再启动后续步骤。已经发出的请求需要等待结束，供应商仍可能计费。',okText:'取消研究',cancelText:'继续研究',onOk:cancel,
          })}>取消研究</Button>}
          {data.status === "FAILED" && (
            <Button
              type="primary"
              disabled={!runs.data || runs.isError || !data.runId || capped}
              onClick={() => setTarget(data.runId)}
            >
              {capped ? "已达到 5 次上限" : data.errorCode==='EXECUTION_CANCELLED' ? '重新执行' : "重试这次失败"}
            </Button>
          )}
        </div>
      </section>
      <p className="muted">检索语言：{data.language === 'zh' ? '中文' : '英文'} · 原始问题：{data.question}</p>
      {data.modelSession && <ModelResearchResult result={data.modelSession}/>}
      {data.webResult && <WebResearchResult result={data.webResult}/>}
      {data.result?.plan && <section className="paper history" aria-label="检索计划与结果">
        <h2>检索计划与结果</h2>
        <p>{data.result.plan.mode === 'model' ? '已使用模型规划检索关键词' : '本次使用原始问题直接检索'}</p>
        {data.result.plan.intent && <p>问题理解：{data.result.plan.intent}</p>}
        {data.result.plan.mode === 'direct' && <p className="muted">{
          data.result.plan.reason === 'PLANNING_DISABLED' || data.result.plan.reason === 'MODEL_DISABLED'
            ? '检索规划未启用，没有自动拆分或翻译问题。'
            : '检索规划暂不可用或未通过校验，已退回直接检索。'
        }</p>}
        <ol>{data.result.plan.queries.map((q,i)=><li key={i}>
          <strong>{q.query}</strong> · {q.language === 'zh' ? '中文' : '英文'} Wikipedia
          <p>{q.status === 'FAILED' ? '检索失败：'+explain(q.errorCode) : `获得 ${q.resultCount} 条资料`}
          {q.evidenceIds.length > 0 ? ` · 已保存证据：${q.evidenceIds.join('、')}` : ' · 未保留证据'}</p>
        </li>)}</ol>
        <p className="muted">最多检索 3 个关键词，去重后最多保存 5 条证据。结果仅来自 Wikipedia，不保证覆盖全部问题。</p>
      </section>}
      {empty && <Alert type="info" title="本次没有获得可用证据，不代表相关资料不存在。" description="请尝试更短的主题关键词，或选择与关键词一致的检索语言。当前只搜索 Wikipedia，不会自动翻译问题。" action={<Link to="/research/new" state={{question:data.question,language:data.language}}>修改主题或语言，重新研究</Link>}/>}
      {error && <Alert type="error" title={error} />}{" "}
      {data.result && !empty && (
        <>
          <p className="muted">
            {data.result.generation
              ? "模型报告 · " + data.result.generation.model
              : "资料摘录"}{" "}
            · {data.result.provider}
          </p>
          <Report
            answer={data.result.answer}
            evidence={data.result.evidence || []}
          />
        </>
      )}
      <section className="paper history">
        <h2>执行历史</h2>
        {runs.isError ? (
          <Alert type="warning" title="执行历史读取失败，暂不可重试" />
        ) : runs.isPending ? (
          <Spin />
        ) : !runs.data?.length ? (
          <p>尚未开始执行。</p>
        ) : (
          <ol>
            {runs.data.map((run) => (
              <li key={run.id}>
                <strong>
                  第 {run.attempt} 次 · {run.errorCode==='EXECUTION_CANCELLED'?'已取消':labels[run.status]}
                </strong>
                <p>
                  {new Date(run.startedAt).toLocaleString("zh-CN")} →{" "}
                  {run.completedAt
                    ? new Date(run.completedAt).toLocaleString("zh-CN")
                    : "尚未结束"}
                </p>
                {run.errorCode && (
                  <small>
                    {explain(run.errorCode)} · {run.errorCode}
                  </small>
                )}
                {data.researchMode !== 'wikipedia' && run.completedAt && <Button onClick={() => setSnapshotId(run.id)}>查看第 {run.attempt} 次资料</Button>}
              </li>
            ))}
          </ol>
        )}
      </section>
      <Modal title="历史网页资料" open={!!snapshotId} onCancel={() => setSnapshotId(null)} footer={null} width={900}>
        {snapshot.isPending ? <Spin/> : snapshot.data ? ('session' in snapshot.data ? <ModelResearchResult result={snapshot.data}/> : <WebResearchResult result={snapshot.data}/>) : <p>这次执行没有可读取的结果快照，或读取失败。{snapshot.error?.message}</p>}
      </Modal>
      <Modal
        title="重新执行这次研究？"
        open={!!target}
        onCancel={() => {
          if (!busy) setTarget(null);
        }}
        onOk={() => void retry()}
        confirmLoading={busy}
        okText="确认重试"
        cancelText="取消"
        closable={!busy}
        mask={{ closable: !busy }}
      >
        <p>
          网页模式将优先复用上一次执行一小时内已保存且匹配的检索结果和正文；模型步骤仍会重新执行，可能消耗供应商额度。Wikipedia 模式重新检索。每个任务最多执行 5
          次，已有历史会保留。
        </p>
      </Modal>
    </>
  );
}
