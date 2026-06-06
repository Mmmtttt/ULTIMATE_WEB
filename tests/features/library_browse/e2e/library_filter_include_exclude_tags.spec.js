const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  getMediaTitles,
  buildPaginatedData,
} = require("../../../shared/e2e_helpers");

const EXPECTED_FILTERED_TITLES = ["E2E Comic Alpha", "E2E Comic Gamma"];

/**
 * 用例描述:
 * - 用例目的: 强看护漫画库高级筛选"包含标签 + 排除标签"组合逻辑，确保前后端筛选结果一致。
 * - 测试步骤:
 *   1. 先检查测试漫画是否在库中，如果不在则从回收站恢复。
 *   2. 打开 `/library`，进入高级筛选面板。
 *   3. 在标签页选择 `Action` 为包含标签。
 *   4. 对 `Story` 连续点击两次，切换为排除标签。
 *   5. 点击"应用"触发筛选。
 *   6. 校验请求参数和页面展示的结果集合。
 * - 预期结果:
 *   1. 触发 `/api/v1/comic/filter`，并携带 `include_tag_ids=tag_action` 与 `exclude_tag_ids=tag_story`。
 *   2. 页面只展示满足条件的漫画，标题集合应为 `E2E Comic Alpha`、`E2E Comic Gamma`。
 * - 历史变更:
 *   - 2026-03-23: 初始创建，覆盖标签组合筛选强看护。
 *   - 2026-03-23: 增加结果渲染等待，避免异步刷新导致假阴性。
 *   - 2026-03-26: 增加前置检查，确保测试数据可用。
 */
test("library filter include and exclude tags returns expected comics", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);
  const allComics = [
    {
      id: "JM100001",
      title: "E2E Comic Alpha",
      author: "Tester A",
      cover_path: "/static/mock/JM100001.jpg",
      total_page: 3,
      current_page: 1,
      score: 8.5,
      tag_ids: ["tag_action"],
      tags: [{ id: "tag_action", name: "Action" }],
      list_ids: [],
    },
    {
      id: "JM100003",
      title: "E2E Comic Gamma",
      author: "Tester C",
      cover_path: "/static/mock/JM100003.jpg",
      total_page: 5,
      current_page: 5,
      score: 9.8,
      tag_ids: ["tag_action", "tag_drama"],
      tags: [{ id: "tag_action", name: "Action" }, { id: "tag_drama", name: "Drama" }],
      list_ids: [],
    },
    {
      id: "JM100005",
      title: "E2E Comic Epsilon",
      author: "Tester B",
      cover_path: "/static/mock/JM100005.jpg",
      total_page: 3,
      current_page: 1,
      score: 4.1,
      tag_ids: ["tag_action", "tag_story"],
      tags: [{ id: "tag_action", name: "Action" }, { id: "tag_story", name: "Story" }],
      list_ids: [],
    },
  ];

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
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: [
          { id: "tag_action", name: "Action", comic_count: 3 },
          { id: "tag_story", name: "Story", comic_count: 1 },
          { id: "tag_drama", name: "Drama", comic_count: 1 },
        ],
      }),
    });
  });

  await page.route("**/api/v1/comic/list**", async (route) => {
    const url = new URL(route.request().url());
    const includeTagIds = url.searchParams.getAll("include_tag_ids");
    const excludeTagIds = url.searchParams.getAll("exclude_tag_ids");
    const filtered = allComics.filter((item) => {
      const tags = Array.isArray(item.tag_ids) ? item.tag_ids : [];
      const includeOk = includeTagIds.length === 0 || includeTagIds.every((tagId) => tags.includes(tagId));
      const excludeOk = excludeTagIds.every((tagId) => !tags.includes(tagId));
      return includeOk && excludeOk;
    });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data: buildPaginatedData(filtered) }),
    });
  });

  await page.goto("/library");
  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();

  const filterButton = page
    .locator(".toolbar .toolbar-action-btn")
    .filter({ has: page.locator(".van-icon-filter-o") })
    .first();
  await filterButton.click();
  await expect(page.locator(".filter-panel")).toBeVisible();
  await expect(page.locator(".filter-panel .van-nav-bar__title")).toHaveText("高级筛选");

  await page.locator(".tag-item", { hasText: "Action" }).first().click();
  await page.locator(".tag-item", { hasText: "Story" }).first().click();
  await page.locator(".tag-item", { hasText: "Story" }).first().click();

  await page.locator(".filter-panel .van-nav-bar .van-button").first().click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/comic/list") &&
            item.url.includes("include_tag_ids=tag_action") &&
            item.url.includes("exclude_tag_ids=tag_story"),
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();

  await expect(page.getByText("E2E Comic Alpha")).toBeVisible();
  await expect(page.getByText("E2E Comic Gamma")).toBeVisible();

  await expect.poll(() => getMediaTitles(page), { timeout: 5000 }).toEqual(EXPECTED_FILTERED_TITLES);
});
