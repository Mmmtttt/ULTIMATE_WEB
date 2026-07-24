const {
  test,
  expect,
} = require("../../../shared/e2e_helpers");

const VIDEO_ID = "LOCALVTHUMB001";
const VIDEO_TITLE = "本地缩略图测试视频";

function ok(data, msg = "成功") {
  return {
    status: 200,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify({
      code: 200,
      msg,
      data,
    }),
  };
}

test("local video detail supports generating thumbnails and selecting cover from action menu", async ({ page }) => {
  const routeCalls = {
    generate: [],
    selectCover: [],
  };
  const coverRequests = [];
  const tinyPng = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlH0iYAAAAASUVORK5CYII=",
    "base64",
  );
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/media/video/LOCAL/thumb-demo/cover.jpg")) {
      coverRequests.push(url);
    }
  });

  const buildThumbUrls = () =>
    Array.from({ length: 20 }, (_, index) => `/media/video/LOCAL/thumb-demo/thumbs/thumb-${String(index + 1).padStart(4, "0")}.jpg`);

  let currentDetail = {
    id: VIDEO_ID,
    title: VIDEO_TITLE,
    code: "LOCAL-THUMB-001",
    source: "local",
    actors: [],
    tags: [],
    thumbnail_images: [],
    thumbnail_images_local: [],
    cover_path: "",
    cover_path_local: "",
    local_cover_asset_version: "",
    local_cover_thumbnail_index: -1,
    preview_video: "",
    preview_video_local: "",
    local_video_path: "",
    local_source_path: "D:/videos/local-thumb-demo.mp4",
    list_ids: [],
    tag_ids: [],
    score: 8,
    local_thumbnail_capability: {
      supported: true,
      has_local_source: true,
      show_generate_action: true,
      can_generate: true,
      can_select_cover: false,
      generated_count: 0,
      target_count: 20,
      selected_index: -1,
      reason: "",
    },
  };

  await page.route("**/api/v1/video/detail**", async (route) => {
    const url = new URL(route.request().url());
    const requestedId = url.searchParams.get("video_id");
    if (requestedId === VIDEO_ID) {
      await route.fulfill(ok(currentDetail));
      return;
    }
    await route.continue();
  });

  await page.route("**/api/v1/video/local-thumbnails/generate", async (route) => {
    routeCalls.generate.push(route.request().postDataJSON());
    currentDetail = {
      ...currentDetail,
      thumbnail_images_local: buildThumbUrls(),
      cover_path_local: "/media/video/LOCAL/thumb-demo/cover.jpg",
      local_cover_asset_version: "cover-v-1",
      local_cover_thumbnail_index: 10,
      local_thumbnail_capability: {
        ...currentDetail.local_thumbnail_capability,
        show_generate_action: true,
        can_select_cover: true,
        generated_count: 20,
        selected_index: 10,
      },
    };
    await route.fulfill(ok(currentDetail, "缩略图生成成功"));
  });

  await page.route("**/api/v1/video/local-thumbnails/cover", async (route) => {
    const payload = route.request().postDataJSON();
    routeCalls.selectCover.push(payload);
    currentDetail = {
      ...currentDetail,
      local_cover_asset_version: "cover-v-2",
      local_cover_thumbnail_index: payload.thumbnail_index,
      local_thumbnail_capability: {
        ...currentDetail.local_thumbnail_capability,
        selected_index: payload.thumbnail_index,
      },
    };
    await route.fulfill(ok(currentDetail, "封面已更新"));
  });

  await page.route("**/media/video/LOCAL/thumb-demo/cover.jpg**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: tinyPng,
    });
  });

  await page.goto(`/video/${VIDEO_ID}`);
  await expect(page.locator(".video-title").first()).toContainText(VIDEO_TITLE);

  // 使用更精确的选择器，避免匹配到收藏和删除两个 van-icon
  await page.locator(".van-nav-bar__right .van-icon").first().click();
  await expect(page.getByText("生成缩略图")).toBeVisible();
  await page.getByText("生成缩略图").click();

  await expect.poll(() => routeCalls.generate.length).toBe(1);
  await expect.poll(() => coverRequests.some((url) => url.includes("cover-v-1"))).toBe(true);
  await expect(page.getByText("选择视频封面")).toBeVisible();
  await expect(page.locator(".thumbnail-picker-card")).toHaveCount(20);
  await expect(page.locator(".thumbnail-picker-badge", { hasText: "当前封面" })).toHaveCount(1);

  await page.locator(".thumbnail-picker-card").nth(3).click();
  await page.getByRole("button", { name: "设为封面", exact: true }).click();

  await expect.poll(() => routeCalls.selectCover.length).toBe(1);
  await expect(routeCalls.selectCover[0]).toEqual({
    video_id: VIDEO_ID,
    thumbnail_index: 3,
  });
  await expect.poll(() => coverRequests.some((url) => url.includes("cover-v-2"))).toBe(true);

  await expect(page.getByText("选择视频封面")).toBeHidden();

  // 使用更精确的选择器，避免匹配到收藏和删除两个 van-icon
  await page.locator(".van-nav-bar__right .van-icon").first().click();
  await expect(page.getByText("选择封面")).toBeVisible();
});
