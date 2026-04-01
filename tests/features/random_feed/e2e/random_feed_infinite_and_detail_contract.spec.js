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

async function tapCurrentFeedImage(page) {
  const scroller = page.getByTestId("random-feed-scroller");
  const box = await scroller.boundingBox();
  if (!box) {
    throw new Error("random feed scroller has no bounding box");
  }
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}

async function ensureFeedControlsVisible(page) {
  const detailButton = page.getByTestId("random-feed-detail");
  if (await detailButton.isVisible()) {
    return;
  }
  await tapCurrentFeedImage(page);
  await expect(detailButton).toBeVisible();
}

test("random feed supports refresh, infinite loading, and button-only detail navigation", async ({
  page,
}) => {
  await setInitialMode(page, "comic");
  const apiRequests = startApiRequestRecorder(page);

  await openRandomFeed(page);
  const heightContract = await page.getByTestId("random-feed-scroller").evaluate((node) => {
    const firstCard = node.querySelector("[data-testid='random-feed-card']");
    const cardHeight = firstCard ? firstCard.getBoundingClientRect().height : 0;
    return {
      scrollerHeight: node.clientHeight,
      cardHeight,
    };
  });
  expect(Math.abs(heightContract.cardHeight - heightContract.scrollerHeight)).toBeLessThanOrEqual(4);
  await expect(page.getByTestId("random-feed-detail")).not.toBeVisible();

  const currentPath = new URL(page.url()).pathname;
  await ensureFeedControlsVisible(page);
  await expect.poll(() => new URL(page.url()).pathname).toBe(currentPath);
  await page.getByTestId("random-feed-detail").click();
  await expect.poll(() => new URL(page.url()).pathname).not.toBe("/random-feed");
  await page.goBack();
  await openRandomFeed(page);

  await ensureFeedControlsVisible(page);
  await expect(page.getByTestId("random-feed-detail")).toBeVisible();
  await page.getByTestId("random-feed-detail").click();
  await expect.poll(() => new URL(page.url()).pathname).not.toBe("/random-feed");
  await page.goBack();
  await openRandomFeed(page);

  await ensureFeedControlsVisible(page);
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

test("random feed supports video mode and detail jump by button", async ({ page }) => {
  await setInitialMode(page, "comic");
  await openRandomFeed(page);

  await page.locator(".mode-switch").first().click();
  await expect(page.getByTestId("random-feed-card").first()).toBeVisible();

  await ensureFeedControlsVisible(page);
  await expect(page.getByTestId("random-feed-detail")).toBeVisible();
  await expect(page.getByTestId("random-feed-card-detail").filter({ visible: true }).first()).toBeVisible();
  await page.getByTestId("random-feed-card-detail").filter({ visible: true }).first().click();
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
  const rememberedState = await scroller.evaluate((node) => {
    const card = node.querySelector("[data-testid='random-feed-card']");
    const cardHeight = card ? card.getBoundingClientRect().height : node.clientHeight || 1;
    node.scrollTop = node.clientHeight * 2;
    const rememberedTop = node.scrollTop;
    return {
      rememberedTop,
      rememberedIndex: Math.round(rememberedTop / Math.max(cardHeight, 1)),
      cardHeight,
    };
  });

  await expect
    .poll(async () => await scroller.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);

  await ensureFeedControlsVisible(page);
  await expect(page.getByTestId("random-feed-detail")).toBeVisible();
  await page.getByTestId("random-feed-detail").click();
  await expect.poll(() => new URL(page.url()).pathname).not.toBe("/random-feed");

  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/random-feed");
  await expect(scroller).toBeVisible();

  await expect
    .poll(async () => await scroller.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);
  const restoredState = await scroller.evaluate((node) => {
    const card = node.querySelector("[data-testid='random-feed-card']");
    const cardHeight = card ? card.getBoundingClientRect().height : node.clientHeight || 1;
    const restoredTop = node.scrollTop;
    return {
      restoredTop,
      restoredIndex: Math.round(restoredTop / Math.max(cardHeight, 1)),
      cardHeight,
    };
  });

  // View-state now restores by active index; toolbar visibility can change card height
  // between leave/back, so absolute pixel scrollTop may differ while logical position
  // remains correct.
  expect(Math.abs(restoredState.restoredIndex - rememberedState.rememberedIndex)).toBeLessThanOrEqual(1);

  const expectedTopByRestoredCardHeight =
    rememberedState.rememberedIndex * Math.max(restoredState.cardHeight, 1);
  const pixelTolerance = Math.max(72, restoredState.cardHeight * 0.35);
  expect(Math.abs(restoredState.restoredTop - expectedTopByRestoredCardHeight)).toBeLessThan(
    pixelTolerance
  );
});
