const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const COMIC_TITLE = "E2E Comic Alpha";

async function createListFromManagePage(page, listName) {
  await page.locator(".nav-right .van-icon").nth(1).click();
  await page.locator(".van-field").filter({ hasText: "清单名称" }).locator("input").fill(listName);
  await page.locator(".van-field").filter({ hasText: "清单描述" }).locator("input").fill("bind scenario");
  await page.getByRole("button", { name: "确定" }).click();
  await expect(page.getByText(listName)).toBeVisible();
}

/**
 * 用例描述:
 * - 用例目的: 验证用户可将漫画从详情页加入自定义清单，并在清单详情中可见。
 * - 测试步骤:
 *   1. 在清单管理页创建自定义清单。
 *   2. 进入漫画详情页，打开“加入清单”弹窗并选择该清单保存。
 *   3. 回到清单详情页确认该漫画已出现。
 * - 预期结果:
 *   1. 前端发出 /api/v1/list/comic/bind 请求。
 *   2. 目标清单详情出现目标漫画。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖漫画与清单绑定主链路。
 */
test("comic detail adds comic into custom list", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);
  const listName = `E2E Bind List ${Date.now()}`;

  await page.goto("/lists");
  await createListFromManagePage(page, listName);

  await page.goto("/comic/JM100001");
  await expect(page.getByText(COMIC_TITLE)).toBeVisible();
  await page.getByRole("button", { name: "加入清单" }).click();

  const targetListCell = page.locator(".van-cell", { hasText: listName }).first();
  await expect(targetListCell).toBeVisible();
  await targetListCell.click();
  await page.locator(".list-action").getByRole("button", { name: "保存" }).click();

  await page.goto("/lists");
  await page.locator(".van-cell", { hasText: listName }).first().click();
  await expect(page.getByText(COMIC_TITLE)).toBeVisible();

  expect(hasApiCall(apiRequests, "/api/v1/list/comic/bind")).toBeTruthy();
});
