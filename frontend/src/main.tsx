import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
const NewResearch = React.lazy(() => import("./features/research/NewResearch"));
const TaskList = React.lazy(() => import("./features/research/TaskList"));
const TaskDetail = React.lazy(() => import("./features/research/TaskDetail"));
const Topics = React.lazy(() => import("./features/tracking/Topics"));
const TopicDetail = React.lazy(() => import("./features/tracking/TopicDetail"));
import "./styles.css";
import { debugResearchEnabled } from './components/ResearchTrace';
const client = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: true,
      refetchIntervalInBackground: false,
    },
    mutations: { retry: false },
  },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      csp={{
        nonce:
          document.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]')
            ?.content || "",
      }}
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#246b53",
          borderRadius: 10,
          fontFamily: 'Inter, "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <QueryClientProvider client={client}>
        <HashRouter>
          <div className="shell">
            <aside className="sidebar">
              <a className="brand" href="#/research/new">
                <span className="brand-icon">i</span>InfoExplorer
              </a>
              <p className="brand-sub">信息探索工作台</p>
              <nav aria-label="主导航">
                <NavLink to="/research/new">＋ 开始研究</NavLink>
                <NavLink to="/tasks">☷ 研究任务</NavLink>
                <NavLink to="/topics">◎ 持续追踪</NavLink>
              </nav>
              <div className="sidebar-note">
                <span className="live-dot" /> 本机开发版
                <p>公开资料，让探索有据可循。</p>
              </div>
            </aside>
            <main>
              {debugResearchEnabled && <p className="paper" role="note">隔离调试环境 · 与日常任务分开保存。默认使用合成样例，实际资料模式以阶段记录标注为准。</p>}
              <React.Suspense fallback={<p role="status">正在加载页面…</p>}>
                <Routes>
                  <Route path="/research/new" element={<NewResearch />} />
                  <Route path="/tasks" element={<TaskList />} />
                  <Route path="/tasks/:id" element={<TaskDetail />} />
                  <Route path="/topics" element={<Topics />} />
                  <Route path="/topics/:id" element={<TopicDetail />} />
                  <Route
                    path="/"
                    element={<Navigate to="/research/new" replace />}
                  />
                  <Route
                    path="*"
                    element={
                      <p>
                        页面不存在。<NavLink to="/tasks">返回任务列表</NavLink>
                      </p>
                    }
                  />
                </Routes>
              </React.Suspense>
              <footer>InfoExplorer · 公开网页与 Wikipedia · 以任务所选方式为准</footer>
            </main>
          </div>
        </HashRouter>
      </QueryClientProvider>
    </ConfigProvider>
  </React.StrictMode>,
);
