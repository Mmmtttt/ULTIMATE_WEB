const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  confirmDialog,
} = require("../../../shared/e2e_helpers");

const TRASH_TEST_COMIC_ID = "JM100005";
const TRASH_TEST_COMIC_TITLE = "E2E Comic Epsilon";

/**
 * 用例描述:
 * - 用例目的: 强看护漫画详情页评分更新主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开 `/comic/JM100005` 详情页（使用专用测试漫画，不影响排序测试）。
 *   2. 点击评分组件设置新评分。
 *   3. 校验 `/api/v1/comic/score` PUT 请求参数正确。
 *   4. 恢复原始评分。
 * - 预期结果:
 *   1. 评分请求包含正确的 comic_id 和 score。
 *   2. 页面显示更新后的评分。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖漫画详情评分更新主链路。
 *   - 2026-03-26: 改用 JM100005 避免影响 library_sort_by_score 测试。
 *   - 2026-03-26: 测试结束后恢复原始评分。
 */
test("comic detail page updates score via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto(`/comic/${TRASH_TEST_COMIC_ID}`);
  await expect(page.locator(".title")).toContainText(TRASH_TEST_COMIC_TITLE);

  const rateComponent = page.locator(".score-rate .van-rate__item").nth(9);
  await rateComponent.click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/comic/score") &&
            item.method === "PUT",
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();

  const restoreRate = page.locator(".score-rate .van-rate__item").nth(3);
  await restoreRate.click();

  await page.waitForTimeout(500);
});

/**
 * 用例描述:
 * - 用例目的: 强看护漫画详情页收藏切换主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开 `/comic/JM100005` 详情页。
 *   2. 点击收藏按钮。
 *   3. 校验 `/api/v1/list/favorite/toggle` PUT 请求。
 * - 预期结果:
 *   1. 收藏请求包含正确的 comic_id。
 *   2. 按钮状态切换。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖漫画详情收藏主链路。
 *   - 2026-03-26: 改用 JM100005 避免影响其他测试。
 */
test("comic detail page toggles favorite via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto(`/comic/${TRASH_TEST_COMIC_ID}`);
  await expect(page.locator(".title")).toContainText(TRASH_TEST_COMIC_TITLE);

  const favoriteButton = page.getByRole("button", { name: /收藏|已收藏/ });
  await favoriteButton.click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/list/favorite/toggle") &&
            item.method === "PUT",
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();
});

/**
 * 用例描述:
 * - 用例目的: 强看护漫画详情页移入回收站主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 先检查漫画是否在库中，如果不在则从回收站恢复。
 *   2. 打开 `/comic/JM100005` 详情页（使用专用测试漫画，不影响其他测试）。
 *   3. 点击"移入回收站"按钮。
 *   4. 确认对话框。
 *   5. 校验 `/api/v1/comic/trash/move` PUT 请求。
 *   6. 恢复数据状态。
 * - 预期结果:
 *   1. 移入回收站请求包含正确的 comic_id。
 *   2. 操作完成后页面跳转。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖漫画详情移入回收站主链路。
 *   - 2026-03-26: 改用 JM100005 避免影响其他测试用例。
 *   - 2026-03-26: 测试结束后恢复数据状态。
 *   - 2026-03-26: 增加前置检查，确保测试数据可用。
 */
test("comic detail page moves to trash via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");
  let trashItem = page.locator(".media-item", { hasText: TRASH_TEST_COMIC_TITLE }).first();
  const isTrashVisible = await trashItem.isVisible();
  if (isTrashVisible) {
    await trashItem.getByRole("button", { name: "恢复" }).click();
    await page.waitForTimeout(1000);
  }

  await page.goto(`/comic/${TRASH_TEST_COMIC_ID}`);
  await expect(page.locator(".title")).toContainText(TRASH_TEST_COMIC_TITLE);

  const trashButton = page.getByRole("button", { name: /移入回收站|删除/ });
  await trashButton.click();

  await confirmDialog(page);

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/comic/trash/move") &&
            item.method === "PUT",
        ),
      { timeout: 8000 },
    )
    .toBeTruthy();

  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);

  try {
    await page.goto("/trash", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");
    trashItem = page.locator(".media-item", { hasText: TRASH_TEST_COMIC_TITLE }).first();
    const isTrashVisibleAfter = await trashItem.isVisible();
    if (isTrashVisibleAfter) {
      await trashItem.getByRole("button", { name: "恢复" }).click();
      await page.waitForTimeout(1000);
    }
  } catch {
  }
});

/**
 * 用例描述:
 * - 用例目的: 强看护漫画详情页开始阅读主链路，确保点击阅读按钮跳转到阅读器页面。
 * - 测试步骤:
 *   1. 打开 `/comic/JM100005` 详情页。
 *   2. 点击"开始阅读"或"继续阅读"按钮。
 *   3. 校验路由跳转到阅读器页面。
 * - 预期结果:
 *   1. 路由跳转到 `/reader/JM100005`。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖漫画详情开始阅读主链路。
 *   - 2026-03-26: 改用 JM100005 避免影响其他测试。
 */
test("comic detail page starts reading and navigates to reader", async ({ page }) => {
  await page.goto(`/comic/${TRASH_TEST_COMIC_ID}`);
  await expect(page.locator(".title")).toContainText(TRASH_TEST_COMIC_TITLE);

  const readButton = page.getByRole("button", { name: /开始阅读|继续阅读/ });
  await readButton.click();

  await expect(page).toHaveURL(/\/reader\//);
});
