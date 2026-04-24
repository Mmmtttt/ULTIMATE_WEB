const { test, expect, hasApiCall, startApiRequestRecorder } = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 看护前端“JAVDB 标签搜索下一页 + 导入到预览库”链路，防止 page 参数、追加渲染和导入 target 回归。
 * - 测试步骤:
 *   1. mock health-status/tags/search-by-tags/import 接口，并为搜索接口返回两页数据。
 *   2. 用户进入 /video-tag-search，选择标签并发起首次搜索。
 *   3. 用户点击“加载更多”触发第二页请求，确认结果列表追加。
 *   4. 用户选择第二页结果并导入到 recommendation。
 *   5. 断言 search-by-tags 的 page=1/2 请求与 import body 的 target=recommendation。
 * - 预期结果:
 *   1. 至少发生两次 search-by-tags 请求，页码分别为 1 和 2。
 *   2. 结果卡片从 1 条追加为 2 条。
 *   3. import 请求包含 video_id=JVID-2、target=recommendation、platform=javdb。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖标签搜索分页与推荐库导入前端契约。
 */
test("video tag search load more forwards page and imports to recommendation", async ({ page }) => {
  const requests = startApiRequestRecorder(page);
  const searchQueries = [];
  const importTaskBodies = [];

  await page.route("**/api/v1/comic/third-party/config", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          default_adapter: "javdb",
          adapter_order: ["javdb"],
          plugins: [
            {
              plugin_id: "video.javdb",
              config_key: "javdb",
              name: "JAVDB",
              version: "1.0.0",
              media_types: ["video"],
              capabilities: ["taxonomy.tag_search", "taxonomy.tags", "health.query.status"],
              lookup_names: ["video.javdb", "javdb", "JAVDB"],
              identity: {
                content_type: "video",
                host_id_prefix: "JAVDB",
                platform_label: "JAVDB",
                aliases: ["javdb"],
              },
              presentation: {
                media_card: {
                  cover: {
                    aspect_ratio: "16 / 9",
                    mobile_aspect_ratio: "3 / 2",
                    fit: "cover",
                  },
                  badge: {
                    show_platform_label: true,
                    label: "JAVDB",
                  },
                },
              },
              order: 30,
            },
          ],
        },
      }),
    });
  });

  await page.route("**/api/v1/video/third-party/javdb/health-status", async (route) => {
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
    const pageNum = url.searchParams.get("page");
    searchQueries.push({
      page: pageNum,
      tagIds: url.searchParams.getAll("tag_ids"),
    });

    const isSecondPage = pageNum === "2";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          page: isSecondPage ? 2 : 1,
          has_next: !isSecondPage,
          videos: [
            {
              id: isSecondPage ? "JVID-2" : "JVID-1",
              title: isSecondPage ? "Second Page Video" : "First Page Video",
              code: isSecondPage ? "TP-002" : "TP-001",
              platform: "javdb",
              cover_url: "/static/default/default_cover.jpg",
            },
          ],
        },
      }),
    });
  });

  await page.route("**/api/v1/comic/import/async", async (route) => {
    const body = route.request().postDataJSON();
    importTaskBodies.push(body);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: { task_id: "task-video-tag-002", content_type: "video" },
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

  await page.locator(".load-more .van-button").click();
  await expect(page.locator(".remote-result-card")).toHaveCount(2);

  await page.locator(".remote-result-card").nth(1).click();
  await expect(page.locator(".floating-import-bar")).toBeVisible();
  await page.locator(".floating-import-bar .van-button").click();
  await page.locator(".sheet-content .van-button").nth(1).click();

  expect(searchQueries.length).toBeGreaterThanOrEqual(2);
  expect(searchQueries[0].page).toBe("1");
  expect(searchQueries[1].page).toBe("2");
  expect(searchQueries[0].tagIds).toEqual(expect.arrayContaining(["c1=23", "c1=24"]));

  expect(importTaskBodies).toHaveLength(1);
  expect(importTaskBodies[0]).toMatchObject({
    import_type: "by_list",
    target: "recommendation",
    platform: "JAVDB",
    content_type: "video",
  });
  expect(importTaskBodies[0].comic_ids).toEqual(["JVID-2"]);

  expect(hasApiCall(requests, "/api/v1/video/third-party/javdb/search-by-tags")).toBeTruthy();
  expect(hasApiCall(requests, "/api/v1/comic/import/async")).toBeTruthy();
});
