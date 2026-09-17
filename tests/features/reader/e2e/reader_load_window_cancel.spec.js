const { test, expect } = require("../../../shared/e2e_helpers");

const COMIC_ID = "CA100001";
const TOTAL_PAGES = 200;
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

function getPageNumber(url) {
  try {
    return Number(new URL(url).searchParams.get("page_num"));
  } catch (error) {
    return 0;
  }
}

test("reader keeps a bounded load window and stops requests after unmount", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.removeItem("comic_cache");
    window.localStorage.removeItem("comic_config");
  });

  const requestedPages = [];
  let imageListRequests = 0;
  await page.route("**/api/v1/comic/detail**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: {
        code: 200,
        data: {
          id: COMIC_ID,
          title: "Bounded reader fixture",
          current_page: 100,
          total_page: TOTAL_PAGES,
        },
      },
    });
  });
  await page.route("**/api/v1/comic/images**", async (route) => {
    imageListRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: {
        code: 200,
        data: Array.from({ length: TOTAL_PAGES }, () => "placeholder"),
      },
    });
  });
  await page.route(/\/api\/v1\/comic\/image\?/, async (route) => {
    const pageNumber = getPageNumber(route.request().url());
    if (pageNumber > 0) requestedPages.push(pageNumber);
    await new Promise((resolve) => setTimeout(resolve, 80));
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: PNG_1X1,
    });
  });

  await page.goto(`/reader/${COMIC_ID}?page=100`);
  await expect(page.locator(".reader-content")).toBeVisible({ timeout: 10000 });

  await expect
    .poll(() => new Set(requestedPages).size, { timeout: 5000 })
    .toBeGreaterThan(0);
  expect(imageListRequests).toBe(0);
  await page.waitForTimeout(2800);

  const loadedBeforeUnmount = new Set(requestedPages);
  expect(loadedBeforeUnmount.size).toBeGreaterThan(0);
  expect(Array.from(loadedBeforeUnmount).every((pageNumber) => pageNumber >= 80 && pageNumber <= 160)).toBeTruthy();
  expect(await page.locator(".page, .up-down-page").count()).toBeLessThan(TOTAL_PAGES);

  await page.goto("/library");
  const countAfterUnmount = requestedPages.length;
  await page.waitForTimeout(500);
  expect(requestedPages.length).toBe(countAfterUnmount);
});
