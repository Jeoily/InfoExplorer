export type Status = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
export type ResearchMode = 'wikipedia' | 'web' | 'web-model';
export interface Summary {
  id: string;
  question: string;
  status: Status;
  createdAt: string;
  updatedAt: string;
}
export interface Evidence {
  id: string;
  title: string;
  url: string;
  excerpt: string;
  retrievedAt: string;
  contentHash: string;
}
export interface Task extends Summary {
  researchMode: ResearchMode;
  webResult: WebResult | null;
  modelSession?: ModelSessionResult | null;
  language: 'en' | 'zh';
  runId: string | null;
  errorCode: string | null;
  result: null | {
    answer: string;
    evidence: Evidence[];
    generation: null | { model: string };
    provider: string;
    query: string;
    plan?: null | {
      mode: 'direct' | 'model';
      intent: string | null;
      reason: string | null;
      queries: {query:string; language:string; status:string; resultCount:number; evidenceIds:string[]; errorCode:string|null}[];
    };
  };
}
export interface Run {
  id: string;
  attempt: number;
  status: Status;
  startedAt: string;
  completedAt: string | null;
  errorCode: string | null;
  retryAccepted: boolean;
}
export interface Page {
  items: Summary[];
  page: number;
  size: number;
  hasNext: boolean;
}
const messages: Record<string, string> = {
  WEB_MODEL_DISABLED: "模型研究尚未启用，请先配置并启动模型研究服务",
  MODEL_CONFIG_ERROR: "模型服务配置不完整",
  WEB_DISABLED: "网页检索服务尚未启用，请启动网页研究服务",
  WEB_BUSY: "网页检索正在处理其他任务，请稍后手动重试",
  WEB_RESPONSE_TOO_LARGE: "网页结果超过保存上限",
  AGENT_INVALID_RESPONSE: "研究服务返回的数据未通过校验",
  AGENT_TIMEOUT: "研究服务响应超时",
  CONTENT_UNAVAILABLE: "未能读取网页正文",
  RESULT_PERSISTENCE_FAILED: "结果保存失败",
  TASK_NOT_FOUND: "未找到这个任务",
  INVALID_TASK_ID: "任务地址无效",
  MODEL_TIMEOUT: "模型响应超时",
  MODEL_INVALID_RESPONSE: "模型回复未通过校验",
  MODEL_AUTH_ERROR: "模型凭据配置有误",
  MODEL_RATE_LIMITED: "模型服务限流",
  MODEL_BUSY: "模型正在处理其他请求",
  SEARCH_TIMEOUT: "资料检索超时",
  SEARCH_RATE_LIMITED: "检索源限流",
  AGENT_UNAVAILABLE: "研究服务暂时无法连接",
  EXECUTION_INTERRUPTED: "上次执行被中断",
  EXECUTION_CANCELLED: "本次研究已取消",
  EXECUTION_ALREADY_STARTED: "上次请求已开始执行，请查看任务状态或手动重试",
  RETRY_CONFLICT: "任务状态已变化，请刷新后查看",
  RETRY_LIMIT_EXCEEDED: "已达到 5 次执行上限",
  STORAGE_UNAVAILABLE: "数据库暂时不可用",
};
export const explain = (code: string | null) =>
  code ? messages[code] || "本次操作未能完成" : "本次操作未能完成";
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(12000);
  const signal = options.signal
    ? AbortSignal.any([options.signal, timeout])
    : timeout;
  let response: Response;
  try {
    response = await fetch("/api/v1/research-tasks" + path, {
      ...options,
      signal,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(
      "无法连接服务或请求超时。提交可能已被接受；请保持相同内容重发，或先检查任务列表。",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(explain(body.code));
  }
  return response.json();
}
export const createTask = (question: string, key: string, language: 'en' | 'zh' = 'en', researchMode: ResearchMode = 'wikipedia') =>
  request<Task>("", {
    method: "POST",
    headers: { "Idempotency-Key": key },
    body: JSON.stringify({ question, language, researchMode }),
  });
export interface WebResult {
  mode: 'web-extract' | 'web-model';
  outcome: {
    runId: string; status: string; completionReason: string; coverage: string;
    answer: string | null;
    evidence: {evidenceId:string; sourceId:string; excerpt:string; evidenceKey:string; truncated:boolean}[];
    sources: {candidate:{sourceId:string; title:string; canonicalUrl:string; host:string}; status:string; errorCode:string|null; metadata:null|{resolvedUrl:string; retrievedAt:string; truncated:boolean}}[];
    queries: {query:string; status:string; warnings:string[]; errorCode:string|null}[];
    usage: {searches:number; documents:number; modelCalls:number};
  };
}
export interface ModelSessionResult {
  mode: 'web-model';
  session: {
    runId: string; planMode: 'direct'|'model'; planReason: string|null; stopReason: string;
    plan: null|{scope:string; questions:{id:string;question:string;evidenceNeed:string}[];queries:string[]};
    decision: null|{action:'finish'|'supplement';reason:string;coverage:{questionId:string;state:string;evidenceIds:string[];gap:string}[];queries:string[]};
    report: null|{claims:{kind:string;text:string;evidenceIds:string[]}[];limitations:string[]};
    events:{stage:string;status:string;code:string|null;inputHash:string}[];
    usage:{searches:number;documents:number;modelCalls:number};
    outcome: WebResult['outcome']|null;
  };
}
export const retryTask = (id: string, failedRunId: string) =>
  request<Task>("/" + encodeURIComponent(id) + "/retry", {
    method: "POST",
    body: JSON.stringify({ failedRunId }),
  });
