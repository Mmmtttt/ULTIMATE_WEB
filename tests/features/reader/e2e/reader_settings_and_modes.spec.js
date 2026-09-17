const { test, expect } = require("../../../shared/e2e_helpers");

const COMIC_ID = "CA100002";
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

test("reader settings control double-page mode, animation, filter and tap preferences", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("comic_config", JSON.stringify({
      defaultPageMode: "left_right",
      defaultBackground: "white",
      autoHideToolbar: true,
      showPageNumber: true,
      autoDownloadPreviewImportAssets: true,
    }));
  });

  await page.route("**/api/v1/comic/detail**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: { code: 200, data: { id: COMIC_ID, title: "Reader settings fixture", current_page: 1 } },
    });
  });
  await page.route("**/api/v1/comic/images**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: { code: 200, data: ["one", "two", "three", "four"] },
    });
  });
  await page.route(/\/api\/v1\/comic\/image\?/, async (route) => {
    await route.fulfill({ status: 200, contentType: "image/png", body: PNG_1X1 });
  });

  await page.goto(`/reader/${COMIC_ID}?page=1`);
  await expect(page.locator(".reader-content")).toBeVisible();
  await expect(page.locator(".comic-image").first()).toBeVisible();
  await page.keyboard.press("m");
  await expect(page.locator(".control-bar")).toBeVisible();
  await page.getByTestId("reader-settings-button").click();
  await expect(page.getByText("阅读设置")).toBeVisible();

  await page.getByTestId("reader-double-page").click();
  await page.getByTestId("reader-no-animation").click();
  const filterSlider = page.getByTestId("reader-filter");
  await filterSlider.scrollIntoViewIfNeeded();
  await filterSlider.click({ position: { x: 30, y: 4 } });
  await page.getByText("右侧下一页", { exact: true }).click();

  const config = await page.evaluate(() => JSON.parse(window.localStorage.getItem("comic_config") || "{}"));
  expect(config.doublePageMode).toBe(true);
  expect(config.noReaderAnimation).toBe(true);
  expect(config.readFilterOpacity).toBeGreaterThan(0);
  expect(config.tapPageTurnMode).toBe("right");
  await expect(page.locator(".double-page-mode")).toBeVisible();
});
