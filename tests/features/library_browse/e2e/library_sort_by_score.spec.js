const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  getMediaTitles,
} = require("../../../shared/e2e_helpers");

const EXPECTED_SCORE_ORDER = [
  "E2E Comic Gamma",
  "E2E Comic Alpha",
  "E2E Comic Beta",
  "E2E Comic Delta",
  "E2E Comic Epsilon",
];

/**
 * 用例描述:
 * - 用例目的: 强看护漫画库“按评分排序”主链路，确保前端操作会触发正确后端参数，且页面结果顺序与评分降序一致。
 * - 测试步骤:
 *   1. 打开 `/library` 并确认测试数据已渲染。
 *   2. 点击排序按钮，在排序面板选择“评分最高”并确认。
 *   3. 记录并校验 `/api/v1/comic/list?sort_type=score` 请求。
 *   4. 校验页面卡片标题顺序与预期评分降序一致。
 * - 预期结果:
 *   1. 至少出现一次携带 `sort_type=score` 的漫画列表请求。
 *   2. 前端展示的前 5 个漫画标题顺序严格等于种子数据评分降序。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，用于守护排序入口请求参数。
 *   - 2026-03-23: 升级为强看护，新增 UI 结果顺序断言。
 *   - 2026-03-23: 增加结果渲染等待，避免异步刷新导致假阴性。
 */
test("library sort by score keeps UI order consistent with backend sorting", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/library");
  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();

  await page.locator(".toolbar .toolbar-action-btn").first().click();
  const pickerItems = page.locator(".van-picker-column__item");
  await expect(pickerItems.nth(1)).toBeVisible();
  await pickerItems.nth(1).click();
  await page.locator(".van-picker__confirm").first().click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/comic/list") &&
            item.url.includes("sort_type=score"),
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();

  await expect(page.getByText("E2E Comic Gamma")).toBeVisible();
  await expect.poll(() => getMediaTitles(page), { timeout: 5000 }).toEqual(EXPECTED_SCORE_ORDER);
});
