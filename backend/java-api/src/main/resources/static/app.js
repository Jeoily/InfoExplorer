'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const labels = {PENDING:'等待处理', RUNNING:'正在研究', SUCCEEDED:'已完成', FAILED:'未完成'};
  const errors = {MODEL_TIMEOUT:'模型响应超时', MODEL_INVALID_RESPONSE:'模型回复未通过校验', MODEL_RATE_LIMITED:'模型服务限流', MODEL_AUTH_ERROR:'模型凭据无效', MODEL_CONFIG_ERROR:'模型配置有误', MODEL_BUSY:'模型正在处理其他请求', SEARCH_TIMEOUT:'资料检索超时', SEARCH_RATE_LIMITED:'检索源限流', SEARCH_UNAVAILABLE:'暂时无法访问检索源', AGENT_UNAVAILABLE:'Python 服务未启动或无法连接', AGENT_TIMEOUT:'研究服务响应超时', EXECUTION_INTERRUPTED:'上次执行被中断', RETRY_LIMIT_EXCEEDED:'已达到 5 次执行上限', RETRY_CONFLICT:'任务状态已变化，请刷新后查看', STORAGE_UNAVAILABLE:'数据库暂时不可用', IDEMPOTENCY_CONFLICT:'该提交标识已用于其他问题'};
  let page=0, selected=null, current=null, hasNext=false, listVersion=0, detailVersion=0;
  let createBusy=false, retryBusy=false, retryTarget=null, pendingCreate=null;
  let listSignature='', detailSignature='';
  const date = value => value ? new Date(value).toLocaleString('zh-CN', {hour12:false}) : '—';
  const el = (tag, text, cls) => {const node=document.createElement(tag); if(text!==undefined) node.textContent=text; if(cls) node.className=cls; return node;};
  function notice(text, success=false) { $('notice').textContent=text; $('notice').className='notice'+(success?' success':''); $('notice').hidden=!text; }
  async function api(path, options={}) {
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),12000);
    try {
      const response=await fetch('/api/v1/research-tasks'+path, {...options, signal:controller.signal, headers:{'Content-Type':'application/json',...options.headers}});
      const body=await response.json();
      if(!response.ok) { const error=new Error(errors[body.code] || '请求失败，请检查服务状态后重试'); error.code=body.code; throw error; }
      return body;
    } catch(error) { if(error.code) throw error; throw new Error('暂时无法连接服务，请检查 Java 是否运行。提交失败时再次提交相同内容可避免重复创建。'); }
    finally {clearTimeout(timer);}
  }
  function badge(status) {return el('span',labels[status]||status,'badge '+status);}
  async function loadList(quiet=false) {
    const version=++listVersion, params=new URLSearchParams({page:String(page),size:'10'});
    if($('status').value) params.set('status',$('status').value);
    if(!quiet) { $('list-status').textContent='正在加载…'; $('prev').disabled=true; $('next').disabled=true; }
    try {
      const data=await api('?'+params);
      if(version!==listVersion) return;
      hasNext=data.hasNext;
      const signature=JSON.stringify(data);
      if(signature!==listSignature) {
      const focusedId=document.activeElement?.classList.contains('task-row')?document.activeElement.dataset.id:null;
      listSignature=signature; $('tasks').replaceChildren();
      for(const task of data.items) {
        const button=el('button',undefined,'task-row'); button.type='button'; button.dataset.id=task.id;
        button.setAttribute('aria-pressed',String(task.id===selected));
        button.append(el('strong',task.question)); const meta=el('span',undefined,'row-meta');
        meta.append(badge(task.status),el('span',date(task.createdAt),'muted')); button.append(meta);
        button.addEventListener('click',()=>select(task.id)); $('tasks').append(button);
      }
      if(focusedId) [...document.querySelectorAll('.task-row')].find(row=>row.dataset.id===focusedId)?.focus({preventScroll:true});
      }
      $('list-status').textContent=data.items.length ? '本页 '+data.items.length+' 项 · 最新创建在前' : '暂无符合条件的任务';
      $('page').textContent='第 '+(page+1)+' 页'; $('prev').disabled=page===0; $('next').disabled=!hasNext||page>=10000;
    } catch(error) {if(version===listVersion) {$('list-status').textContent=error.message; $('prev').disabled=page===0;}}
  }
  async function select(id) {
    if(selected!==id) {selected=id; current=null; detailSignature=''; $('detail').hidden=true; $('empty-detail').hidden=false; $('detail-title').textContent='正在读取任务…';}
    for(const row of document.querySelectorAll('.task-row')) row.setAttribute('aria-pressed',String(row.dataset.id===id));
    await loadDetail();
  }
  function renderTask(task, runs) {
    current=task; $('empty-detail').hidden=true; $('detail').hidden=false;
    let planPanel=$('search-plan');
    if(!planPanel) {planPanel=el('section',undefined,'paper');planPanel.id='search-plan';$('report-section').before(planPanel);}
    planPanel.replaceChildren();planPanel.hidden=!task.result?.plan;
    if(task.result?.plan) {
      const plan=task.result.plan;
      planPanel.append(el('h2','检索计划与结果'),el('p',plan.mode==='model'?'已使用模型规划关键词':'本次使用原始问题直接检索'));
      if(plan.intent) planPanel.append(el('p','问题理解：'+plan.intent));
      if(plan.reason) planPanel.append(el('p',['PLANNING_DISABLED','MODEL_DISABLED'].includes(plan.reason)?'规划未启用，没有自动拆分或翻译问题。':'规划暂不可用或未通过校验，已退回直接检索。'));
      for(const q of plan.queries) planPanel.append(el('p',q.query+' · '+q.language+' · '+(q.status==='FAILED'?'检索失败：'+(errors[q.errorCode]||'检索异常'):'获得 '+q.resultCount+' 条资料')+' · 保存证据：'+(q.evidenceIds.join('、')||'无')));
    }
    $('task-title').textContent=task.question; $('task-id').textContent='任务 ID · '+task.id;
    $('task-time').textContent=date(task.createdAt); $('task-status').textContent=labels[task.status]||task.status; $('task-status').className='badge '+task.status;
    $('progress').textContent=task.status==='PENDING'?'任务已排队，等待后台处理。':task.status==='RUNNING'?'正在检索公开资料并整理报告，可留在此页等待。':task.status==='FAILED'?(errors[task.errorCode]||'本次执行失败')+'（'+task.errorCode+'）':(task.result && !task.result.evidence?.length && task.result.provider!=='legacy-mock'?'检索完成，未找到可用资料。请在创建区调整主题关键词或检索语言。':'研究已完成，报告和证据已保存。');
    $('retry').hidden=task.status!=='FAILED'; $('retry').disabled=retryBusy||runs===null||runs.length>=5;
    $('retry').textContent=runs&&runs.length>=5?'已达到 5 次执行上限':'重试这次失败';
    $('report-section').hidden=!task.result; $('answer').textContent=task.result?.answer||''; $('evidence').replaceChildren();
    if(task.result) {
      $('generation').textContent=task.result.generation?'模型报告 · '+task.result.generation.model:'资料摘录';
      for(const evidence of task.result.evidence||[]) {
        const card=el('section',undefined,'evidence-card');
        const title='['+evidence.id+'] '+evidence.title;
        let safe=false; try {const url=new URL(evidence.url); safe=url.protocol==='https:'&&!url.username&&!url.password;} catch {}
        if(safe) {const link=el('a',title); link.href=evidence.url; link.target='_blank'; link.rel='noopener noreferrer'; card.append(link);} else card.append(el('strong',title));
        card.append(el('p',evidence.excerpt),el('div','获取于 '+date(evidence.retrievedAt),'muted'));
        const details=el('details'); details.append(el('summary','查看摘录校验值'),el('code',evidence.contentHash)); card.append(details); $('evidence').append(card);
      }
      if(!task.result.evidence?.length) $('evidence').append(el('p','没有保存的结构化证据。','muted'));
    }
    $('runs').replaceChildren(); $('history-status').textContent=runs===null?'执行历史读取失败，请刷新后重试。':runs.length?'共 '+runs.length+' 次执行':'尚未开始执行';
    for(const run of runs||[]) {const li=el('li'); li.append(el('strong','第 '+run.attempt+' 次 · '+(labels[run.status]||run.status)),el('div',date(run.startedAt)+' → '+date(run.completedAt),'muted')); if(run.errorCode) li.append(el('div',(errors[run.errorCode]||'执行失败')+' · '+run.errorCode,'muted')); $('runs').append(li);}
  }
  async function loadDetail() {
    if(!selected) return; const id=selected, version=++detailVersion;
    try {
      const task=await api('/'+encodeURIComponent(id));
      let runs=null; try {runs=await api('/'+encodeURIComponent(id)+'/runs');} catch {}
      if(version!==detailVersion||id!==selected) return;
      const signature=JSON.stringify([task,runs]);
      if(signature===detailSignature) return;
      detailSignature=signature;
      renderTask(task,runs);
    } catch(error) {if(version===detailVersion) {notice(error.message); $('detail-title').textContent='暂时无法读取任务';}}
  }
  $('create-form').addEventListener('submit',async event=>{
    event.preventDefault(); if(createBusy) return;
    const question=$('question').value, language=$('search-language').value;
    if(!question.trim()||question.length>4000) {notice('请输入 1～4000 字符的主题。'); return;}
    if(!pendingCreate||pendingCreate.question!==question||pendingCreate.language!==language) pendingCreate={question,language,key:crypto.randomUUID()};
    const submission=pendingCreate; createBusy=true; $('create').disabled=true; $('create').textContent='正在提交…'; notice('');
    try {
      const task=await api('',{method:'POST',headers:{'Idempotency-Key':submission.key},body:JSON.stringify({question,language})});
      pendingCreate=null; if($('question').value===question) $('question').value='';
      page=0; $('status').value=''; await select(task.id); await loadList(); notice('任务已创建，处理进度会自动更新。',true);
    } catch(error) {notice(error.message);} finally {createBusy=false; $('create').disabled=false; $('create').textContent='开始研究 ↗';}
  });
  $('status').addEventListener('change',()=>{page=0; loadList();});
  $('prev').addEventListener('click',()=>{if(page>0) {page--;loadList();}});
  $('next').addEventListener('click',()=>{if(hasNext&&page<10000) {page++;loadList();}});
  $('refresh').addEventListener('click',()=>{loadList();loadDetail();});
  $('retry').addEventListener('click',()=>{if(!current||current.status!=='FAILED'||retryBusy) return; retryTarget={id:current.id,runId:current.runId}; $('retry-dialog').showModal();});
  $('cancel-retry').addEventListener('click',()=>$('retry-dialog').close());
  $('confirm-retry').addEventListener('click',async()=>{
    if(retryBusy||!retryTarget) return; const target=retryTarget; retryBusy=true; $('retry-dialog').close(); $('retry').disabled=true;
    try {await api('/'+encodeURIComponent(target.id)+'/retry',{method:'POST',body:JSON.stringify({failedRunId:target.runId})}); notice('重试请求已接受，请查看最新进度。',true);}
    catch(error) {notice(error.message);} finally {retryBusy=false; detailSignature=''; await loadDetail(); await loadList();}
  });
  async function poll() {
    if(!document.hidden&&!retryBusy) {await loadList(true); if(selected) await loadDetail();}
    setTimeout(poll,5000);
  }
  loadList(); setTimeout(poll,5000);
})();
