import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ResearchTrace } from './ResearchTrace';
afterEach(()=>vi.unstubAllGlobals());
const trace={mode:'fixture',recordStatus:'COMPLETE',researchStatus:'FAILED',codeChanged:false,
  stages:[{stage:'report',status:'FAILED',code:'MODEL_INVALID_RESPONSE',durationMs:20}],
  details:[{event:'model_start',elapsedMs:1,data:{stage:'report',input:{question:'<script>unsafe()</script>'}}}]};
it('loads on demand and distinguishes replayed failure from successful research',async()=>{
  const fetcher=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>trace})
    .mockResolvedValueOnce({ok:true,json:async()=>({status:'FAILED',externalRequests:0})});
  vi.stubGlobal('fetch',fetcher);
  const {container}=render(<ResearchTrace runId="run-1"/>);
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('查看阶段记录'));
  expect(await screen.findByText('合成样例 · 不代表真实回答质量')).toBeVisible();
  expect(container.querySelector('script')).toBeNull();
  fireEvent.click(screen.getByText('离线回放完整流程'));
  expect(await screen.findByText('回放复现了原研究的失败，不代表研究成功。')).toBeVisible();
  expect(fetcher.mock.calls[1][0]).toBe('/__debug/records/run-1/review/session');
});
it('missing records do not trigger retries or generation',async()=>{
  const fetcher=vi.fn().mockResolvedValue({ok:false,status:404});
  vi.stubGlobal('fetch',fetcher);
  render(<ResearchTrace runId="old-run"/>);
  fireEvent.click(screen.getByText('查看阶段记录'));
  expect(await screen.findByRole('alert')).toHaveTextContent('没有阶段记录');
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it('incomplete records disable full replay',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({...trace,recordStatus:'INCOMPLETE'})}));
  render(<ResearchTrace runId="incomplete"/>);
  fireEvent.click(screen.getByText('查看阶段记录'));
  expect(await screen.findByText('离线回放完整流程')).toBeDisabled();
});
