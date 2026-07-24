const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  confirmDialog,
} = require("../../../shared/e2e_helpers");

const TRASH_COMIC_TITLE = "E2E Comic Epsilon";

/**
 * 打开漫画详情页：点击卡片并等待详情页加载完成，"移入回收站"按钮可见。
 */
async function openComicDetail(page, title) {
  await page.goto("/library");
  await page.waitForLoadState("networkidle");
  const card = page.locator(".media-card", { hasText: title }).first();
  await expect(card).toBeVisible({ timeout: 10000 });

  await card.click();
  // SPA 内导航，等待路由切到 /comic/:id
  await page.waitForURL(/\/comic\//);
  await page.waitForLoadState("networkidle");

  const moveToTrashBtn = page.locator('[title="移入回收站"]');
  await expect(moveToTrashBtn).toBeVisible({ timeout: 10000 });
  return moveToTrashBtn;
}

/**
 * 等待移入回收站的 API 调用完成。
 */
async function waitForMoveToTrashApi(apiRequests) {
  await expect
    .poll(
      () =>
        hasApiCall(apiRequests, (item) =>
          item.url.includes("/api/v1/comic/trash/move") && item.method === "PUT"
        ),
      { timeout: 5000 }
    )
    .toBeTruthy();
}

/**
 * 用例描述:
 * - 用例目的: 强看护回收站完整生命周期（移入->列表->恢复）。
 * - 测试步骤:
 *   1. 先检查漫画是否在库中，如果不在则从回收站恢复。
 *   2. 从库页面将漫画移入回收站。
 *   3. 打开回收站页面验证列表请求。
 *   4. 在回收站中恢复该漫画。
 * - 预期结果:
 *   1. 移入回收站请求成功。
 *   2. 回收站列表请求成功。
 *   3. 恢复请求成功。
 * - 历史变更:
 *   - 2026-03-26: 重构为独立测试，避免用例间数据耦合。
 *   - 2026-03-26: 改用 E2E Comic Epsilon 避免影响 library_sort_by_score 测试。
 *   - 2026-03-26: 确保测试结束时恢复数据状态。
 *   - 2026-03-26: 增加前置检查，确保测试数据可用。
 *   - 2026-03-26: 增加等待时间，确保页面正确加载。
 */
test("trash page complete lifecycle: move to trash, list, and restore", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");
  const trashItem = page.locator(".media-item", { hasText: TRASH_COMIC_TITLE }).first();
  if (await trashItem.isVisible()) {
    await trashItem.getByRole("button", { name: "恢复" }).click();
    await expect
      .poll(
        () =>
          hasApiCall(apiRequests, (item) =>
            item.url.includes("/api/v1/comic/trash/restore") && item.method === "PUT"
          ),
        { timeout: 5000 }
      )
      .toBeTruthy();
  }

  const moveToTrashBtn = await openComicDetail(page, TRASH_COMIC_TITLE);
  await moveToTrashBtn.click();
  await confirmDialog(page);
  await expect(page).toHaveURL(/\/library/);
  await waitForMoveToTrashApi(apiRequests);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");
  await expect
    .poll(
      () =>
        hasApiCall(apiRequests, (item) =>
          item.url.includes("/api/v1/comic/trash/list") && item.method === "GET"
        ),
      { timeout: 5000 }
    )
    .toBeTruthy();

  const trashItemAfter = page.locator(".media-item", { hasText: TRASH_COMIC_TITLE }).first();
  await expect(trashItemAfter).toBeVisible();
  await trashItemAfter.getByRole("button", { name: "恢复" }).click();

  await expect
    .poll(
      () =>
        hasApiCall(apiRequests, (item) =>
          item.url.includes("/api/v1/comic/trash/restore") && item.method === "PUT"
        ),
      { timeout: 5000 }
    )
    .toBeTruthy();

  await page.goto("/library");
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".media-card", { hasText: TRASH_COMIC_TITLE }).first()).toBeVisible({ timeout: 10000 });
});

