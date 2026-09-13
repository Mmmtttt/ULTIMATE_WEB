const { test, expect, hasApiCall, startApiRequestRecorder } = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 看护前端“VIDEO_ALPHA 标签搜索 -> 导入”链路与后端第三方接口契约，防止 tag_ids/page/import body 参数回归。
 * - 测试步骤:
 *   1. mock VIDEO_ALPHA health-status/tags/search-by-tags/import 接口返回。
 *   2. 用户进入 /video-tag-search，必要时切换到视频模式，选择标签并执行搜索。
 *   3. 用户选择搜索结果并执行导入到本地库。
 *   4. 断言 search-by-tags 与 import 请求参数，以及前端结果渲染。
 * - 预期结果:
 *   1. search-by-tags 请求携带重复 tag_ids 和 page=1。
 *   2. import 请求 body 正确包含 item_ids/target/platform。
 *   3. 页面显示搜索结果卡片并可完成导入动作。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖前端到第三方后端接口关键契约。
 */
test("video tag search forwards third-party query and import contracts", async ({ page }) => {
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
          default_adapter: "video_alpha",
          adapter_order: ["video_alpha"],
          adapters: {
            video_alpha: { enabled: true },
          },
          plugins: [
            {
              plugin_id: "video.video_alpha",
              config_key: "video_alpha",
              name: "VIDEO_ALPHA",
              version: "1.0.0",
              media_types: ["video"],
              capabilities: ["taxonomy.tag_search", "taxonomy.tags", "health.query.status"],
              lookup_names: ["video.video_alpha", "video_alpha", "VIDEO_ALPHA"],
              identity: {
                content_type: "video",
                host_id_prefix: "VIDEO_ALPHA",
                platform_label: "VIDEO_ALPHA",
                aliases: ["video_alpha"],
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
                    label: "VIDEO_ALPHA",
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

  await page.route("**/api/v1/video/third-party/video_alpha/health-status", async (route) => {
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

  await page.route("**/api/v1/video/third-party/video_alpha/tags**", async (route) => {
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

  await page.route("**/api/v1/video/third-party/video_alpha/search-by-tags**", async (route) => {
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
              id: "VIDA-1",
              title: "Third Party Video",
              code: "TP-001",
              platform: "video_alpha",
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
        data: { task_id: "task-video-tag-001", content_type: "video" },
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

  expect(importTaskBodies).toHaveLength(1);
  expect(importTaskBodies[0]).toMatchObject({
    import_type: "by_list",
    target: "home",
    platform: "VIDEO_ALPHA",
    content_type: "video",
  });
  expect(importTaskBodies[0].item_ids).toEqual(["VIDA-1"]);

  expect(hasApiCall(requests, "/api/v1/video/third-party/video_alpha/search-by-tags")).toBeTruthy();
  expect(hasApiCall(requests, "/api/v1/comic/import/async")).toBeTruthy();
});
