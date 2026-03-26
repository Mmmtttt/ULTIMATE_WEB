const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const VIDEO_ID = "JAVDB900001";
const VIDEO_TITLE = "Seed Video";

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

  await page.goto("/library");
  await page.locator(".mode-switch").first().click();
  await expect(page.getByText("搜索视频...")).toBeVisible();

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
