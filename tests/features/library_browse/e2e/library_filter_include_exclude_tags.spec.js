const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  getMediaTitles,
} = require("../../../shared/e2e_helpers");

const EXPECTED_FILTERED_TITLES = ["E2E Comic Alpha", "E2E Comic Gamma"];

/**
 * 用例描述:
 * - 用例目的: 强看护漫画库高级筛选“包含标签 + 排除标签”组合逻辑，确保前后端筛选结果一致。
 * - 测试步骤:
 *   1. 打开 `/library`，进入高级筛选面板。
 *   2. 在标签页选择 `Action` 为包含标签。
 *   3. 对 `Story` 连续点击两次，切换为排除标签。
 *   4. 点击“应用”触发筛选。
 *   5. 校验请求参数和页面展示的结果集合。
 * - 预期结果:
 *   1. 触发 `/api/v1/comic/filter`，并携带 `include_tag_ids=tag_action` 与 `exclude_tag_ids=tag_story`。
 *   2. 页面只展示满足条件的漫画，标题集合应为 `E2E Comic Alpha`、`E2E Comic Gamma`。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖标签组合筛选强看护。
 *   - 2026-03-23: 增加结果渲染等待，避免异步刷新导致假阴性。
 */
test("library filter include and exclude tags returns expected comics", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/library");
  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();

  const filterButton = page
    .locator(".toolbar .toolbar-action-btn")
    .filter({ has: page.locator(".van-icon-filter-o") })
    .first();
  await filterButton.click();
  await expect(page.locator(".filter-panel")).toBeVisible();
  await expect(page.locator(".filter-panel .van-nav-bar__title")).toHaveText("高级筛选");

  await page.locator(".tag-item", { hasText: "Action" }).first().click();
  await page.locator(".tag-item", { hasText: "Story" }).first().click();
  await page.locator(".tag-item", { hasText: "Story" }).first().click();

  await page.locator(".filter-panel .van-nav-bar .van-button").first().click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/comic/filter") &&
            item.url.includes("include_tag_ids=tag_action") &&
            item.url.includes("exclude_tag_ids=tag_story"),
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();

  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();
  await expect(page.getByText("E2E Comic Gamma")).toBeVisible();

  await expect.poll(() => getMediaTitles(page), { timeout: 5000 }).toEqual(EXPECTED_FILTERED_TITLES);
});
