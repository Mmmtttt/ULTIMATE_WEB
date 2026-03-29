const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

async function setInitialMode(page, mode = "comic") {
  await page.addInitScript((targetMode) => {
    window.localStorage.setItem("app_mode", targetMode);
  }, mode);
}

async function openRandomFeed(page) {
  await page.goto("/random-feed");
  await expect(page.getByTestId("random-feed-scroller")).toBeVisible();
  await expect(page.getByTestId("random-feed-card").first()).toBeVisible();
}

/**
 * 用例描述:
 * - 用例目的: 看护随机流页面核心契约，覆盖无限加载、刷新序列、图片不可直接跳详情、按钮可跳详情。
 * - 测试步骤:
 *   1. 打开 /random-feed，等待首屏卡片渲染。
 *   2. 点击当前图片，确认仍停留在随机流页面。
 *   3. 点击“查看详情”按钮，确认成功跳转到详情页，再返回。
 *   4. 点击“刷新序列”，确认触发后端 refresh 接口。
 *   5. 滚动到底触发加载更多，确认卡片数量增长。
 * - 预期结果:
 *   1. 图片点击不触发路由跳转。
 *   2. 详情跳转只能由按钮触发，且链路可达。
 *   3. 刷新操作命中 /api/v1/feed/session/refresh。
 *   4. 列表可持续增长，满足无限浏览。
 * - 历史变更:
 *   - 2026-03-29: 初始创建，覆盖随机流主交互契约。
 */
test("random feed supports refresh, infinite loading, and button-only detail navigation", async ({
  page,
}) => {
  await setInitialMode(page, "comic");
  const apiRequests = startApiRequestRecorder(page);

  await openRandomFeed(page);
  await expect(page.getByText("漫画随机流")).not.toBeVisible();

  const currentPath = new URL(page.url()).pathname;
  await page.locator(".feed-image").first().click();
  await expect.poll(() => new URL(page.url()).pathname).toBe(currentPath);
  await expect(page.getByText("漫画随机流")).toBeVisible();

  await expect(page.getByTestId("random-feed-detail")).toBeVisible();
  await page.getByTestId("random-feed-detail").click();
  await expect.poll(() => new URL(page.url()).pathname).not.toBe("/random-feed");
  await page.goBack();
  await openRandomFeed(page);

  await page.locator(".feed-image").first().click();
  await expect(page.getByTestId("random-feed-card-detail").first()).toBeVisible();
  await page.getByTestId("random-feed-card-detail").first().click();
  await expect.poll(() => new URL(page.url()).pathname).not.toBe("/random-feed");
  await page.goBack();
  await openRandomFeed(page);

  await page.locator(".feed-image").first().click();
  await expect(page.getByTestId("random-feed-refresh")).toBeVisible();
  await page.getByTestId("random-feed-refresh").click();
  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "POST" &&
        item.url.includes("/api/v1/feed/session/refresh"),
    ),
  ).toBeTruthy();

  const beforeCount = await page.getByTestId("random-feed-card").count();
  const scroller = page.getByTestId("random-feed-scroller");
  await scroller.evaluate((node) => {
    node.scrollTop = node.scrollHeight;
  });
  await expect
    .poll(async () => await page.getByTestId("random-feed-card").count())
    .toBeGreaterThan(beforeCount);
});

/**
 * 用例描述:
 * - 用例目的: 看护随机流在漫画/视频模式切换时的页面状态与详情跳转链路。
 * - 测试步骤:
 *   1. 进入随机流页面。
 *   2. 点击模式开关切换到视频模式。
 *   3. 校验页面状态文本更新为“视频模式”。
 *   4. 点击卡片“查看详情”按钮，校验跳转到视频详情链路。
 * - 预期结果:
 *   1. 模式切换后随机流仍可用且有内容。
 *   2. 详情按钮在视频模式下可跳转到 /video/* 或 /video-recommendation/*。
 * - 历史变更:
 *   - 2026-03-29: 初始创建，覆盖跨模式随机流交互。
 */
test("random feed supports video mode and detail jump by button", async ({ page }) => {
  await setInitialMode(page, "comic");
  await openRandomFeed(page);

  await page.locator(".mode-switch").first().click();
  await expect(page.getByTestId("random-feed-card").first()).toBeVisible();

  await page.locator(".feed-image").first().click();
  await expect(page.getByText("视频模式")).toBeVisible();
  await expect(page.getByTestId("random-feed-card-detail").first()).toBeVisible();
  await page.getByTestId("random-feed-card-detail").first().click();
  await expect
    .poll(() => new URL(page.url()).pathname)
    .toMatch(/^\/video(\/|-.+)/);
});

test("random feed keeps browsing position after entering detail and going back", async ({
  page,
}) => {
  await setInitialMode(page, "comic");
  await openRandomFeed(page);

  const scroller = page.getByTestId("random-feed-scroller");
  const rememberedTop = await scroller.evaluate((node) => {
    node.scrollTop = node.clientHeight * 2;
    return node.scrollTop;
  });

  await expect
    .poll(async () => await scroller.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);

  const box = await scroller.boundingBox();
  if (!box) {
    throw new Error("random feed scroller has no bounding box");
  }
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);

  await expect(page.getByTestId("random-feed-detail")).toBeVisible();
  await page.getByTestId("random-feed-detail").click();
  await expect.poll(() => new URL(page.url()).pathname).not.toBe("/random-feed");

  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/random-feed");
  await expect(scroller).toBeVisible();

  const restoredTop = await scroller.evaluate((node) => node.scrollTop);
  expect(Math.abs(restoredTop - rememberedTop)).toBeLessThan(180);
});
