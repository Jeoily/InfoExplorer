import { Alert, Button, Empty, Select, Spin } from "antd";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { request, type Page } from "../../api/research";
import { StatusBadge, labels } from "../../components/StatusBadge";
export default function TaskList() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("page") || "0";
  const page = /^\d+$/.test(raw) && Number(raw) <= 10000 ? Number(raw) : 0;
  const status = params.get("status") || "";
  const filter = Object.hasOwn(labels, status) ? status : "";
  const query = useQuery({
    queryKey: ["tasks", page, filter],
    queryFn: ({ signal }) =>
      request<Page>(
        `?page=${page}&size=10${filter ? "&status=" + filter : ""}`,
        { signal },
      ),
    refetchInterval: 5000,
  });
  function change(next: number, nextStatus = filter) {
    setParams({
      page: String(next),
      ...(nextStatus ? { status: nextStatus } : {}),
    });
  }
  return (
    <>
      <header className="page-heading">
        <span className="eyebrow">你的探索记录</span>
        <h1>研究任务</h1>
        <p>追踪进度，回看每一次研究的结论与依据。</p>
      </header>
      <section className="paper">
        <div className="toolbar">
          <Select
            aria-label="任务状态"
            value={filter}
            onChange={(value) => change(0, value)}
            options={[
              { value: "", label: "全部状态" },
              ...Object.entries(labels).map(([value, label]) => ({
                value,
                label,
              })),
            ]}
          />
          <Button onClick={() => void query.refetch()}>刷新列表</Button>
        </div>
        {query.isPending ? (
          <Spin />
        ) : query.isError ? (
          <Alert type="error" title={query.error.message} />
        ) : (
          <>
            {!query.data.items.length ? (
              <Empty description="暂无符合条件的任务" />
            ) : (
              <div className="task-list">
                {query.data.items.map((task) => (
                  <Link
                    className="task-row"
                    key={task.id}
                    to={"/tasks/" + task.id}
                    state={{ listSearch: params.toString() }}
                  >
                    <div>
                      <h3>{task.question}</h3>
                      <small>
                        {new Date(task.createdAt).toLocaleString("zh-CN")}
                      </small>
                    </div>
                    <StatusBadge status={task.status} />
                  </Link>
                ))}
              </div>
            )}
            <div className="pagination">
              <Button disabled={page === 0} onClick={() => change(page - 1)}>
                上一页
              </Button>
              <span>第 {page + 1} 页</span>
              <Button
                disabled={!query.data.hasNext || page >= 10000}
                onClick={() => change(page + 1)}
              >
                下一页
              </Button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
