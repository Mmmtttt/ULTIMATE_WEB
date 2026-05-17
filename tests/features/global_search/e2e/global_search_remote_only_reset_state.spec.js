const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const SEARCH_KEYWORD = "Alpha";

/**
 * 用例描述:
 * - 用例目的: 验证全网搜索页只保留远端搜索能力，且重新进入页面时不会自动恢复上一次关键字。
 * - 测试步骤:
 *   1. mock 远端漫画搜索接口并首次进入 `/search`。
 *   2. 输入关键字后执行搜索，确认命中第三方漫画搜索接口。
 *   3. 跳转离开页面，再重新进入 `/search`。
 *   4. 断言搜索框为空、结果未自动展示、也没有自动发起搜索请求。
 * - 预期结果:
 *   1. 页面仅展示“全网搜索”语义，不出现本地库/预览库切换。
 *   2. 二次进入页面时不回填上次搜索关键字。
 *   3. 只有手动触发时才调用远端搜索接口。
 */
test("global search resets previous keyword and stays remote-only", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);
  const remoteSearchCalls = [];

  await page.route("**/api/v1/comic/search-third-party**", async (route) => {
    const url = new URL(route.request().url());
    remoteSearchCalls.push({
      keyword: url.searchParams.get("keyword"),
      page: url.searchParams.get("page"),
      platform: url.searchParams.get("platform"),
    });

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          results: [
            {
              id: "JM100001",
              title: "Remote Comic Alpha",
              author: "Remote Author",
              cover_path: "/static/default/default_cover.jpg",
              score: 8.6,
              platform: "JM",
            },
          ],
          page: 1,
          has_more: false,
          platform_info: {
            JM: {
              page: 1,
              total_pages: 1,
            },
          },
        },
      }),
    });
  });

  await page.goto("/search");

  await expect(page.getByText("仅搜索全网内容，输入关键词后点击搜索或按回车触发。")).toBeVisible();
  await expect(page.getByText("本地库")).toHaveCount(0);
  await expect(page.getByText("预览库")).toHaveCount(0);

  const searchInput = page.locator("input[type='search']").first();
  await expect(searchInput).toBeVisible();
  await searchInput.fill(SEARCH_KEYWORD);
  await searchInput.press("Enter");

  await expect(page.locator(".remote-result-card", { hasText: "Remote Comic Alpha" })).toBeVisible();
  expect(remoteSearchCalls.length).toBe(1);
  expect(remoteSearchCalls[0].keyword).toBe(SEARCH_KEYWORD);
  expect(hasApiCall(apiRequests, "/api/v1/comic/search-third-party")).toBeTruthy();

  await page.goto("/library");
  await page.goto("/search");

  const freshInput = page.locator("input[type='search']").first();
  await expect(freshInput).toHaveValue("");
  await expect(page.locator(".remote-result-card")).toHaveCount(0);
  await expect(page.getByText("开始全网搜索")).toBeVisible();
  expect(remoteSearchCalls.length).toBe(1);
});
