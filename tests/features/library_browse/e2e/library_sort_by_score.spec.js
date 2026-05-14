const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 强看护漫画库"按评分排序"主链路，确保前端操作会触发正确后端参数，且页面结果顺序与评分降序一致。
 * - 测试步骤:
 *   1. 打开 `/library` 并确认测试数据已渲染。
 *   2. 点击排序按钮，在排序面板选择"评分最高"并确认。
 *   3. 记录并校验 `/api/v1/comic/list?sort_type=score&sort_order=desc` 请求。
 *   4. 获取页面卡片评分，校验顺序为降序。
 * - 预期结果:
 *   1. 至少出现一次携带 `sort_type=score&sort_order=desc` 的漫画列表请求。
 *   2. 前端展示的漫画评分顺序为降序。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，用于守护排序入口请求参数。
 *   - 2026-03-23: 升级为强看护，新增 UI 结果顺序断言。
 *   - 2026-03-23: 增加结果渲染等待，避免异步刷新导致假阴性。
 *   - 2026-03-26: 改为动态验证评分降序，避免依赖固定评分值。
 */
test("library sort by score keeps UI order consistent with backend sorting", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/library");
  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();

  await page.locator(".toolbar .toolbar-action-btn").first().click();
  const scoreOption = page.locator(".van-picker-column__item", { hasText: "评分最高" });
  await expect(scoreOption.first()).toBeVisible();
  await scoreOption.first().click();
  await page.locator(".van-picker__confirm").first().click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/comic/list") &&
            item.url.includes("sort_type=score") &&
            item.url.includes("sort_order=desc"),
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();

  await expect(page.getByText("E2E Comic Gamma")).toBeVisible();

  const scoreElements = await page.locator(".media-card .score").allTextContents();
  const scores = scoreElements
    .map((text) => parseFloat(text.replace(/[^\d.]/g, "")))
    .filter((s) => !isNaN(s));

  for (let i = 0; i < scores.length - 1; i++) {
    expect(scores[i]).toBeGreaterThanOrEqual(scores[i + 1]);
  }
});
