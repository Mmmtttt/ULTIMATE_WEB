const { test, expect, hasApiCall, startApiRequestRecorder } = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 看护视频全网搜索在“同一行混合 JAVDB 横图 + JAVBUS 竖图”时的卡片布局契约，
 *   防止横图卡片被强制拉高到竖图高度导致大片留白。
 * - 测试步骤:
 *   1. mock `/api/v1/video/third-party/search` 返回一条 javdb 与一条 javbus 结果。
 *   2. 进入 `/search`，切换视频模式并在“全网搜”发起搜索。
 *   3. 校验结果区同时出现 landscape/portrait 两类封面容器。
 *   4. 断言两类封面容器高度显著不同（横图更矮），避免同高拉伸。
 * - 预期结果:
 *   1. 前端命中第三方视频搜索接口。
 *   2. `.video-cover-landscape` 与 `.video-cover-portrait` 同时存在。
 *   3. landscape 高度 < portrait 高度，且高度差明显。
 */
test("video global search mixed javdb/javbus cards keep independent cover ratios", async ({ page }) => {
  const requests = startApiRequestRecorder(page);
  const searchQueries = [];

  await page.route("**/api/v1/video/third-party/search**", async (route) => {
    const url = new URL(route.request().url());
    searchQueries.push({
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
          platform: "all",
          page: 1,
          total_pages: 1,
          has_next: false,
          videos: [
            {
              id: "JVID-DB-1",
              title: "JAVDB Landscape Card",
              code: "DB-001",
              platform: "javdb",
              cover_url: "/static/default/default_cover.jpg",
              actors: ["A"],
            },
            {
              id: "JVID-BUS-1",
              title: "JAVBUS Portrait Card",
              code: "BUS-001",
              platform: "javbus",
              cover_url: "/static/default/default_cover.jpg",
              actors: ["B"],
            },
          ],
        },
      }),
    });
  });

  await page.addInitScript(() => {
    window.localStorage.setItem("app_mode", "video");
  });

  await page.goto("/search");
  const searchInput = page.locator("input[type='search']").first();
  await expect(searchInput).toBeVisible();
  await searchInput.fill("mixed-layout");
  await searchInput.press("Enter");

  await page.locator(".van-tab").nth(2).click();
  await expect(page.locator(".remote-result-card")).toHaveCount(2);
  await expect(page.locator(".card-cover.video-cover-landscape")).toHaveCount(1);
  await expect(page.locator(".card-cover.video-cover-portrait")).toHaveCount(1);

  const dimensions = await page.evaluate(() => {
    const landscape = document.querySelector(".card-cover.video-cover-landscape");
    const portrait = document.querySelector(".card-cover.video-cover-portrait");
    if (!landscape || !portrait) {
      return null;
    }
    const l = landscape.getBoundingClientRect();
    const p = portrait.getBoundingClientRect();
    return {
      landscapeHeight: l.height,
      portraitHeight: p.height,
      landscapeRatio: l.width / Math.max(1, l.height),
      portraitRatio: p.width / Math.max(1, p.height),
      heightDelta: Math.abs(l.height - p.height),
    };
  });

  expect(dimensions).not.toBeNull();
  expect(dimensions.landscapeHeight).toBeLessThan(dimensions.portraitHeight);
  expect(dimensions.landscapeRatio).toBeGreaterThan(dimensions.portraitRatio);
  expect(dimensions.heightDelta).toBeGreaterThan(20);

  expect(searchQueries.length).toBeGreaterThan(0);
  expect(searchQueries[0].keyword).toBe("mixed-layout");
  expect(hasApiCall(requests, "/api/v1/video/third-party/search")).toBeTruthy();
});
