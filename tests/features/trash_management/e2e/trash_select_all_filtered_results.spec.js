const {
  test,
  expect,
} = require("../../../shared/e2e_helpers");

function ok(data, msg = "成功") {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      code: 200,
      msg,
      data,
    }),
  };
}

test("trash select all covers the full filtered result instead of one page", async ({ page }) => {
  const trashItems = Array.from({ length: 21 }, (_, index) => ({
    id: `TRASH${String(index + 1).padStart(3, "0")}`,
    title: `Trash Comic ${String(index + 1).padStart(2, "0")}`,
    cover_path: `/static/mock/trash-${index + 1}.jpg`,
  }));

  await page.route("**/api/v1/comic/trash/list**", async (route) => {
    await route.fulfill(ok(trashItems));
  });

  await page.route("**/api/v1/recommendation/trash/list**", async (route) => {
    await route.fulfill(ok([]));
  });

  await page.goto("/trash");
  await expect(page.getByText("Trash Comic 01")).toBeVisible();

  await page.getByText("全选").click();
  await expect(page.locator(".selected-info")).toContainText("已选 21 个");
});
