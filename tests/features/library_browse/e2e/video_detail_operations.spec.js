const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const PRIMARY_VIDEO_ID = "JAVDB900001";
const VIDEO_TITLE = "Seed Video";

async function restoreVideoIfInTrash(page) {
  let lastError = null;
  for (let i = 0; i < 3; i++) {
    try {
      await page.goto("/trash", { waitUntil: "domcontentloaded" });
      lastError = null;
      break;
    } catch (error) {
      lastError = error;
      await page.waitForTimeout(300);
    }
  }
  if (lastError) {
    throw lastError;
  }
  await page.waitForLoadState("networkidle");
  const trashItem = page.locator(".media-item", { hasText: VIDEO_TITLE }).first();
  if (await trashItem.isVisible().catch(() => false)) {
    await trashItem.getByRole("button", { name: "恢复" }).click();
    await page.waitForTimeout(500);
  }
}

test("video detail page updates score via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  const rateComponent = page.getByRole("radio").nth(9);
  await rateComponent.click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) => item.url.includes("/api/v1/video/score") && item.method === "PUT",
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();
});

test("video detail page toggles favorite via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  const favoriteButton = page.getByRole("button", { name: /收藏|已收藏/ });
  await favoriteButton.click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) => item.url.includes("/api/v1/list/video/favorite/toggle") && item.method === "PUT",
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();
});

test("video detail page moves to trash via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await restoreVideoIfInTrash(page);

  try {
    await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
    await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

    const trashButton = page.getByRole("button", { name: /移入回收站|删除/ });
    await trashButton.click();

    await page.waitForTimeout(300);

    const confirmButton = page.locator(".van-dialog__confirm");
    if (await confirmButton.isVisible().catch(() => false)) {
      await confirmButton.click();
    }

    await expect
      .poll(
        () =>
          hasApiCall(
            apiRequests,
            (item) => item.url.includes("/api/v1/video/trash/move") && item.method === "PUT",
          ),
        { timeout: 8000 },
      )
      .toBeTruthy();
  } finally {
    try {
      await restoreVideoIfInTrash(page);
    } catch {
      // cleanup should not turn a validated main assertion into a false negative
    }
  }
});

test("video detail page tag click navigates to library with filter", async ({ page }) => {
  await page.goto(`/video/${PRIMARY_VIDEO_ID}`);
  await expect(page.locator(".video-title, .detail-title").first()).toContainText(VIDEO_TITLE);

  const tagItem = page.locator(".tag-item").first();
  if (await tagItem.isVisible().catch(() => false)) {
    await tagItem.click();
    await expect(page).toHaveURL(/\/library/);
  }
});
