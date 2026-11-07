import {useRef,useState} from 'react';
import {Alert,Button,Form,Input,Select,Spin,Empty,Tag} from 'antd';
import {useQuery,useQueryClient,useMutation} from '@tanstack/react-query';
import {Link,useNavigate} from 'react-router-dom';
import {tracking,type Topic,type Config,type Page} from '../../api/tracking';

export function TopicFields() {
 return <>
  <Form.Item name="name" label="主题名称" rules={[{required:true,whitespace:true,max:160}]}><Input maxLength={160} placeholder="例如：Python 新版本与兼容性" /></Form.Item>
  <Form.Item name="question" label="持续关注的问题" rules={[{required:true,whitespace:true,max:4000}]}><Input.TextArea rows={3} maxLength={4000} placeholder="明确你希望持续观察的公开信息" /></Form.Item>
  <Form.Item name="language" label="检索语言"><Select options={[{value:'zh',label:'中文'},{value:'en',label:'英文'}]} /></Form.Item>
  <Form.Item name="researchMode" label="检查方式"><Select options={[{value:'web',label:'网页摘录 · 不调用模型'},{value:'web-model',label:'模型研究 · 每轮会调用模型'}]} /></Form.Item>
  <Form.Item name="scheduleMinutes" label="自动检查频率" rules={[({getFieldValue})=>({validator(_,value){return value>0&&getFieldValue('researchMode')==='web-model'?Promise.reject(new Error('模型研究仅支持手动检查')):Promise.resolve();}})]} dependencies={['researchMode']}><Select options={[{value:0,label:'仅手动检查'},{value:60,label:'每小时'},{value:360,label:'每 6 小时'},{value:1440,label:'每天'}]} /></Form.Item>
 </>;
}
export const topicStates:Record<string,string>={ACTIVE:'关注中',PAUSED:'已暂停',ARCHIVED:'已归档'};
export default function Topics() {
 const [page,setPage]=useState(0); const [creating,setCreating]=useState(false);
 const navigate=useNavigate(); const client=useQueryClient(); const submission=useRef({json:'',key:crypto.randomUUID()});
 const list=useQuery({queryKey:['topics',page],queryFn:({signal})=>tracking<Page<Topic>>(`?page=${page}&size=10`,{signal})});
 const create=useMutation({mutationFn:(config:Config)=>{const json=JSON.stringify(config);if(submission.current.json!==json)submission.current={json,key:crypto.randomUUID()};return tracking<Topic>('',{method:'POST',body:json,headers:{'Idempotency-Key':submission.current.key}});},onSuccess:topic=>{void client.invalidateQueries({queryKey:['topics']});navigate('/topics/'+topic.id);}});
 return <>
 <header className="page-heading"><span className="eyebrow">把一次探索延续下去</span><h1>持续追踪</h1><p>保存关注的问题，按轮次比较资料。发现时间表示我们何时看见变化，不等同于事件发生时间。</p></header>
 <div className="toolbar"><Button type="primary" onClick={()=>setCreating(!creating)}>{creating?'收起表单':'新建追踪主题'}</Button><Button onClick={()=>void list.refetch()}>刷新</Button></div>
 {creating&&<section className="paper tracking-section"><h2>新建主题</h2><p className="muted">创建主题不会立即研究。自动检查仅在本机服务运行期间执行，默认关闭。</p><Form layout="vertical" initialValues={{language:'zh',researchMode:'web',scheduleMinutes:0}} onFinish={config=>create.mutate(config)}><TopicFields />{create.isError&&<Alert type="error" title={create.error.message}/>}<Button type="primary" htmlType="submit" loading={create.isPending}>保存主题</Button></Form></section>}
 <section className="paper tracking-section">{list.isPending?<Spin/>:list.isError?<Alert type="error" title={list.error.message}/>:<>
 {!list.data.items.length?<Empty description="还没有追踪主题"/>:<div className="task-list">{list.data.items.map(topic=><Link className="task-row" to={'/topics/'+topic.id} key={topic.id}><div><strong>{topic.name}</strong><p>{topic.question}</p><small>{topic.scheduleMinutes?`每 ${topic.scheduleMinutes/60} 小时检查`:'手动检查'}</small></div><Tag>{topicStates[topic.status]}</Tag></Link>)}</div>}
 <div className="toolbar"><Button disabled={!page} onClick={()=>setPage(page-1)}>上一页</Button><span>第 {page+1} 页</span><Button disabled={!list.data.hasNext} onClick={()=>setPage(page+1)}>下一页</Button></div></>}</section>
 </>;
}
