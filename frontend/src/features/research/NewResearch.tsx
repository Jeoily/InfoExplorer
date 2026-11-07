import { useRef, useState } from "react";
import { Alert, Button, Input, Select } from "antd";
import { useNavigate, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { createTask, type ResearchMode } from "../../api/research";
import { readSubmission, saveSubmission, clearSubmission } from '../../api/submission';
export default function NewResearch() {
  const location = useLocation();
  const [saved] = useState(readSubmission);
  const [question, setQuestion] = useState(typeof location.state?.question === 'string' ? location.state.question : saved?.question || ''),
    [language, setLanguage] = useState<'en'|'zh'>(location.state?.language || saved?.language || 'zh'),
    [researchMode, setResearchMode] = useState<ResearchMode>(location.state?.researchMode || saved?.researchMode || 'wikipedia'),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const lock = useRef(false),
    submission = useRef<{ question: string; language: 'en'|'zh'; researchMode: ResearchMode; key: string } | null>(saved);
  const navigate = useNavigate(),
    client = useQueryClient();
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    if (!question.trim() || question.length > 4000) {
      setError("请输入 1～4000 字符的主题");
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    if (submission.current?.question !== question || submission.current?.language !== language || submission.current?.researchMode !== researchMode)
      submission.current = { question, language, researchMode, key: crypto.randomUUID() };
    try {
      saveSubmission(submission.current);
      const task = await createTask(question, submission.current.key, language, researchMode);
      clearSubmission();
      client.setQueryData(["task", task.id], task);
      void client.invalidateQueries({ queryKey: ["tasks"] });
      navigate("/tasks/" + task.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <header className="page-heading">
        <span className="eyebrow">从好奇开始 · EXPLORE</span>
        <h1>
          让每一个问题，
          <br />
          都有据可循。
        </h1>
        <p>从公开资料出发，整理一份可以核对来源的研究报告。</p>
      </header>
      <section className="paper compose">
        <form onSubmit={submit}>
          <label htmlFor="question">你想探索什么主题？</label>
          <Input.TextArea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={4000}
            showCount
            rows={5}
            placeholder={language === 'zh' ? '例如：人工智能、软件工程（建议用主题关键词）' : '例如：artificial intelligence'}
            disabled={busy}
          />
          <div className="language-choice"><label htmlFor="research-mode">检索方式</label><Select id="research-mode" aria-label="检索方式" value={researchMode} onChange={setResearchMode} disabled={busy} options={[{value:"wikipedia",label:"Wikipedia"},{value:"web",label:"网页摘录"},{value:"web-model",label:"模型研究"}]}/></div>
          <div className="language-choice"><label htmlFor="search-language">检索语言</label><Select id="search-language" aria-label="检索语言" value={language} onChange={setLanguage} disabled={busy} options={[{value:'zh',label:researchMode !== 'wikipedia' ? '中文' : '中文 Wikipedia'},{value:'en',label:researchMode !== 'wikipedia' ? '英文' : '英文 Wikipedia'}]}/></div>
          <p className="muted">
            {researchMode === "web-model" ? "模型会规划检索、判断资料缺口并根据证据生成报告，必要时补搜一轮。会调用已配置的模型供应商并可能消耗额度。" : researchMode === "web" ? "通过搜索引擎发现网页，再读取公开正文。当前直接搜索原问题并摘录资料，不调用模型，不保证完整覆盖问题。" : "检索 Wikipedia。启用检索规划后会尝试拆解问题；未启用时直接搜索原文，建议输入所选语言的主题关键词。"}不要填写密码、密钥或私人业务资料。
          </p>
          {error && <Alert type="error" title={error} showIcon />}
          {saved && <p className="muted">已恢复上次未确认的提交；保持问题和选项不变再次提交，会查回同一个任务。</p>}
          <div className="form-actions">
            <span>公开资料 · 可核对来源</span>
            <Button type="primary" htmlType="submit" loading={busy}>
              开始研究
            </Button>
          </div>
        </form>
      </section>
      <div className="intro-grid">
        <section>
          <span>01</span>
          <h3>提出主题</h3>
          <p>选择你想了解的公开话题。</p>
        </section>
        <section>
          <span>02</span>
          <h3>整理资料</h3>
          <p>后台检索，页面展示实际处理状态。</p>
        </section>
        <section>
          <span>03</span>
          <h3>核对证据</h3>
          <p>阅读报告，回到来源判断结论。</p>
        </section>
      </div>
    </>
  );
}
