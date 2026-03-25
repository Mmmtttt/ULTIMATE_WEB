const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const COMIC_ID = "JM100001";
const COMIC_TITLE = "E2E Comic Alpha";

/**
 * 用例描述:
 * - 用例目的: 验证用户从本地库进入漫画详情时，前端路由与关键后端请求链路正常。
 * - 测试步骤:
 *   1. 先检查漫画是否在库中，如果不在则从回收站恢复。
 *   2. 打开本地库页面并定位目标漫画卡片。
 *   3. 点击漫画卡片进入详情页。
 *   4. 校验页面 URL、标题与关键 API 请求。
 * - 预期结果:
 *   1. 路由跳转到 /comic/{comic_id}。
 *   2. 详情页展示正确标题。
 *   3. 请求链路包含 /api/v1/comic/list 与 /api/v1/comic/detail。
 * - 历史变更:
 *   - 2026-03-23: 初始创建并纳入门禁主路径。
 *   - 2026-03-23: 升级为统一用例描述模板并复用共享 E2E 工具。
 *   - 2026-03-26: 增加前置检查，确保测试数据可用。
 */
test("library browse opens comic detail with expected backend calls", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/trash");
  const trashItem = page.locator(".media-item", { hasText: COMIC_TITLE }).first();
  if (await trashItem.isVisible()) {
    await trashItem.getByRole("button", { name: "恢复" }).click();
    await page.waitForTimeout(500);
  }

  await page.goto("/library");

  const card = page.locator(".media-card", { hasText: COMIC_TITLE }).first();
  await expect(card).toBeVisible();
  await card.click();

  await expect(page).toHaveURL(new RegExp(`/comic/${COMIC_ID}$`));
  await expect(page.locator(".title")).toContainText(COMIC_TITLE);

  expect(hasApiCall(apiRequests, "/api/v1/comic/list")).toBeTruthy();
  expect(hasApiCall(apiRequests, (item) => item.url.includes("/api/v1/comic/detail") && item.url.includes(`comic_id=${COMIC_ID}`))).toBeTruthy();
});