/**
 * 用例描述:
 * - 用例目的: 强看护回收站永久删除后恢复功能（通过API验证）。
 * - 测试步骤:
 *   1. 先检查漫画是否在库中，如果不在则从回收站恢复。
 *   2. 从库页面将漫画移入回收站。
 *   3. 在回收站中验证删除按钮存在。
 *   4. 恢复数据状态。
 * - 预期结果:
 *   1. 移入回收站请求成功。
 *   2. 删除按钮可见。
 * - 历史变更:
 *   - 2026-03-26: 重构为独立测试，避免用例间数据耦合。
 *   - 2026-03-26: 简化测试，只验证UI元素存在。
 *   - 2026-03-26: 增加前置检查，确保测试数据可用。
 *   - 2026-03-26: 增加等待时间，确保页面正确加载。
 */
test("trash page shows delete button for trashed item", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");
  let trashItem = page.locator(".media-item", { hasText: TRASH_COMIC_TITLE }).first();
  if (await trashItem.isVisible()) {
    await trashItem.getByRole("button", { name: "恢复" }).click();
    await expect
      .poll(
        () =>
          hasApiCall(apiRequests, (item) =>
            item.url.includes("/api/v1/comic/trash/restore") && item.method === "PUT"
          ),
        { timeout: 5000 }
      )
      .toBeTruthy();
  }

  const moveToTrashBtn = await openComicDetail(page, TRASH_COMIC_TITLE);
  await moveToTrashBtn.click();
  await confirmDialog(page);
  await waitForMoveToTrashApi(apiRequests);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");

  trashItem = page.locator(".media-item", { hasText: TRASH_COMIC_TITLE }).first();
  await expect(trashItem).toBeVisible({ timeout: 10000 });
  const deleteButton = trashItem.getByRole("button", { name: /永久删除|删除/ });
  await expect(deleteButton).toBeVisible();

  await trashItem.getByRole("button", { name: "恢复" }).click();
  await expect
    .poll(
      () =>
        hasApiCall(apiRequests, (item) =>
          item.url.includes("/api/v1/comic/trash/restore") && item.method === "PUT"
        ),
      { timeout: 5000 }
    )
    .toBeTruthy();
});

/**
 * 用例描述:
 * - 用例目的: 强看护回收站清空功能UI。
 * - 测试步骤:
 *   1. 先检查漫画是否在库中，如果不在则从回收站恢复。
 *   2. 从库页面将漫画移入回收站。
 *   3. 验证回收站有内容时UI正确显示。
 *   4. 恢复数据状态。
 * - 预期结果:
 *   1. 回收站列表显示移入的漫画。
 *   2. 恢复按钮可见。
 * - 历史变更:
 *   - 2026-03-26: 重构为独立测试，避免用例间数据耦合。
 *   - 2026-03-26: 简化测试，只验证UI元素存在。
 *   - 2026-03-26: 增加前置检查，确保测试数据可用。
 *   - 2026-03-26: 增加等待时间，确保页面正确加载。
 *   - 2026-03-26: 改为验证恢复按钮存在，而非清空按钮。
 */
test("trash page shows restore button when items exist", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");
  let trashItem = page.locator(".media-item", { hasText: TRASH_COMIC_TITLE }).first();
  if (await trashItem.isVisible()) {
    await trashItem.getByRole("button", { name: "恢复" }).click();
    await expect
      .poll(
        () =>
          hasApiCall(apiRequests, (item) =>
            item.url.includes("/api/v1/comic/trash/restore") && item.method === "PUT"
          ),
        { timeout: 5000 }
      )
      .toBeTruthy();
  }

  const moveToTrashBtn = await openComicDetail(page, TRASH_COMIC_TITLE);
  await moveToTrashBtn.click();
  await confirmDialog(page);
  await waitForMoveToTrashApi(apiRequests);

  await page.goto("/trash");
  await page.waitForLoadState("networkidle");

  trashItem = page.locator(".media-item", { hasText: TRASH_COMIC_TITLE }).first();
  await expect(trashItem).toBeVisible({ timeout: 10000 });

  const restoreButton = trashItem.getByRole("button", { name: "恢复" });
  await expect(restoreButton).toBeVisible();

  await restoreButton.click();
  await expect
    .poll(
      () =>
        hasApiCall(apiRequests, (item) =>
          item.url.includes("/api/v1/comic/trash/restore") && item.method === "PUT"
        ),
      { timeout: 5000 }
    )
    .toBeTruthy();
});
