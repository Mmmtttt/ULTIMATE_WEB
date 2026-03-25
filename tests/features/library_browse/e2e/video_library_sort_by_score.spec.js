const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const VIDEO_TITLE = "Seed Video";

/**
 * 用例描述:
 * - 用例目的: 强看护视频库"按评分排序"主链路，确保前端操作会触发正确后端参数，且页面结果顺序与评分降序一致。
 * - 测试步骤:
 *   1. 打开 `/library` 并切换到视频模式。
 *   2. 点击排序按钮，在排序面板选择"评分最高"并确认。
 *   3. 记录并校验 `/api/v1/video/list?sort_type=score` 请求。
 *   4. 获取页面卡片评分，校验顺序为降序。
 * - 预期结果:
 *   1. 至少出现一次携带 `sort_type=score` 的视频列表请求。
 *   2. 前端展示的视频评分顺序为降序。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖视频排序强看护。
 *   - 2026-03-26: 修复测试语义，确保切换到视频模式并验证视频API。
 *   - 2026-03-26: 修复选择器精确匹配，避免匹配到多个元素。
 */
test("video library sort by score keeps UI order consistent with backend sorting", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/library");
  await page.locator(".mode-switch").first().click();
  await expect(page.getByText("搜索视频...")).toBeVisible();

  await page.locator(".toolbar .toolbar-action-btn").first().click();
  const pickerItems = page.locator(".van-picker-column__item");
  await expect(pickerItems.nth(1)).toBeVisible();
  await pickerItems.nth(1).click();
  await page.locator(".van-picker__confirm").first().click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/video/list") &&
            item.url.includes("sort_type=score"),
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
