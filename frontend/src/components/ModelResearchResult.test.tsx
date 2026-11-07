import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModelResearchResult } from './ModelResearchResult';
import type { ModelSessionResult } from '../api/research';

it('规划失败不展示虚构计划或实时进度，外部文本只作文本',()=>{
  const result:ModelSessionResult={mode:'web-model',session:{runId:'r',planMode:'model',planReason:'MODEL_AUTH_ERROR',
    plan:null,decision:null,report:null,outcome:null,stopReason:'MODEL_AUTH_ERROR',usage:{searches:0,documents:0,modelCalls:1},
    events:[{stage:'plan',status:'FAILED',code:'MODEL_AUTH_ERROR',inputHash:'a'.repeat(64)}]}};
  const {container}=render(<ModelResearchResult result={result}/>);
  expect(screen.getByText('本次未能完成研究规划。')).toBeVisible();
  expect(screen.queryByRole('heading',{name:'研究回答与证据'})).toBeNull();
  expect(container.querySelector('progress')).toBeNull();
});
