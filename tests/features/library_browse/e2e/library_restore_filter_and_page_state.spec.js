const { test, expect } = require("../../../shared/e2e_helpers");

function buildComic(index, tagIds) {
  const padded = String(index).padStart(2, "0");
  return {
    id: `restore-comic-${padded}`,
    title: `Restore Comic ${padded}`,
    title_jp: "",
    author: `Author ${padded}`,
    desc: `Restore detail ${padded}`,
    cover_path: `/static/mock/restore-${padded}.jpg`,
    total_page: 12,
    current_page: 1,
    score: 8.2,
    tag_ids: tagIds,
    tags: tagIds.map((tagId) => ({
      id: tagId,
      name: tagId === "tag_action" ? "Action" : "Other",
    })),
    list_ids: [],
    create_time: `2026-05-${String((index % 28) + 1).padStart(2, "0")}T08:00:00`,
    last_read_time: `2026-05-${String((index % 28) + 1).padStart(2, "0")}T09:00:00`,
    is_deleted: false,
    source: "local",
  };
}

test("library back restores filter and pagination state", async ({ page }) => {
  const actionComics = Array.from({ length: 25 }, (_, index) => buildComic(index + 1, ["tag_action"]));
  const otherComics = [buildComic(26, ["tag_other"]), buildComic(27, ["tag_other"])];
  const allComics = [...actionComics, ...otherComics];
  const detailMap = new Map(allComics.map((item) => [item.id, item]));
  let uiStatePayload = null;

  await page.route("https://api.github.com/repos/Mmmtttt/ULTIMATE_WEB/releases/latest", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tag_name: "0.0.0",
        html_url: "https://github.com/Mmmtttt/ULTIMATE_WEB/releases",
      }),
    });
  });

  await page.route("**/api/v1/ui-state**", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: 200, data: { state: uiStatePayload } }),
      });
      return;
    }
    if (request.method() === "PUT") {
      const body = JSON.parse(request.postData() || "{}");
      uiStatePayload = body.state || null;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: 200, data: { ok: true } }),
      });
      return;
    }
    if (request.method() === "DELETE") {
      uiStatePayload = null;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: 200, data: { ok: true } }),
      });
      return;
    }
    await route.fallback();
  });

  await page.route("**/api/v1/list/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: [] }),
    });
  });

  await page.route("**/api/v1/tag/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: [
          { id: "tag_action", name: "Action", comic_count: 25 },
          { id: "tag_other", name: "Other", comic_count: 2 },
        ],
      }),
    });
  });

  await page.route("**/api/v1/comic/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: allComics }),
    });
  });

  await page.route("**/api/v1/comic/filter**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: actionComics }),
    });
  });

  await page.route("**/api/v1/comic/detail**", async (route) => {
    const url = new URL(route.request().url());
    const comicId = url.searchParams.get("comic_id");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: detailMap.get(comicId) || null }),
    });
  });

  await page.route("**/api/v1/author/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: [] }),
    });
  });

  await page.goto("/library");
  await expect(page.getByText("Restore Comic 01")).toBeVisible();

  const filterButton = page
    .locator(".toolbar .toolbar-action-btn")
    .filter({ has: page.locator(".van-icon-filter-o") })
    .first();
  await filterButton.click();

  await expect(page.locator(".filter-panel")).toBeVisible();
  await page.locator(".tag-item", { hasText: "Action" }).first().click();
  await page.locator(".filter-panel .van-nav-bar .van-button").first().click();
  await expect(page.locator(".filter-panel")).toBeHidden();

  await expect(page.locator(".active-filters")).toContainText("包含: Action");
  await expect(page.locator(".app-pagination .summary-main")).toHaveText("第 1 / 2 页");

  await page.getByRole("button", { name: "第 2 页" }).click();
  await expect(page.locator(".app-pagination .summary-main")).toHaveText("第 2 / 2 页");
  await expect(page.getByText("Restore Comic 21")).toBeVisible();

  await page.locator(".media-card", { hasText: "Restore Comic 21" }).first().click({ force: true });
  await expect(page.getByText("漫画详情")).toBeVisible();

  await page.goBack();

  await expect(page.locator(".active-filters")).toContainText("包含: Action");
  await expect(page.locator(".app-pagination .summary-main")).toHaveText("第 2 / 2 页");
  await expect(page.getByText("Restore Comic 21")).toBeVisible();
  await expect(page.getByText("Restore Comic 01")).not.toBeVisible();
});
