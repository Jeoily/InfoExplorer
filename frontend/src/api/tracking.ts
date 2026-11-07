export interface Config {name:string; question:string; language:'en'|'zh'; researchMode:'web'|'web-model'; scheduleMinutes:number}
export interface Topic extends Config {id:string; status:'ACTIVE'|'PAUSED'|'ARCHIVED'; version:number; nextDueAt:string|null; createdAt:string; updatedAt:string}
export interface Cycle {id:string; topicId:string; configVersion:number; trigger:string; taskId:string; runId:string|null; baselineCycleId:string|null; status:string; errorCode:string|null; createdAt:string; completedAt:string|null; missedSlots:number}
export interface Change {id:string;cycleId:string;taskId:string;kind:string;possibleDuplicate:boolean;url:string;title:string;runId:string;revisionId:string;previousRevisionId:string|null;discoveredAt:string;evidence:{excerpt:string;evidenceId:string}[];previousEvidence:{excerpt:string;evidenceId:string}[]}
export interface Page<T> {items:T[];page:number;size:number;hasNext:boolean}
const messages:Record<string,string>={TOPIC_BUSY:'这个主题已有检查在进行，请等待完成。',TOPIC_NOT_ACTIVE:'主题已暂停或归档，请先恢复。',TOPIC_VERSION_CONFLICT:'主题已更新，请刷新后再保存。',CYCLE_RETRY_CONFLICT:'这一轮不能重试，请查看最新轮次。',INVALID_TRACKING_SCHEDULE:'自动检查至少间隔一小时，且仅支持网页摘录。',TOPIC_NOT_FOUND:'未找到这个主题。',IDEMPOTENCY_CONFLICT:'相同提交编号的内容不同，请刷新后重试。',RESEARCH_QUEUE_FULL:'任务队列已满，请稍后再试。',TOPIC_LIMIT:'主题数量已达上限。'};
export async function tracking<T>(path='',options:RequestInit={}):Promise<T> {
  const timeout=AbortSignal.timeout(12000);
  let response:Response;
  try {response=await fetch('/api/v1/tracking-topics'+path,{...options,signal:options.signal?AbortSignal.any([options.signal,timeout]):timeout,headers:{'Content-Type':'application/json',...options.headers}});}
  catch {throw new Error('连接超时或服务未启动。提交可能已经接受，请先刷新确认；再次提交将复用当前编号。');}
  if(!response.ok) {const body=await response.json().catch(()=>({}));throw new Error(messages[body.code]||'操作未完成，请刷新确认后再试。');}
  return response.json();
}
