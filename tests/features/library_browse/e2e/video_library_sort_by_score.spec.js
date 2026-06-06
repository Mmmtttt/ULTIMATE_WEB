const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  buildPaginatedData,
} = require("../../../shared/e2e_helpers");

const VIDEO_TITLE = "Seed Video";

function buildVideo(id, title, score) {
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
 * - 用例目的: 强看护视频库"按评分排序"主链路，确保前端操作会触发正确后端参数，且页面结果顺序与评分降序一致。
 * - 测试步骤:
 *   1. 打开 `/library` 并切换到视频模式。
 *   2. 点击排序按钮，在排序面板选择"评分最高"并确认。
 *   3. 记录并校验 `/api/v1/video/list?sort_type=score&sort_order=desc` 请求。
 *   4. 获取页面卡片评分，校验顺序为降序。
 * - 预期结果:
 *   1. 至少出现一次携带 `sort_type=score&sort_order=desc` 的视频列表请求。
 *   2. 前端展示的视频评分顺序为降序。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖视频排序强看护。
 *   - 2026-03-26: 修复测试语义，确保切换到视频模式并验证视频API。
 *   - 2026-03-26: 修复选择器精确匹配，避免匹配到多个元素。
 */
test("video library sort by score keeps UI order consistent with backend sorting", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);
  const unsortedVideos = [
    buildVideo("video-low", "Low Video", 7.2),
    buildVideo("video-high", VIDEO_TITLE, 9.6),
    buildVideo("video-mid", "Mid Video", 8.4),
  ];
  const sortedVideos = [...unsortedVideos].sort((a, b) => b.score - a.score);

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
    const url = new URL(route.request().url());
    const sortType = url.searchParams.get("sort_type");
    const sortOrder = url.searchParams.get("sort_order");
    const data = sortType === "score" && sortOrder === "desc" ? sortedVideos : unsortedVideos;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: buildPaginatedData(data) }),
    });
  });

  await page.goto("/library");
  await page.locator(".mode-switch").first().click();
  const searchInput = page.locator('.toolbar-search input').first();
  await expect(searchInput).toHaveAttribute("placeholder", "实时搜索视频...");
  await searchInput.clear();

  await page.locator(".toolbar .toolbar-action-btn").first().click();
  const scoreOption = page.locator(".van-picker-column__item", { hasText: "评分最高" });
  await expect(scoreOption.first()).toBeVisible();
  await scoreOption.first().click();
  await page.locator(".van-picker__confirm").first().click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/video/list") &&
            item.url.includes("sort_type=score") &&
            item.url.includes("sort_order=desc"),
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();

  const videoCard = page.locator(".media-card").filter({ hasText: VIDEO_TITLE }).first();
  await expect(videoCard).toBeVisible();

  const scoreElements = await page.locator(".media-card .score").allTextContents();
  const scores = scoreElements
    .map((text) => parseFloat(text.replace(/[^\d.]/g, "")))
    .filter((s) => !isNaN(s));

  for (let i = 0; i < scores.length - 1; i++) {
    expect(scores[i]).toBeGreaterThanOrEqual(scores[i + 1]);
  }
});
