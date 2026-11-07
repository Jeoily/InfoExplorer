import type { Evidence } from "../api/research";
export function safeUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}
export function Report({
  answer,
  evidence,
}: {
  answer: string;
  evidence: Evidence[];
}) {
  const ids = new Set(evidence.map((item) => item.id));
  return (
    <div className="report-grid">
      <article className="paper">
        <h2>研究报告</h2>
        <div className="answer">
          {answer.split(/(\[E\d+\])/g).map((part, index) =>
            ids.has(part.slice(1, -1)) ? (
              <button
                key={index}
                className="citation"
                onClick={() =>
                  document
                    .getElementById("evidence-" + part.slice(1, -1))
                    ?.focus()
                }
              >
                {part}
              </button>
            ) : (
              part
            ),
          )}
        </div>
        <p className="muted">
          引用编号对应保存的资料，不代表结论已经过事实核验。
        </p>
      </article>
      <aside className="paper">
        <h2>
          证据来源 <span className="count">{evidence.length}</span>
        </h2>
        {evidence.length === 0 && <p>没有保存的结构化证据。</p>}
        {evidence.map((item) => (
          <section
            className="evidence"
            id={"evidence-" + item.id}
            key={item.id}
            tabIndex={-1}
          >
            <h3>
              {safeUrl(item.url) ? (
                <a
                  href={safeUrl(item.url)!}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  [{item.id}] {item.title} ↗
                </a>
              ) : (
                <>
                  [{item.id}] {item.title}
                </>
              )}
            </h3>
            <p>{item.excerpt}</p>
            <small>
              获取时间：{new Date(item.retrievedAt).toLocaleString("zh-CN")}
            </small>
            <details>
              <summary>摘录校验值</summary>
              <code>{item.contentHash}</code>
            </details>
          </section>
        ))}
      </aside>
    </div>
  );
}
