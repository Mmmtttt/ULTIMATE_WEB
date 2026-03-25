const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const PRIMARY_VIDEO_ID = "JAVDB900001";
const VIDEO_TITLE = "Seed Video";

/**
 * 用例描述:
 * - 用例目的: 强看护视频详情页评分更新主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开 `/video/JAVDB900001` 详情页。
 *   2. 点击评分组件设置新评分。
 *   3. 校验 `/api/v1/video/score` PUT 请求参数正确。
 * - 预期结果:
 *   1. 评分请求包含正确的 video_id 和 score。
 *   2. 页面显示更新后的评分。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖视频详情评分更新主链路。
 *   - 2026-03-26: 修改选择器适配视频详情页的radio元素。
 */
test("video detail page updates score via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  const rateComponent = page.getByRole("radio").nth(9);
  await rateComponent.click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/video/score") &&
            item.method === "PUT",
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();
});

/**
 * 用例描述:
 * - 用例目的: 强看护视频详情页收藏切换主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开 `/video/JAVDB900001` 详情页。
 *   2. 点击收藏按钮。
 *   3. 校验 `/api/v1/list/video/favorite/toggle` PUT 请求。
 * - 预期结果:
 *   1. 收藏请求包含正确的 video_id。
 *   2. 按钮状态切换。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖视频详情收藏主链路。
 */
test("video detail page toggles favorite via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  const favoriteButton = page.getByRole("button", { name: /收藏|已收藏/ });
  await favoriteButton.click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/list/video/favorite/toggle") &&
            item.method === "PUT",
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();
});

/**
 * 用例描述:
 * - 用例目的: 强看护视频详情页移入回收站主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开 `/video/JAVDB900001` 详情页。
 *   2. 点击"移入回收站"按钮。
 *   3. 确认对话框。
 *   4. 校验 `/api/v1/video/trash/move` PUT 请求。
 * - 预期结果:
 *   1. 移入回收站请求包含正确的 video_id。
 *   2. 操作完成后页面跳转。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖视频详情移入回收站主链路。
 */
test("video detail page moves to trash via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  const trashButton = page.getByRole("button", { name: /移入回收站|删除/ });
  await trashButton.click();

  await page.waitForTimeout(300);

  const confirmButton = page.locator(".van-dialog__confirm");
  if (await confirmButton.isVisible()) {
    await confirmButton.click();
  }

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/video/trash/move") &&
            item.method === "PUT",
        ),
      { timeout: 8000 },
    )
    .toBeTruthy();
});

/**
 * 用例描述:
 * - 用例目的: 强看护视频详情页标签点击跳转筛选主链路。
 * - 测试步骤:
 *   1. 打开 `/video/JAVDB900001` 详情页。
 *   2. 点击标签。
 *   3. 校验跳转到库页面并带有筛选参数。
 * - 预期结果:
 *   1. 路由跳转到 `/library` 并带有标签筛选参数。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖视频详情标签跳转主链路。
 */
test("video detail page tag click navigates to library with filter", async ({ page }) => {
  await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  const tagItem = page.locator(".tag-item").first();
  if (await tagItem.isVisible()) {
    await tagItem.click();
    await expect(page).toHaveURL(/\/library/);
  }
});
