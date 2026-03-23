const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const KEYWORD = "Alpha";
const COMIC_TITLE = "E2E Comic Alpha";
const COMIC_ID = "JM100001";

/**
 * 用例描述:
 * - 用例目的: 验证全局搜索在“本地库”模式下可正确搜索并进入漫画详情。
 * - 测试步骤:
 *   1. 进入搜索页并输入关键字。
 *   2. 执行搜索并等待结果渲染。
 *   3. 点击结果卡片进入详情页。
 * - 预期结果:
 *   1. 请求链路包含 /api/v1/comic/search?keyword=...。
 *   2. 搜索结果出现目标漫画。
 *   3. 路由跳转到 /comic/{comic_id} 且详情标题正确。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖全局搜索本地主路径。
 */
test("global search local comic result opens comic detail", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/search");
  const searchInput = page.locator("input[type='search']").first();
  await expect(searchInput).toBeVisible();
  await searchInput.fill(KEYWORD);
  await searchInput.press("Enter");

  const resultCard = page.locator(".media-card", { hasText: COMIC_TITLE }).first();
  await expect(resultCard).toBeVisible();
  await resultCard.click();

  await expect(page).toHaveURL(new RegExp(`/comic/${COMIC_ID}$`));
  await expect(page.locator(".title")).toContainText(COMIC_TITLE);

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.url.includes("/api/v1/comic/search") &&
        item.url.toLowerCase().includes("keyword=alpha"),
    ),
  ).toBeTruthy();
});
