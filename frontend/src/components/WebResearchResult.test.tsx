import { expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { WebResearchResult } from './WebResearchResult';
import type { WebResult } from '../api/research';

it('失败仍显示证据，拒绝危险外链，引用只定位当前快照', () => {
  const result: WebResult = {mode:'web-extract',outcome:{
    runId:'run-a',status:'FAILED',completionReason:'EXECUTION_DEADLINE',coverage:'partial',answer:'[E1] [E9]',
    evidence:[{evidenceId:'E1',sourceId:'S1',excerpt:'<script>bad()</script>',evidenceKey:'key',truncated:true}],
    sources:[{candidate:{sourceId:'S1',title:'公开资料',canonicalUrl:'javascript:alert(1)',host:'example.org'},status:'READ',errorCode:null,metadata:null}],
    queries:[{query:'public topic',status:'SUCCEEDED',warnings:['SEARCH_ENGINES_PARTIALLY_UNAVAILABLE'],errorCode:null}],
    usage:{searches:1,documents:1,modelCalls:0},
  }};
  const {container}=render(<WebResearchResult result={result}/>);
  expect(screen.getByRole('status')).toHaveTextContent('下方保留已获得的资料');
  expect(screen.getByText('<script>bad()</script>')).toBeVisible();
  expect(container.querySelector('script')).toBeNull();
  expect(screen.queryByRole('link',{name:/打开来源/})).toBeNull();
  expect(screen.queryByRole('link',{name:'[E9]'})).toBeNull();
  const article = container.querySelector('article')!;
  article.scrollIntoView = vi.fn();
  fireEvent.click(screen.getByRole('link',{name:'[E1]'}));
  expect(document.activeElement).toBe(article);
  fireEvent.click(screen.getByText('检索与网页读取记录'));
  expect(screen.getByText(/部分搜索引擎暂不可用/)).toBeVisible();
});
