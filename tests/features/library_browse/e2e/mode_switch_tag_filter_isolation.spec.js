const { test, expect } = require("../../../shared/e2e_helpers");

function buildComic(id, title, tagIds) {
  return {
    id,
    title,
    title_jp: "",
    author: "Comic Author",
    desc: `${title} detail`,
    cover_path: `/static/mock/${id}.jpg`,
    total_page: 12,
    current_page: 1,
    score: 8.2,
    tag_ids: tagIds,
    tags: tagIds.map((tagId) => ({
      id: tagId,
      name: tagId === "tag_action" ? "Action" : "Other",
    })),
    list_ids: [],
    create_time: "2026-05-17T08:00:00",
    last_read_time: "2026-05-17T09:00:00",
    is_deleted: false,
    source: "local",
  };
}

function buildVideo(id, title, tagIds) {
  return {
    id,
    code: id.toUpperCase(),
    title,
    creator: "Video Creator",
    actors: ["Actor A"],
    cover_path: `/static/mock/${id}.jpg`,
    thumbnail_images: [],
    score: 8.8,
    tag_ids: tagIds,
    tags: tagIds.map((tagId) => ({
      id: tagId,
      name: tagId === "tag_video_action" ? "VideoAction" : "VideoOther",
    })),
    list_ids: [],
    total_units: 1,
    current_unit: 1,
    create_time: "2026-05-17T08:00:00",
    last_access_time: "2026-05-17T09:00:00",
    is_deleted: false,
    source: "local",
  };
}

async function installSharedMocks(page, stateByScope) {
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
    const url = new URL(request.url());
    const scope = request.method() === "DELETE"
      ? JSON.parse(request.postData() || "{}").scope
      : request.method() === "PUT"
        ? JSON.parse(request.postData() || "{}").scope
        : url.searchParams.get("scope");

    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: 200, data: { state: stateByScope[scope] || null } }),
      });
      return;
    }
    if (request.method() === "PUT") {
      const body = JSON.parse(request.postData() || "{}");
      stateByScope[scope] = body.state || null;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: 200, data: { ok: true } }),
      });
      return;
    }
    if (request.method() === "DELETE") {
      delete stateByScope[scope];
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
    const data = contentType === "video"
      ? [
          { id: "tag_video_action", name: "VideoAction", video_count: 2 },
          { id: "tag_video_other", name: "VideoOther", video_count: 1 },
        ]
      : [
          { id: "tag_action", name: "Action", comic_count: 2 },
          { id: "tag_other", name: "Other", comic_count: 1 },
        ];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data }),
    });
  });
}

async function assertModeSwitchClearsTagFilters(page, options) {
  const {
    path,
    comicListPattern,
    comicFilterPattern,
    videoListPattern,
    videoFilterPattern,
    comicSearchText,
    videoSearchText,
  } = options;

  const stateByScope = {};
  const comicItems = [
    buildComic("comic-1", "Comic Action A", ["tag_action"]),
    buildComic("comic-2", "Comic Action B", ["tag_action"]),
    buildComic("comic-3", "Comic Other", ["tag_other"]),
  ];
  const filteredComicItems = comicItems.filter((item) => item.tag_ids.includes("tag_action"));
  const videoItems = [
    buildVideo("video-1", "Video Mode One", ["tag_video_action"]),
    buildVideo("video-2", "Video Mode Two", ["tag_video_other"]),
  ];

  await installSharedMocks(page, stateByScope);

  await page.route(comicListPattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: comicItems }),
    });
  });

  await page.route(comicFilterPattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: filteredComicItems }),
    });
  });

  await page.route(videoListPattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: videoItems }),
    });
  });

  await page.route(videoFilterPattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: [] }),
    });
  });

  await page.goto(path);
  await expect(page.locator('.toolbar-search input').first()).toHaveAttribute("placeholder", comicSearchText);
  await expect(page.getByText("Comic Action A")).toBeVisible();

  const filterButton = page
    .locator(".toolbar .toolbar-action-btn")
    .filter({ has: page.locator(".van-icon-filter-o") })
    .first();
  await filterButton.click();
  await expect(page.locator(".filter-panel")).toBeVisible();
  await page.locator(".tag-item", { hasText: "Action" }).first().click();
  await page.locator(".filter-panel .van-nav-bar .van-button").first().click();

  await expect(page.locator(".active-filters")).toContainText("包含: Action");
  await expect(page.getByText("Comic Other")).not.toBeVisible();

  await page.locator(".mode-switch").first().click();
  await expect(page.locator('.toolbar-search input').first()).toHaveAttribute("placeholder", videoSearchText);
  await expect(page.locator(".active-filters")).toHaveCount(0);
  await expect(page.getByText("Video Mode One")).toBeVisible();
}

test("library mode switch does not leak comic tag filters into video mode", async ({ page }) => {
  await assertModeSwitchClearsTagFilters(page, {
    path: "/library",
    comicListPattern: "**/api/v1/comic/list**",
    comicFilterPattern: "**/api/v1/comic/filter**",
    videoListPattern: "**/api/v1/video/list**",
    videoFilterPattern: "**/api/v1/video/filter**",
    comicSearchText: "实时搜索漫画...",
    videoSearchText: "实时搜索视频...",
  });
});

test("preview mode switch does not leak comic tag filters into video mode", async ({ page }) => {
  await assertModeSwitchClearsTagFilters(page, {
    path: "/preview",
    comicListPattern: "**/api/v1/recommendation/list**",
    comicFilterPattern: "**/api/v1/recommendation/filter**",
    videoListPattern: "**/api/v1/video/recommendation/list**",
    videoFilterPattern: "**/api/v1/video/recommendation/filter**",
    comicSearchText: "实时搜索推荐漫画...",
    videoSearchText: "实时搜索推荐视频...",
  });
});
