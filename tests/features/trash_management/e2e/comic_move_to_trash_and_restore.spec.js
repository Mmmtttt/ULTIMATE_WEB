const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  confirmDialog,
} = require("../../../shared/e2e_helpers");

const COMIC_TITLE = "E2E Comic Beta";

/**
 * 用例描述:
 * - 用例目的: 验证漫画从详情页移入回收站后，可在回收站恢复并重新出现在本地库。
 * - 测试步骤:
 *   1. 先检查漫画是否在库中，如果不在则从回收站恢复。
 *   2. 从本地库进入目标漫画详情，执行"移入回收站"并确认。
 *   3. 进入"我的-回收站"，对同一漫画执行恢复。
 *   4. 回到本地库确认漫画重新可见。
 * - 预期结果:
 *   1. 请求链路包含 /api/v1/comic/trash/move 与 /api/v1/comic/trash/restore。
 *   2. 回收站可见目标漫画并可恢复。
 *   3. 恢复后本地库重新显示目标漫画。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖回收站主路径。
 *   - 2026-03-26: 增加前置检查，确保测试数据可用。
 *   - 2026-03-26: 确保测试结束时恢复数据状态。
 *   - 2026-03-26: 增加等待时间，确保页面正确加载。
 */
test("comic can be moved to trash and restored by user flow", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");
  let trashItem = page.locator(".media-item", { hasText: COMIC_TITLE }).first();
  if (await trashItem.isVisible()) {
    await trashItem.getByRole("button", { name: "恢复" }).click();
    await page.waitForTimeout(500);
  }

  await page.goto("/library");
  await page.waitForLoadState("networkidle");
  const card = page.locator(".media-card", { hasText: COMIC_TITLE }).first();
  await expect(card).toBeVisible({ timeout: 10000 });
  await card.click();

  await page.getByRole("button", { name: "移入回收站" }).click();
  await confirmDialog(page);
  await expect(page).toHaveURL(/\/library/);

  await page.waitForTimeout(500);

  await page.goto("/mine");
  await page.waitForLoadState("networkidle");
  await page.getByText("回收站").click();
  await expect(page).toHaveURL(/\/trash$/);

  await page.waitForLoadState("networkidle");
  trashItem = page.locator(".media-item", { hasText: COMIC_TITLE }).first();
  await expect(trashItem).toBeVisible({ timeout: 10000 });
  await trashItem.getByRole("button", { name: "恢复" }).click();

  await page.waitForTimeout(500);

  await page.goto("/library");
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".media-card", { hasText: COMIC_TITLE }).first()).toBeVisible({ timeout: 10000 });

  expect(hasApiCall(apiRequests, "/api/v1/comic/trash/move")).toBeTruthy();
  expect(hasApiCall(apiRequests, "/api/v1/comic/trash/restore")).toBeTruthy();
});
