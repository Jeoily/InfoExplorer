import {useRef,useState} from 'react';
import {Alert,Button,Empty,Form,Modal,Spin,Tag} from 'antd';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {Link,useParams} from 'react-router-dom';
import {tracking,type Topic,type Config,type Cycle,type Change,type Page} from '../../api/tracking';
import {TopicFields,topicStates} from './Topics';
import {safeUrl} from '../../components/Report';
const cycleStates:Record<string,string>={PENDING:'检查中',COMPLETED:'已完成',FAILED:'检查失败',EMPTY:'未取得可用资料'};
const changeKinds:Record<string,string>={FIRST_SEEN:'首次发现',UPDATED:'正文变化',UNCHANGED:'正文未变',EXTRACTOR_CHANGED:'提取方式变化'};
const date=(value:string)=>new Date(value).toLocaleString();
function configOf(topic:Topic):Config {return {name:topic.name,question:topic.question,language:topic.language,researchMode:topic.researchMode,scheduleMinutes:topic.scheduleMinutes};}
export default function TopicDetail() {
 const {id=''}=useParams(); const client=useQueryClient(); const [edit,setEdit]=useState(false); const [confirm,setConfirm]=useState(false);
 const [cyclePage,setCyclePage]=useState(0); const [changePage,setChangePage]=useState(0); const key=useRef(crypto.randomUUID());
 const topic=useQuery({queryKey:['topic',id],queryFn:({signal})=>tracking<Topic>('/'+id,{signal}),refetchInterval:5000});
 const cycles=useQuery({queryKey:['cycles',id,cyclePage],queryFn:({signal})=>tracking<Page<Cycle>>(`/${id}/cycles?page=${cyclePage}&size=10`,{signal}),refetchInterval:5000});
 const changes=useQuery({queryKey:['changes',id,changePage],queryFn:({signal})=>tracking<Page<Change>>(`/${id}/changes?page=${changePage}&size=10`,{signal}),refetchInterval:5000});
 function refresh(){void client.invalidateQueries({queryKey:['topic',id]});void client.invalidateQueries({queryKey:['cycles',id]});void client.invalidateQueries({queryKey:['changes',id]});void client.invalidateQueries({queryKey:['topics']});}
 const check=useMutation({mutationFn:()=>tracking<Cycle>(`/${id}/cycles`,{method:'POST',headers:{'Idempotency-Key':key.current}}),onSuccess:()=>{key.current=crypto.randomUUID();setCyclePage(0);refresh();}});
 const update=useMutation({mutationFn:(value:{config:Config;status:Topic['status']})=>tracking<Topic>('/'+id,{method:'PUT',body:JSON.stringify({...value,expectedVersion:topic.data?.version})}),onSuccess:()=>{setEdit(false);refresh();}});
 const retry=useMutation({mutationFn:(cycle:Cycle)=>tracking<Cycle>(`/${id}/cycles/${cycle.id}/retry`,{method:'POST',body:JSON.stringify({failedRunId:cycle.runId})}),onSuccess:refresh});
 if(topic.isPending)return <Spin/>;
 if(topic.isError)return <Alert type="error" title={topic.error.message}/>;
 const current=topic.data; const busy=cycles.data?.items.some(c=>c.status==='PENDING')??false;
 function start(){if(current.researchMode==='web-model')setConfirm(true);else check.mutate();}
 return <>
 <Link to="/topics">← 返回追踪主题</Link><header className="page-heading"><Tag>{topicStates[current.status]}</Tag><h1>{current.name}</h1><p>{current.question}</p><small>{current.researchMode==='web-model'?'模型研究':'网页摘录'} · {current.scheduleMinutes?`每 ${current.scheduleMinutes/60} 小时检查`:'仅手动检查'}{current.nextDueAt&&` · 下次计划 ${date(current.nextDueAt)}`}</small></header>
 <div className="toolbar"><Button type="primary" disabled={busy||current.status!=='ACTIVE'} loading={check.isPending} onClick={start}>现在检查</Button><Button onClick={()=>setEdit(!edit)}>编辑主题</Button><Button loading={update.isPending} onClick={()=>update.mutate({config:configOf(current),status:current.status==='ACTIVE'?'PAUSED':'ACTIVE'})}>{current.status==='ACTIVE'?'暂停追踪':'恢复追踪'}</Button><Button disabled={current.status==='ARCHIVED'} onClick={()=>update.mutate({config:configOf(current),status:'ARCHIVED'})}>归档</Button><Button onClick={refresh}>刷新</Button></div>
 {[check,update,retry].filter(m=>m.isError).map((m,i)=><Alert key={i} type="error" title={m.error?.message}/>)}
 {edit&&<section className="paper tracking-section"><h2>编辑关注范围</h2><p className="muted">修改问题、语言或研究方式后，将按新的关注范围建立比较基线。已有轮次保留原配置。</p><Form key={current.version} layout="vertical" initialValues={configOf(current)} onFinish={config=>update.mutate({config,status:current.status})}><TopicFields/><Button htmlType="submit" type="primary" loading={update.isPending}>保存修改</Button></Form></section>}
 <section className="paper tracking-section"><h2>检查轮次</h2><p className="muted">失败重试保留在原轮次。服务停止期间错过的定时检查会合并，不逐次补跑。</p>{cycles.isPending?<Spin/>:cycles.isError?<Alert type="error" title={cycles.error.message}/>:<>{!cycles.data.items.length?<Empty description="尚未检查，点击“现在检查”开始"/>:cycles.data.items.map((cycle,index)=><article className="tracking-item" key={cycle.id}><div className="toolbar"><Tag>{cycleStates[cycle.status]||cycle.status}</Tag><span>{date(cycle.createdAt)}</span><span>{cycle.trigger==='SCHEDULED'?'定时检查':'手动检查'}</span></div><p><Link to={'/tasks/'+cycle.taskId}>查看本轮报告与来源 →</Link></p><small>配置版本 {cycle.configVersion}{cycle.missedSlots>0&&` · 合并 ${cycle.missedSlots} 个错过的时段`}{cycle.errorCode&&` · ${cycle.errorCode}`}</small>{cycle.status==='FAILED'&&index===0&&cyclePage===0&&current.status==='ACTIVE'&&<p><Button loading={retry.isPending} onClick={()=>current.researchMode==='web-model'?Modal.confirm({title:'重试模型研究？',content:'将再次调用已配置的模型服务，请确认当前计费与额度。',onOk:()=>retry.mutateAsync(cycle)}):retry.mutate(cycle)}>重试本轮</Button></p>}</article>)}<Pager page={cyclePage} next={cycles.data.hasNext} setPage={setCyclePage}/></>}</section>
 <section className="paper tracking-section"><h2>资料变化时间线</h2><p className="muted">这里记录发现时间与正文比较结果，不自动认定真实事件、删除、矛盾或事实成立。“未变”也仅指本次读到的资料。</p>{changes.isPending?<Spin/>:changes.isError?<Alert type="error" title={changes.error.message}/>:<>{!changes.data.items.length?<Empty description="还没有可比较的资料"/>:changes.data.items.map(change=><article className="tracking-item" key={change.id}><div className="toolbar"><Tag>{changeKinds[change.kind]||change.kind}</Tag><small>{date(change.discoveredAt)}</small>{change.possibleDuplicate&&<Tag>可能为相同正文</Tag>}</div><h3>{safeUrl(change.url)?<a href={safeUrl(change.url)!} target="_blank" rel="noopener noreferrer">{change.title}</a>:change.title}</h3><small>{change.url}</small>{change.previousEvidence.length>0&&<details><summary>查看上次保存的摘录</summary>{change.previousEvidence.map((e,i)=><p key={i}>{e.excerpt}</p>)}</details>}{change.evidence.map((e,i)=><p key={i}>{e.excerpt}</p>)}<p><Link to={'/tasks/'+change.taskId}>查看对应轮次报告 →</Link></p></article>)}<Pager page={changePage} next={changes.data.hasNext} setPage={setChangePage}/></>}</section>
 <Modal title="开始模型研究？" open={confirm} onCancel={()=>setConfirm(false)} onOk={()=>{setConfirm(false);check.mutate();}}><p>本轮会调用已配置的模型服务，请确认当前计费与剩余额度。模型研究不会自动定时运行。</p></Modal>
 </>;
}
function Pager({page,next,setPage}:{page:number;next:boolean;setPage:(value:number)=>void}){return <div className="toolbar"><Button disabled={!page} onClick={()=>setPage(page-1)}>上一页</Button><span>第 {page+1} 页</span><Button disabled={!next} onClick={()=>setPage(page+1)}>下一页</Button></div>;}
