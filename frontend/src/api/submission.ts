import type { ResearchMode } from './research';
export interface Submission { question:string; language:'en'|'zh'; researchMode:ResearchMode; key:string }
const name='infoexplorer.pending-submission.v1';
export function readSubmission():Submission|null {
  try {
    const value=JSON.parse(sessionStorage.getItem(name)||'null');
    return value && typeof value.question==='string' && value.question.length<=4000 &&
      ['en','zh'].includes(value.language) && ['wikipedia','web','web-model'].includes(value.researchMode) &&
      typeof value.key==='string' && /^[a-f0-9-]{36}$/.test(value.key) ? value : null;
  } catch { return null; }
}
export function saveSubmission(value:Submission) {
  // If browser persistence is unavailable, refuse sending rather than lose the key on refresh.
  try { sessionStorage.setItem(name,JSON.stringify(value)); }
  catch { throw new Error('浏览器无法保存提交记录，请允许本地存储后再提交。'); }
}
export function clearSubmission() {
  try { sessionStorage.removeItem(name); } catch { /* A saved key still safely replays the same task. */ }
}
