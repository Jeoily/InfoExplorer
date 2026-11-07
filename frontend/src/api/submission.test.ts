import {it,expect} from 'vitest';
import {readSubmission,saveSubmission,clearSubmission} from './submission';
it('ambiguous submission retains identity across reload and clears only after acknowledgement',()=>{
  const value={question:'public topic',language:'zh' as const,researchMode:'web-model' as const,key:crypto.randomUUID()};
  saveSubmission(value);
  expect(readSubmission()).toEqual(value);
  clearSubmission(); expect(readSubmission()).toBeNull();
  sessionStorage.setItem('infoexplorer.pending-submission.v1','{"question":42}');
  expect(readSubmission()).toBeNull();
  clearSubmission();
});
