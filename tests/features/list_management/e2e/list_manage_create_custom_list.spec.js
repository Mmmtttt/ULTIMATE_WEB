const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 验证用户可在“我的清单”中创建自定义清单并在 UI 中立即可见。
 * - 测试步骤:
 *   1. 从“我的”进入“我的清单”页面。
 *   2. 点击新建按钮，填写清单名称与描述并提交。
 *   3. 校验后端创建请求与新清单展示。
 * - 预期结果:
 *   1. 前端发出 /api/v1/list/add 请求。
 *   2. 页面显示刚创建的清单名称。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖清单创建主路径。
 */
test("list management creates custom comic list", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);
  const listName = `E2E Comic List ${Date.now()}`;
  const listDesc = "created by e2e gate";

  await page.goto("/mine");
  await page.getByText("我的清单").click();
  await expect(page).toHaveURL(/\/lists$/);

  await page.locator(".nav-right .van-icon").nth(1).click();
  await page.locator(".van-field").filter({ hasText: "清单名称" }).locator("input").fill(listName);
  await page.locator(".van-field").filter({ hasText: "清单描述" }).locator("input").fill(listDesc);
  await page.getByRole("button", { name: "确定" }).click();

  await expect(page.getByText(listName)).toBeVisible();
  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "POST" &&
        item.url.includes("/api/v1/list/add") &&
        item.body.includes(listName),
    ),
  ).toBeTruthy();
});
