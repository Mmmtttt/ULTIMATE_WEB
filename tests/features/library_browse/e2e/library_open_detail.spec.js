const path = require("path");
const repoRoot = path.resolve(__dirname, "../../../../");
const { test, expect } = require(
  path.join(repoRoot, "comic_frontend", "node_modules", "@playwright/test"),
);

const COMIC_ID = "JM100001";
const COMIC_TITLE = "E2E Comic Alpha";

test("library browse opens comic detail with expected backend calls", async ({ page }) => {
  const apiRequests = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/api/v1/")) {
      apiRequests.push(url);
    }
  });

  await page.goto("/library");

  const card = page.locator(".media-card", { hasText: COMIC_TITLE }).first();
  await expect(card).toBeVisible();
  await card.click();

  await expect(page).toHaveURL(new RegExp(`/comic/${COMIC_ID}$`));
  await expect(page.locator(".title")).toContainText(COMIC_TITLE);

  expect(apiRequests.some((url) => url.includes("/api/v1/comic/list"))).toBeTruthy();
  expect(
    apiRequests.some(
      (url) => url.includes("/api/v1/comic/detail") && url.includes(`comic_id=${COMIC_ID}`),
    ),
  ).toBeTruthy();
});
