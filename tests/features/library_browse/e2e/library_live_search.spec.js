const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

function buildComic(id, title, author) {
  return {
    id,
    title,
    title_jp: "",
    author,
    desc: `${title} detail`,
    cover_path: `/static/mock/${id}.jpg`,
    total_page: 12,
    current_page: 1,
    score: 8.2,
    tag_ids: [],
    tags: [],
    list_ids: [],
    create_time: "2026-05-17T08:00:00",
    last_read_time: "2026-05-17T09:00:00",
    is_deleted: false,
    source: "local",
  };
}

function buildRecommendation(id, title, author) {
  return {
    id,
    title,
    title_jp: "",
    author,
    desc: `${title} detail`,
    cover_path: `/static/mock/${id}.jpg`,
    total_page: 8,
    current_page: 1,
    score: 8.0,
    tag_ids: [],
    tags: [],
    list_ids: [],
    create_time: "2026-05-17T08:00:00",
    last_read_time: "2026-05-17T09:00:00",
    is_deleted: false,
    source: "preview",
  };
}

async function installSharedMocks(page) {
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
    const url = new URL(route.request().url());
    const contentType = url.searchParams.get("content_type") || "comic";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: contentType === "video"
          ? []
          : [
              { id: "tag_a", name: "Alpha", comic_count: 2 },
              { id: "tag_b", name: "Beta", comic_count: 1 },
            ],
      }),
    });
  });
}

async function assertRealtimeSearch(page, options) {
  const apiRequests = startApiRequestRecorder(page);
  const { path, listPattern, items, expectedSearchApiPath, placeholder } = options;

  await installSharedMocks(page);
  await page.route(listPattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: items }),
    });
  });

  await page.goto(path);
  const searchInput = page.locator(".toolbar-search input").first();
  await expect(searchInput).toHaveAttribute("placeholder", placeholder);
  await expect(page.locator(".media-card")).toHaveCount(items.length);

  await searchInput.fill("Aurora");
  await expect(page.locator(".media-card", { hasText: "Aurora" })).toHaveCount(1);
  await expect(page.locator(".media-card", { hasText: "Nebula" })).toHaveCount(0);
  await expect(page.locator(".media-card", { hasText: "Harbor" })).toHaveCount(0);
  expect(hasApiCall(apiRequests, expectedSearchApiPath)).toBeFalsy();

  await searchInput.fill("Harbor");
  await expect(page.locator(".media-card", { hasText: "Harbor" })).toHaveCount(1);
  await expect(page.locator(".media-card", { hasText: "Aurora" })).toHaveCount(0);

  await searchInput.clear();
  await expect(page.locator(".media-card")).toHaveCount(items.length);
}

test("library search filters local items immediately without manual submit", async ({ page }) => {
  await assertRealtimeSearch(page, {
    path: "/library",
    listPattern: "**/api/v1/comic/list**",
    expectedSearchApiPath: "/api/v1/comic/search",
    placeholder: "实时搜索漫画...",
    items: [
      buildComic("comic-a", "Aurora Comic", "Author Aurora"),
      buildComic("comic-b", "Nebula Comic", "Author Nebula"),
      buildComic("comic-c", "Harbor Story", "Author Harbor"),
    ],
  });
});

test("preview search filters preview items immediately without manual submit", async ({ page }) => {
  await assertRealtimeSearch(page, {
    path: "/preview",
    listPattern: "**/api/v1/recommendation/list**",
    expectedSearchApiPath: "/api/v1/recommendation/search",
    placeholder: "实时搜索推荐漫画...",
    items: [
      buildRecommendation("rec-a", "Aurora Preview", "Preview Aurora"),
      buildRecommendation("rec-b", "Nebula Preview", "Preview Nebula"),
      buildRecommendation("rec-c", "Harbor Preview", "Preview Harbor"),
    ],
  });
});
