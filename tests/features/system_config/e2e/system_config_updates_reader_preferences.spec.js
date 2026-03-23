const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 验证系统设置中的阅读偏好变更会触发配置保存请求。
 * - 测试步骤:
 *   1. 从“我的”进入“系统设置”页面。
 *   2. 将默认翻页模式切换为“上下翻页”。
 *   3. 将默认背景切换为“深色背景”。
 *   4. 校验配置写回请求体。
 * - 预期结果:
 *   1. 触发 /api/v1/config PUT 请求。
 *   2. 请求体包含 default_page_mode=up_down 与 default_background=dark。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖系统配置主路径。
 */
test("system config updates page mode and background settings", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/mine");
  await page.getByText("系统设置").click();
  await expect(page).toHaveURL(/\/config$/);

  await page.getByText("上下翻页").click();
  await page.getByText("深色背景").click();

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "PUT" &&
        item.url.includes("/api/v1/config") &&
        item.body.includes('"default_page_mode":"up_down"'),
    ),
  ).toBeTruthy();
  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "PUT" &&
        item.url.includes("/api/v1/config") &&
        item.body.includes('"default_background":"dark"'),
    ),
  ).toBeTruthy();
});
