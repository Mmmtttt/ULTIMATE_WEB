const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  buildPaginatedData,
} = require("../../../shared/e2e_helpers");

const VIDEO_ID = "JAVDB900001";
const VIDEO_TITLE = "Seed Video";

function buildVideo(id, title, score = 8.8) {
  return {
    id,
    code: id,
    title,
    title_jp: "",
    creator: "Video Creator",
    actors: ["Actor A"],
    desc: `${title} detail`,
    cover_path: `/static/mock/${id}.jpg`,
    thumbnail_images: [],
    score,
    tag_ids: [],
    tags: [],
    list_ids: [],
    total_units: 1,
    current_unit: 1,
    create_time: "2026-05-17T08:00:00",
    last_access_time: "2026-05-17T09:00:00",
    is_deleted: false,
    source: "local",
  };
}

/**
 * 用例描述:
 * - 用例目的: 验证从本地库切换到视频模式后，用户可进入视频详情并触发关键后端请求。
 * - 测试步骤:
 *   1. 打开本地库页面，切换到视频模式。
 *   2. 点击目标视频卡片进入详情。
 *   3. 校验路由、页面标题和关键 API 调用。
 * - 预期结果:
 *   1. 页面出现视频模式文案与目标视频卡片。
 *   2. 路由跳转到 /video/{video_id}。
 *   3. 请求链路包含 /api/v1/video/list 与 /api/v1/video/detail。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖视频主路径浏览能力。
 */
test("library browse switches to video mode and opens video detail", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);
  const video = buildVideo(VIDEO_ID, VIDEO_TITLE);

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
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: 200, data: { state: null } }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: { ok: true } }),
    });
  });

  await page.route("**/api/v1/list/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: [] }),
    });
  });

  await page.route("**/api/v1/tag/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: [] }),
    });
  });

  await page.route("**/api/v1/comic/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: [] }),
    });
  });

  await page.route("**/api/v1/video/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: buildPaginatedData([video]) }),
    });
  });

  await page.route("**/api/v1/video/detail**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: video }),
    });
  });

  await page.goto("/library");
  await page.locator(".mode-switch").first().click();
  const searchInput = page.locator('.toolbar-search input').first();
  await expect(searchInput).toHaveAttribute("placeholder", "实时搜索视频...");
  await searchInput.clear();

  const card = page.locator(".media-card", { hasText: VIDEO_TITLE }).first();
  await expect(card).toBeVisible();
  await card.click();

  await expect(page).toHaveURL(new RegExp(`/video/${VIDEO_ID}$`));
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  expect(hasApiCall(apiRequests, "/api/v1/video/list")).toBeTruthy();
  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.url.includes("/api/v1/video/detail") &&
        item.url.includes(`video_id=${VIDEO_ID}`),
    ),
  ).toBeTruthy();
});
