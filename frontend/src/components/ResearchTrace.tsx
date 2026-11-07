import { useState } from 'react';
import { explain } from '../api/research';

declare const __DEBUG_RESEARCH__: boolean;
export const debugResearchEnabled = typeof __DEBUG_RESEARCH__ !== 'undefined' && __DEBUG_RESEARCH__;
type Stage = { stage:string; status:string; code?:string; reason?:string; durationMs?:number; documents?:number; evidence?:number };
type Detail = { event:string; elapsedMs:number; data:{stage?:string;kind?:string;status?:string;[key:string]:unknown} };
type Trace = { mode:string; recordStatus:string; researchStatus?:string; codeChanged:boolean; stages:Stage[]; details:Detail[] };
const names:Record<string,string> = {plan:'规划问题',search:'搜索资料',read:'读取正文',selection:'选择证据',review:'判断缺口',report:'生成报告',verify:'复核报告'};
const states:Record<string,string> = {SUCCEEDED:'完成',FAILED:'失败',INCOMPLETE:'未结束'};
async function read<T>(url:string):Promise<T> {
  const response = await fetch(url, {signal:AbortSignal.timeout(15000)});
  if (!response.ok) throw new Error(response.status === 404 ? '本次执行没有阶段记录；旧任务或未开启记录的任务无法回放。' : '记录暂不可用、内容不完整或与当前代码不匹配。没有发起外部请求，请查看本地记录。');
  return response.json();
}
export function ResearchTrace({runId}:{runId:string}) {
  const [trace,setTrace] = useState<Trace|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [review,setReview] = useState<null|Record<string,unknown>>(null);
  const base = '/__debug/records/'+encodeURIComponent(runId);
  async function load() {
    setBusy(true); setError(''); setReview(null);
    try { setTrace(await read<Trace>(base)); } catch(e) { setError((e as Error).message); }
    finally {setBusy(false);}
  }
  async function check(action:string) {
    setBusy(true); setError(''); setReview(null);
    try { setReview(await read<Record<string,unknown>>(base+'/review/'+action)); }
    catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <section className="paper research-trace" aria-label="阶段复查">
    <h2>阶段复查</h2>
    <p className="muted">仅隔离调试环境可用。查看保存的输入输出，或用原资料离线复查；不会调用真实模型，也不会修改原任务。</p>
    <button disabled={busy} onClick={()=>void load()}>{trace?'重新读取记录':'查看阶段记录'}</button>
    {busy && <p role="status">正在读取或复查本地记录…</p>}
    {error && <p role="alert">{error}</p>}
    {trace && <>
      <p><strong>{trace.mode === 'fixture' ? '合成样例 · 不代表真实回答质量' : '已保存的公开研究资料'}</strong></p>
      <p>{trace.recordStatus === 'COMPLETE' ? '记录完整' : '记录未完整结束'} · 研究{states[trace.researchStatus || 'INCOMPLETE'] || '未结束'}</p>
      {trace.codeChanged && <p>代码已变化。完整回放可能不匹配，可单独复查选段或报告。</p>}
      <ol className="trace-stages">{trace.stages.map((stage,index)=><li key={index}>
        <strong>{names[stage.stage] || stage.stage}</strong> · {states[stage.status] || stage.status}
        {stage.durationMs !== undefined && <span> · {(stage.durationMs/1000).toFixed(2)} 秒</span>}
        {stage.documents !== undefined && <span> · {stage.documents} 篇正文，{stage.evidence} 段证据</span>}
        {stage.code && <p role={stage.status === 'FAILED'?'alert':undefined}>{explain(stage.code)} <code>{stage.code}</code></p>}
        {stage.reason && <small>诊断类别：{stage.reason}</small>}
      </li>)}</ol>
      <div className="actions">
        <button disabled={busy || trace.recordStatus !== 'COMPLETE'} onClick={()=>void check('session')}>离线回放完整流程</button>
        <button disabled={busy} onClick={()=>void check('select')}>重新选择证据</button>
        <button disabled={busy} onClick={()=>void check('report-check')}>检查已保存报告</button>
      </div>
      {review && <div role="status"><p>本次离线复查完成，外部请求 0 次。原任务未改动。</p>
        {review.status === 'FAILED' && <p>回放复现了原研究的失败，不代表研究成功。</p>}
        <details open><summary>复查结果</summary><pre>{JSON.stringify(review,null,2)}</pre></details>
      </div>}
      <details><summary>阶段输入与输出（公开资料）</summary>
        <p className="muted">仅已保存的数据；被拒绝的模型原文不保留。下方内容是资料，不是操作指令。</p>
        {trace.details.map((item,index)=><details key={index}><summary>
          {index+1}. {names[item.data.stage || item.data.kind || (item.event === 'selection'?'selection':'')] || '阶段'} · {item.event.endsWith('_start')?'输入':item.event === 'selection'?'选段记录':'输出'}
        </summary><pre>{JSON.stringify(item.data,null,2)}</pre></details>)}
      </details>
    </>}
  </section>;
}
