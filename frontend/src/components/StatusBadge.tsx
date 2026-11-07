import type { Status } from "../api/research";
export const labels: Record<Status, string> = {
  PENDING: "等待处理",
  RUNNING: "正在研究",
  SUCCEEDED: "已完成",
  FAILED: "未完成",
};
export function StatusBadge({ status }: { status: Status }) {
  return <span className={"status " + status}>{labels[status] || status}</span>;
}
