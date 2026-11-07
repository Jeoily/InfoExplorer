import { test, expect } from "@playwright/test";

test('模型研究保存计划补搜与引用，刷新和历史均可读取',async ({page})=>{
  await page.goto('/#/research/new');
  await page.getByLabel('你想探索什么主题？').fill('supplement');
  await page.getByLabel('检索方式').click();
  await page.getByTitle('模型研究',{exact:true}).click();
  await page.getByRole('button',{name:'开始研究',exact:true}).click();
  await expect(page.getByRole('heading',{name:'研究计划与过程'})).toBeVisible({timeout:15000});
  await expect(page.getByText(/已完成允许的一轮补搜/)).toBeVisible();
  await expect(page.getByRole('heading',{name:'研究回答与证据'})).toBeVisible();
  await page.getByRole('link',{name:'[E1]',exact:true}).click();
  await expect(page.locator('article:focus')).toContainText('Public topic evidence');
  await page.reload();
  await page.getByRole('button',{name:'查看第 1 次资料'}).click();
  await expect(page.getByRole('dialog').getByRole('heading',{name:'研究计划与过程'})).toBeVisible();
});

test('模型失败保留证据，历史不会伪装成成功报告',async ({page})=>{
  await page.goto('/#/research/new');
  await page.getByLabel('你想探索什么主题？').fill('fail report');
  await page.getByLabel('检索方式').click();
  await page.getByTitle('模型研究',{exact:true}).click();
  await page.getByRole('button',{name:'开始研究',exact:true}).click();
  await expect(page.getByRole('button',{name:'重试这次失败'})).toBeVisible({timeout:15000});
  await expect(page.getByText('Public topic evidence fallback.',{exact:true})).toBeVisible();
  await expect(page.getByText(/推断：A bounded inference/)).toHaveCount(0);
  await page.getByRole('button',{name:'查看第 1 次资料'}).click();
  await expect(page.getByRole('dialog').getByText('Public topic evidence fallback.',{exact:true})).toBeVisible();
});

test('网页资料与历史快照可读取，不执行网页中的 HTML', async ({page})=>{
  await page.goto('/#/research/new');
  await page.getByLabel('你想探索什么主题？').fill('PUBLIC_WEB_TOPIC');
  await page.getByLabel('检索方式').click();
  await page.getByTitle('网页摘录',{exact:true}).click();
  await page.getByRole('button',{name:'开始研究',exact:true}).click();
  await expect(page.getByRole('heading',{name:'网页资料摘录',exact:true})).toBeVisible({timeout:15000});
  await expect(page.getByText('直接检索 · 未调用模型 · 尚未验证问题覆盖度')).toBeVisible();
  await expect(page.getByText('Public evidence <img src=x onerror=alert(1)>',{exact:true})).toBeVisible();
  await expect(page.locator('article img')).toHaveCount(0);
  await page.reload();
  await page.getByRole('button',{name:'查看第 1 次资料'}).click();
  await expect(page.getByRole('dialog').getByRole('heading',{name:'网页资料摘录',exact:true})).toBeVisible();
});

test('计划与证据对应关系保存并可刷新', async ({page})=>{
  await page.goto('/#/research/new');
  await page.getByLabel('你想探索什么主题？').fill('PLAN_FIXTURE');
  await page.getByRole('button',{name:'开始研究',exact:true}).click();
  await expect(page.getByRole('heading',{name:'检索计划与结果'})).toBeVisible({timeout:15000});
  await expect(page.getByText('已使用模型规划检索关键词')).toBeVisible();
  await expect(page.getByText('获得 1 条资料 · 已保存证据：E1')).toBeVisible();
  await page.reload();
  await expect(page.getByText('问题理解：Compare public topics')).toBeVisible();
});

test("语言随任务保存，无结果可带回主题与语言", async ({ page }) => {
  await page.goto('/#/research/new');
  await page.getByLabel('你想探索什么主题？').fill('EMPTY_RESULT');
  await page.getByLabel('检索语言').click();
  await page.getByTitle('英文 Wikipedia').click();
  await page.getByRole('button', {name:'开始研究', exact:true}).click();
  await expect(page.getByText('检索完成，未找到可用资料')).toBeVisible({timeout:15000});
  await expect(page.getByText('报告已保存', {exact:true})).toHaveCount(0);
  await expect(page.getByText('检索语言：英文', {exact:false})).toBeVisible();
  await page.reload();
  await expect(page.getByText('检索完成，未找到可用资料')).toBeVisible();
  await page.getByRole('link', {name:'修改主题或语言，重新研究'}).click();
  await expect(page.getByLabel('你想探索什么主题？')).toHaveValue('EMPTY_RESULT');
  await expect(page.getByText('英文 Wikipedia', {exact:true})).toBeVisible();
});

test("迟到详情不能覆盖新任务，空列表可恢复", async ({ page }) => {
  const first = "11111111-1111-4111-8111-111111111111",
    second = "22222222-2222-4222-8222-222222222222";
  const task = (id: string) => ({
    id,
    question: id === first ? "旧任务" : "新任务",
    status: "SUCCEEDED",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    result: null,
  });
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/research-tasks/" + first, async (route) => {
    await gate;
    await route.fulfill({ json: task(first) }).catch(() => {});
  });
  await page.route("**/api/v1/research-tasks/" + second, (route) =>
    route.fulfill({ json: task(second) }),
  );
  await page.route("**/runs", (route) => route.fulfill({ json: [] }));
  await page.goto("/#/tasks/" + first);
  await page.evaluate((id) => {
    location.hash = "/tasks/" + id;
  }, second);
  await expect(page.getByRole("heading", { name: "新任务" })).toBeVisible();
  release();
  await expect(page.getByRole("heading", { name: "旧任务" })).toHaveCount(0);
  await page.route("**/api/v1/research-tasks?*", (route) =>
    route.fulfill({ json: { items: [], page: 0, size: 10, hasNext: false } }),
  );
  await page.goto("/#/tasks");
  await expect(page.getByText("暂无符合条件的任务")).toBeVisible();
  await page.goto("/#/research/new");
  await expect(page.getByLabel("你想探索什么主题？")).toBeVisible();
  await page.screenshot({
    path: "test-results/home-desktop.png",
    fullPage: true,
  });
});

