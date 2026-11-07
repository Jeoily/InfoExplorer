import type { WebResult } from '../api/research';
import { useId } from 'react';

function safeLink(value: string) {
  try {
    const u = new URL(value);
    return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : undefined;
  } catch { return undefined; }
}

export function WebResearchResult({ result }: { result: WebResult }) {
  const o = result.outcome;
  const viewId = useId();
  const evidenceAnchor = (id: string) => `web-${viewId}-${o.runId}-${id}`;
  return <section className="paper history" aria-label="网页研究结果">
    <h2>{result.mode === 'web-model' ? '研究回答与证据' : '网页资料摘录'}</h2>
    <p>{result.mode === 'web-model' ? '基于公开证据生成；引用存在不代表结论已经事实核验。' : '直接检索 · 未调用模型 · 尚未验证问题覆盖度'}</p>
    <p className="muted">搜索 {o.usage.searches} 次，尝试读取 {o.usage.documents} 个网页，保存 {o.evidence.length} 条证据。</p>
    {o.status === 'FAILED' && <p role="status">本次未完成：{o.completionReason}。下方保留已获得的资料。</p>}
    {!o.evidence.length && <p>未获得可用正文，不代表相关资料不存在。可以调整关键词后新建任务。</p>}
    {o.answer && <div style={{whiteSpace:'pre-wrap'}}>{o.answer.split(/(\[E\d+\])/).map((part, index) => {
      const evidence = o.evidence.find(e => `[${e.evidenceId}]` === part);
      return evidence ? <a key={index} href={`#${evidenceAnchor(evidence.evidenceId)}`} onClick={event => {
        event.preventDefault();
        const element = document.getElementById(evidenceAnchor(evidence.evidenceId));
        element?.scrollIntoView({block:'center'}); element?.focus();
      }}>{part}</a> : part;
    })}</div>}
    <h3>证据与来源</h3>
    {o.evidence.map(e => {
      const source = o.sources.find(s => s.candidate.sourceId === e.sourceId);
      const url = source && safeLink(source.metadata?.resolvedUrl || source.candidate.canonicalUrl);
      return <article key={e.evidenceKey} id={evidenceAnchor(e.evidenceId)} tabIndex={-1}>
        <h4>[{e.evidenceId}] {source?.candidate.title || '公开资料'}</h4>
        {url && <a href={url} target="_blank" rel="noopener noreferrer">{source?.candidate.host} · 打开来源</a>}
        <p>{e.excerpt}</p>
        <small>{e.truncated ? '段落为截取片段 · ' : ''}{source?.metadata && `读取于 ${new Date(source.metadata.retrievedAt).toLocaleString('zh-CN')}`}</small>
      </article>;
    })}
    <details><summary>检索与网页读取记录</summary>
      {o.queries.map((q,i) => <p key={i}>{q.query} · {q.status === 'SUCCEEDED' ? '搜索完成' : '搜索失败'}{q.errorCode && ` · ${q.errorCode}`}{q.warnings.length > 0 && ' · 部分搜索引擎暂不可用，结果可能不完整'}</p>)}
      <ul>{o.sources.map(s => <li key={s.candidate.sourceId}>{s.candidate.title} · {s.candidate.host} · {s.status === 'READ' ? '正文已读取' : s.status === 'SKIPPED' ? '未读取' : '读取失败'}{s.errorCode && ` · ${s.errorCode}`}{s.metadata?.truncated && ' · 正文有截断'}</li>)}</ul>
    </details>
  </section>;
}
