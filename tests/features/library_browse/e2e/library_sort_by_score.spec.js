const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 验证本地库排序操作可由前端触发，并正确携带排序参数请求后端。
 * - 测试步骤:
 *   1. 打开本地库页面。
 *   2. 点击排序按钮，选择“评分最高”并确认。
 *   3. 校验请求参数和列表展示稳定性。
 * - 预期结果:
 *   1. 前端发出 /api/v1/comic/list?sort_type=score 请求。
 *   2. 页面仍可展示核心漫画卡片，不出现空白回退。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖排序门禁。
 */
test("library sort by score sends expected backend query", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/library");
  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();

  await page.locator(".toolbar .toolbar-action-btn").first().click();
  await page.getByText("评分最高").click();
  await page.getByRole("button", { name: /确认|完成/ }).first().click();

  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();
  await expect(page.getByText("E2E Comic Beta")).toBeVisible();

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.url.includes("/api/v1/comic/list") &&
        item.url.includes("sort_type=score"),
    ),
  ).toBeTruthy();
});
