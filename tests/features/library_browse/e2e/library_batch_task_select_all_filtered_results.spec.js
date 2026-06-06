const {
  test,
  expect,
  confirmDialog,
  buildPaginatedData,
} = require("../../../shared/e2e_helpers");

function ok(data, msg = "成功") {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      code: 200,
      msg,
      data,
    }),
  };
}

test("library batch task uses all filtered results instead of only current page", async ({ page }) => {
  const items = Array.from({ length: 21 }, (_, index) => ({
    id: `LOCALBATCH${String(index + 1).padStart(3, "0")}`,
    title: `Batch Comic ${String(index + 1).padStart(2, "0")}`,
    cover_path: `/static/mock/batch-${index + 1}.jpg`,
    current_page: 1,
    total_page: 12,
    score: 8.5,
    tag_ids: [],
    list_ids: [],
  }));

  const batchCalls = [];
  let latestUiState = null;

  await page.route("https://api.github.com/repos/Mmmtttt/ULTIMATE_WEB/releases/latest", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tag_name: "0.0.0",
        html_url: "https://github.com/Mmmtttt/ULTIMATE_WEB/releases",
      }),
    });
  });

  await page.route("**/api/v1/ui-state**", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill(ok({ state: latestUiState }));
      return;
    }
    if (request.method() === "PUT") {
      const body = JSON.parse(request.postData() || "{}");
      latestUiState = body.state || null;
      await route.fulfill(ok({ ok: true }));
      return;
    }
    if (request.method() === "DELETE") {
      latestUiState = null;
      await route.fulfill(ok({ ok: true }));
      return;
    }
    await route.fallback();
  });

  await page.route("**/api/v1/list/list**", async (route) => {
    await route.fulfill(ok([]));
  });

  await page.route("**/api/v1/author/list**", async (route) => {
    await route.fulfill(ok([]));
  });

  await page.route("**/api/v1/tag/list**", async (route) => {
    await route.fulfill(ok([]));
  });

  await page.route("**/api/v1/comic/list**", async (route) => {
    const url = new URL(route.request().url());
    const shouldPaginate = url.searchParams.get("paginate") === "1";
    if (shouldPaginate) {
      await route.fulfill(ok(buildPaginatedData(items.slice(0, 20), { total: items.length, page: 1, pageSize: 20 })));
      return;
    }
    await route.fulfill(ok(items));
  });

  await page.route("**/api/v1/config/system**", async (route) => {
    await route.fulfill(ok({
      runtime: {
        runtime_profile: "full",
        third_party_enabled: true,
        mobile_core: false,
      },
    }));
  });

  await page.route("**/api/v1/comic/local-metadata/refresh/batch", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    batchCalls.push(body);
    await route.fulfill(ok({
      task_id: "task-library-batch",
      count: Array.isArray(body.comic_ids) ? body.comic_ids.length : 0,
      task_type: "comic_local_metadata_refresh",
    }, "批量补全任务已创建"));
  });

  await page.route("**/api/v1/comic/import/tasks**", async (route) => {
    await route.fulfill(ok({
      tasks: [],
      count: 0,
    }));
  });

  await page.goto("/library");
  await expect(page.getByText("Batch Comic 01")).toBeVisible();

  await page.locator(".toolbar .toolbar-action-btn").last().click();
  await page.getByText("批量管理").click();

  await page.locator(".manage-bar").getByText("全选").click();
  await expect(page.locator(".selection-info")).toContainText("已选 21 项");

  await page.locator(".manage-bar").getByText("批量处理").click();
  await page.getByText("批量补全信息").click();
  await confirmDialog(page);

  await expect.poll(() => batchCalls.length).toBe(1);
  expect(batchCalls[0].comic_ids).toHaveLength(21);
  expect(batchCalls[0].comic_ids[0]).toBe("LOCALBATCH001");
  expect(batchCalls[0].comic_ids[20]).toBe("LOCALBATCH021");
});
