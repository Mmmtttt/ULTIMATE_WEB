const { test, expect } = require("../../../shared/e2e_helpers");

function buildComic(id, title) {
  return {
    id,
    title,
    title_jp: "",
    author: "Filter Author",
    desc: `${title} detail`,
    cover_path: `/static/mock/${id}.jpg`,
    total_page: 10,
    current_page: 1,
    score: 8.0,
    tag_ids: [],
    tags: [],
    list_ids: [],
    create_time: "2026-05-17T08:00:00",
    last_read_time: "2026-05-17T09:00:00",
    is_deleted: false,
    source: "local",
  };
}

async function mockGithubRelease(page) {
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
}

test("advanced filter supports searching tags inside the tag selector", async ({ page }) => {
  await mockGithubRelease(page);

  await page.route("**/api/v1/ui-state**", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: 200, data: { state: null } }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: { ok: true } }),
    });
  });

  await page.route("**/api/v1/list/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: [] }),
    });
  });

  await page.route("**/api/v1/author/list**", async (route) => {
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
          { id: "tag_aurora", name: "Aurora", comic_count: 3 },
          { id: "tag_harbor", name: "Harbor", comic_count: 2 },
          { id: "tag_nebula", name: "Nebula", comic_count: 1 },
        ],
      }),
    });
  });

  await page.route("**/api/v1/comic/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: [buildComic("comic-a", "Aurora Comic"), buildComic("comic-b", "Harbor Comic")],
      }),
    });
  });

  await page.goto("/library");
  const filterButton = page
    .locator(".toolbar .toolbar-action-btn")
    .filter({ has: page.locator(".van-icon-filter-o") })
    .first();
  await filterButton.click();

  const tagSearchInput = page.locator('.filter-panel .search-input[placeholder="搜索标签..."]').first();
  await expect(tagSearchInput).toBeVisible();
  await tagSearchInput.fill("Har");

  await expect(page.locator(".filter-panel .tag-item", { hasText: "Harbor" })).toHaveCount(1);
  await expect(page.locator(".filter-panel .tag-item", { hasText: "Aurora" })).toHaveCount(0);
  await expect(page.locator(".filter-panel .tag-item", { hasText: "Nebula" })).toHaveCount(0);
});

test("tag management supports searching tags in list and batch sections", async ({ page }) => {
  await mockGithubRelease(page);

  await page.route("**/api/v1/tag/list**", async (route) => {
    const url = new URL(route.request().url());
    const contentType = url.searchParams.get("content_type") || "comic";
    const data = contentType === "video"
      ? [
          { id: "video_tag_aurora", name: "Video Aurora", video_count: 2 },
          { id: "video_tag_harbor", name: "Video Harbor", video_count: 1 },
        ]
      : [
          { id: "tag_aurora", name: "Aurora", comic_count: 3 },
          { id: "tag_harbor", name: "Harbor", comic_count: 2 },
          { id: "tag_nebula", name: "Nebula", comic_count: 1 },
        ];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data }),
    });
  });

  await page.route("**/api/v1/tag/all-comics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: {
          home_comics: [buildComic("comic-a", "Aurora Comic"), buildComic("comic-b", "Harbor Comic")],
          recommendation_comics: [],
        },
      }),
    });
  });

  await page.goto("/tags");
  await expect(page.getByText("标签管理")).toBeVisible();

  const listSearchInput = page.locator('.tag-list .tag-search-bar input').first();
  await expect(listSearchInput).toBeVisible();
  await listSearchInput.fill("Neb");

  await expect(page.locator(".tag-list .van-cell", { hasText: "Nebula" })).toHaveCount(1);
  await expect(page.locator(".tag-list .van-cell", { hasText: "Aurora" })).toHaveCount(0);

  await page.getByText("批量操作").click();

  const batchSearchInput = page.locator('.batch-section .tag-search-bar input').first();
  await expect(batchSearchInput).toBeVisible();
  await batchSearchInput.fill("Har");

  await expect(page.locator(".batch-section .tag-select-item", { hasText: "Harbor" })).toHaveCount(1);
  await expect(page.locator(".batch-section .tag-select-item", { hasText: "Aurora" })).toHaveCount(0);
});
