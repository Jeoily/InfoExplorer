import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Report, safeUrl } from "./Report";
describe("证据安全与定位", () => {
  it("外部文本不会成为可执行 HTML，引用仅定位已存在证据", () => {
    const { container } = render(
      <Report
        answer={"<img src=x onerror=alert(1)> [E1] [E9]"}
        evidence={[
          {
            id: "E1",
            title: "公开资料",
            url: "https://example.org",
            excerpt: "<script>bad()</script>",
            retrievedAt: "2026-10-14T00:00:00Z",
            contentHash: "abc",
          },
        ]}
      />,
    );
    expect(container.querySelector("img,script")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "[E1]" }));
    expect(document.activeElement?.id).toBe("evidence-E1");
    expect(screen.queryByRole("button", { name: "[E9]" })).toBeNull();
    expect(screen.getByRole("link")).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
  });
  it("阻止非 HTTPS 及含凭据的外链", () => {
    for (const value of [
      "javascript:alert(1)",
      "http://example.org",
      "https://user:pass@example.org",
      "bad",
    ])
      expect(safeUrl(value)).toBeNull();
    expect(safeUrl("https://example.org")).toBe("https://example.org/");
  });
});
