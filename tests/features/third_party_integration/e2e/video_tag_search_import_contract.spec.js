const { test, expect, hasApiCall, startApiRequestRecorder } = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 看护前端“JAVDB 标签搜索 -> 导入”链路与后端第三方接口契约，防止 tag_ids/page/import body 参数回归。
 * - 测试步骤:
 *   1. mock JAVDB cookie-status/tags/search-by-tags/import 接口返回。
 *   2. 用户进入 /video-tag-search，必要时切换到视频模式，选择标签并执行搜索。
 *   3. 用户选择搜索结果并执行导入到本地库。
 *   4. 断言 search-by-tags 与 import 请求参数，以及前端结果渲染。
 * - 预期结果:
 *   1. search-by-tags 请求携带重复 tag_ids 和 page=1。
 *   2. import 请求 body 正确包含 video_id/target/platform。
 *   3. 页面显示搜索结果卡片并可完成导入动作。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖前端到第三方后端接口关键契约。
 */
test("video tag search forwards third-party query and import contracts", async ({ page }) => {
  const requests = startApiRequestRecorder(page);
  const searchQueries = [];
  const importBodies = [];

  await page.route("**/api/v1/video/third-party/javdb/cookie-status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: { configured: true, has_session_cookie: true, cookie_keys: ["_jdb_session", "over18"] },
      }),
    });
  });

  await page.route("**/api/v1/video/third-party/javdb/tags**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          cookie_configured: true,
          source_ready: true,
          tag_search_available: true,
          categories: [{ key: "c1", name: "Category 1", count: 2 }],
          tags: [
            { id: "c1=23", name: "Tag 23", category: "c1", category_name: "Category 1" },
            { id: "c1=24", name: "Tag 24", category: "c1", category_name: "Category 1" },
          ],
          total: 2,
        },
      }),
    });
  });

  await page.route("**/api/v1/video/third-party/javdb/search-by-tags**", async (route) => {
    const url = new URL(route.request().url());
    searchQueries.push({
      page: url.searchParams.get("page"),
      tagIds: url.searchParams.getAll("tag_ids"),
    });

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          page: 1,
          has_next: false,
          videos: [
            {
              id: "JVID-1",
              title: "Third Party Video",
              code: "TP-001",
              platform: "javdb",
              cover_url: "/static/default/default_cover.jpg",
            },
          ],
        },
      }),
    });
  });

  await page.route("**/api/v1/video/third-party/import", async (route) => {
    const body = route.request().postDataJSON();
    importBodies.push(body);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: { id: "JAVDBJVID-1" },
      }),
    });
  });

  await page.addInitScript(() => {
    window.localStorage.setItem("app_mode", "video");
  });
  await page.goto("/video-tag-search");

  await expect(page.locator(".tag-pill")).toHaveCount(2);

  await page.locator(".tag-pill").nth(0).click();
  await page.locator(".tag-pill").nth(1).click();

  await page.locator(".filter-action-btns .van-button--primary").first().click();
  await expect(page.locator(".remote-result-card")).toHaveCount(1);

  await page.locator(".remote-result-card").first().click();
  await expect(page.locator(".floating-import-bar")).toBeVisible();
  await page.locator(".floating-import-bar .van-button").click();
  await page.locator(".sheet-content .van-button--primary").first().click();

  expect(searchQueries.length).toBeGreaterThan(0);
  expect(searchQueries[0].page).toBe("1");
  expect(searchQueries[0].tagIds).toEqual(expect.arrayContaining(["c1=23", "c1=24"]));

  expect(importBodies).toHaveLength(1);
  expect(importBodies[0]).toMatchObject({
    video_id: "JVID-1",
    target: "home",
    platform: "javdb",
  });

  expect(hasApiCall(requests, "/api/v1/video/third-party/javdb/search-by-tags")).toBeTruthy();
  expect(hasApiCall(requests, "/api/v1/video/third-party/import")).toBeTruthy();
});
