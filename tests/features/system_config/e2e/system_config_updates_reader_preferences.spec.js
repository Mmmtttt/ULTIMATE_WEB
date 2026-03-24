const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

test("system config updates reader preferences including single-page mode", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/config");
  await expect(page).toHaveURL(/\/config$/);

  await page.getByText("上下翻页").click();
  await page.getByText("深色背景").click();

  const singlePageSwitch = page
    .locator(".van-cell", { hasText: "单页浏览" })
    .locator(".van-switch");
  await expect(singlePageSwitch).toBeVisible();

  const checkedBefore = (await singlePageSwitch.getAttribute("aria-checked")) === "true";
  if (!checkedBefore) {
    await singlePageSwitch.click();
  }

  await expect
    .poll(async () => (await singlePageSwitch.getAttribute("aria-checked")) === "true")
    .toBeTruthy();

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "PUT" &&
        item.url.includes("/api/v1/config") &&
        item.body.includes('"default_page_mode":"up_down"'),
    ),
  ).toBeTruthy();

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "PUT" &&
        item.url.includes("/api/v1/config") &&
        item.body.includes('"default_background":"dark"'),
    ),
  ).toBeTruthy();

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "PUT" &&
        item.url.includes("/api/v1/config") &&
        item.body.includes('"single_page_browsing":true'),
    ),
  ).toBeTruthy();
});
