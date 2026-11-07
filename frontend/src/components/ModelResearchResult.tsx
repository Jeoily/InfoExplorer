import type { ModelSessionResult } from '../api/research';
import { explain } from '../api/research';
import { WebResearchResult } from './WebResearchResult';
import { ResearchTrace, debugResearchEnabled } from './ResearchTrace';

const reasons: Record<string,string> = {
  EVIDENCE_SUFFICIENT:'模型判断现有资料足够，已结束检索。',
  SUPPLEMENT_ROUND_LIMIT:'已完成允许的一轮补搜；补搜后的覆盖情况未再次审核。',
  NO_PRODUCTIVE_SEARCH:'仍有资料缺口，但未找到值得继续检索的方向。',
  NO_USABLE_EVIDENCE:'未获得可用正文，未生成模型回答。',
  EXECUTION_DEADLINE:'已达到本次研究的时间上限。',
  EXECUTION_BUDGET_EXHAUSTED:'已达到本次研究的调用上限。',
};
export function ModelResearchResult({result}:{result:ModelSessionResult}) {
  const s=result.session;
  return <>
    <section className="paper history" aria-label="模型研究过程">
      <h2>研究计划与过程</h2>
      <p>{s.planMode === 'direct' ? '规划未完成，已退回原问题检索。' : s.plan ? s.plan.scope : '本次未能完成研究规划。'}</p>
      {s.planReason && <p>规划说明：{explain(s.planReason)} · {s.planReason}</p>}
      {s.plan && <><ol>{s.plan.questions.map(q=><li key={q.id}><strong>{q.question}</strong><p>需要的资料：{q.evidenceNeed}</p></li>)}</ol>
        <p>初始检索词：{s.plan.queries.join('；')}</p></>}
      {s.decision && <><h3>资料缺口判断</h3><p>{s.decision.reason}</p>
        <ul>{s.decision.coverage.map(c=><li key={c.questionId}>{c.questionId} · {c.state === 'covered' ? '模型判断已覆盖' : c.state === 'partial' ? '部分覆盖' : '资料缺失'}{c.gap && `：${c.gap}`}</li>)}</ul>
        {s.decision.queries.length>0 && <p>计划补搜：{s.decision.queries.join('；')}（实际执行见下方检索记录）</p>}</>}
      <p role="status">结束原因：{reasons[s.stopReason] || explain(s.stopReason)} <small>{s.stopReason}</small></p>
      <p>本次模型调用 {s.usage.modelCalls} 次，处理 {s.usage.searches} 次检索、{s.usage.documents} 次网页读取（含复用资料）。</p>
      <details><summary>阶段执行记录</summary><ul>{s.events.map(e=><li key={e.stage}>{({plan:'规划',review:'缺口判断',report:'报告生成',verify:'报告复核'} as Record<string,string>)[e.stage]} · {e.status === 'SUCCEEDED' ? '完成' : '失败'}{e.code && ` · ${explain(e.code)}`}</li>)}</ul>
        <p className="muted">这是执行结束后保存的记录，不是实时进度或断点恢复记录。</p></details>
    </section>
    {s.report && <section className="paper history" aria-label="回答质量说明">
      <h2>阅读提示</h2>
      <p>这是模型基于网页资料生成的回答。引用表示资料来源，不保证整句话都被资料支持；请打开原文核对重要结论。</p>
      {s.events.some(e=>e.stage === 'verify' && e.status === 'SUCCEEDED') && <p>本次经过模型复核，但复核仍可能遗漏错误，不等于事实核查。</p>}
    </section>}
    {s.outcome && <WebResearchResult result={{mode:'web-model',outcome:s.outcome}}/>}
    {debugResearchEnabled && <ResearchTrace key={s.runId} runId={s.runId}/>}
  </>;
}