test("真实 Java 隔离库：提交响应丢失后去重、报告证据、刷新恢复", async ({
  page,
}) => {
  const keys: string[] = [];
  const securityErrors: string[] = [];
  page.on("console", (msg) => {
    if (/Content Security Policy|violates.*directive/i.test(msg.text()))
      securityErrors.push(msg.text());
  });
  await page.route("**/api/v1/research-tasks", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    keys.push(route.request().headers()["idempotency-key"]);
    const response = await route.fetch();
    if (keys.length === 1) return route.abort("failed");
    await route.fulfill({ response });
  });
  await page.goto("/#/research/new");
  await page.getByLabel("你想探索什么主题？").fill("artificial intelligence");
  await page.getByRole("button", { name: "开始研究", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("提交可能已被接受");
  await page.getByRole("button", { name: "开始研究", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "研究报告", exact: true }),
  ).toBeVisible({ timeout: 15000 });
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(await page.locator(".answer img").count()).toBe(0);
  await expect(page.locator(".answer")).toContainText(
    "<img src=x onerror=alert(1)>",
  );
  await page.getByRole("button", { name: "[E1]", exact: true }).click();
  await expect(page.locator("#evidence-E1")).toBeFocused();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "研究报告", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/report-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/report-mobile.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "← 返回研究任务" }).click();
  expect(securityErrors).toEqual([]);
  await expect(
    page.locator(".task-row").filter({ hasText: "artificial intelligence" }),
  ).toHaveCount(1);
});

test("真实 Java 隔离库：失败确认取消、重复点击重试与历史保留", async ({
  page,
}) => {
  let retries = 0;
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().endsWith("/retry")) retries++;
  });
  await page.goto("/#/research/new");
  await page.getByLabel("你想探索什么主题？").fill("RETRY_ONCE");
  await page.getByRole("button", { name: "开始研究", exact: true }).click();
  await expect(page.getByRole("button", { name: "重试这次失败" })).toBeEnabled({
    timeout: 15000,
  });
  await page.getByRole("button", { name: "重试这次失败" }).click();
  await page.getByRole("button", { name: /^取\s*消$/ }).click();
  expect(retries).toBe(0);
  await page.getByRole("button", { name: "重试这次失败" }).click();
  await page
    .getByRole("button", { name: "确认重试" })
    .evaluate((button: HTMLButtonElement) => {
      button.click();
      button.click();
    });
  await expect(
    page.getByRole("heading", { name: "研究报告", exact: true }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".history li")).toHaveCount(2);
  expect(retries).toBe(1);
});

test("真实 Java 隔离库：分页、状态筛选与地址恢复", async ({
  page,
  request,
}) => {
  for (let index = 0; index < 10; index++)
    expect(
      (
        await request.post("/api/v1/research-tasks", {
          data: { question: "分页样例 " + index },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        })
      ).ok(),
    ).toBeTruthy();
  await page.goto("/#/tasks");
  await expect(page.locator(".task-row")).toHaveCount(10);
  await page.getByRole("button", { name: "下一页" }).click();
  await expect(page.locator(".pagination")).toContainText("第 2 页");
  await page.reload();
  await expect(page.locator(".pagination")).toContainText("第 2 页");
  await page.goto("/#/tasks?page=0&status=SUCCEEDED");
  await expect(page.locator(".task-row").first()).toBeVisible();
  expect(
    await page.locator(".task-row .status").allTextContents(),
  ).not.toContain("未完成");
});

test("地址错误、查询失败和重试上限明确展示", async ({ page }) => {
  await page.goto("/#/tasks/not-a-uuid");
  await expect(page.getByText("任务地址无效")).toBeVisible();
  const id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  await page.route("**/api/v1/research-tasks/" + id, (route) =>
    route.fulfill({ status: 404, json: { code: "TASK_NOT_FOUND" } }),
  );
  await page.goto("/#/tasks/" + id);
  await expect(page.getByText("未找到这个任务")).toBeVisible();
  await page.unroute("**/api/v1/research-tasks/" + id);
  const task = {
    id,
    question: "达到上限的任务",
    status: "FAILED",
    runId: id,
    errorCode: "MODEL_TIMEOUT",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    result: null,
  };
  await page.route("**/api/v1/research-tasks/" + id, (route) =>
    route.fulfill({ json: task }),
  );
  await page.route("**/api/v1/research-tasks/" + id + "/runs", (route) =>
    route.fulfill({
      json: Array.from({ length: 5 }, (_, i) => ({
        id: String(i),
        attempt: i + 1,
        status: "FAILED",
        startedAt: task.createdAt,
        completedAt: task.createdAt,
        errorCode: "MODEL_TIMEOUT",
      })),
    }),
  );
  await page.reload();
  await expect(
    page.getByRole("button", { name: "已达到 5 次上限" }),
  ).toBeDisabled();
});
