const { test, expect, hasApiCall, startApiRequestRecorder } = require("../../../shared/e2e_helpers");

const RECOMMENDATION_ID = "JAVDBREC9001";

/**
 * 用例描述:
 * - 用例目的: 看护“推荐视频详情页点击播放”端到端链路，确保前端调用推荐播放源接口，并将第三方 `proxy_url` 映射为后端代理地址。
 * - 测试步骤:
 *   1. 进入 `/video-recommendation/JAVDBREC9001`。
 *   2. mock 推荐详情接口，返回含 code 的推荐视频数据。
 *   3. mock 推荐播放源接口，返回 `proxy_url=/proxy2?...`。
 *   4. 用户点击 `.video-preview` 触发播放。
 *   5. 断言请求链路、播放器渲染与 `/api/v1/video/proxy2` 命中。
 * - 预期结果:
 *   1. 前端发起 `/api/v1/video/recommendation/JAVDBREC9001/play-urls`。
 *   2. 页面展示播放器与播放源按钮。
 *   3. 播放链路实际命中 `/api/v1/video/proxy2?...` 代理地址。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，覆盖推荐视频播放链路 E2E 第三方代理契约。
 */
test("recommendation video detail click-to-play triggers recommendation play-urls contract", async ({ page }) => {
  const requests = startApiRequestRecorder(page);
  const detailHits = [];
  const playUrlHits = [];
  const proxyHits = [];

  await page.addInitScript(() => {
    // Stabilize media behavior in headless browsers.
    // eslint-disable-next-line no-extend-native
    HTMLMediaElement.prototype.play = () => Promise.resolve();
  });

  await page.route("**/api/v1/video/recommendation/detail**", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("video_id") !== RECOMMENDATION_ID) {
      await route.continue();
      return;
    }

    detailHits.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          id: RECOMMENDATION_ID,
          title: "Recommendation Seed Video",
          code: "REC-9001",
          date: "2026-01-01",
          actors: ["Actor Rec"],
          score: 9.1,
          list_ids: [],
          tag_ids: [],
          tags: [],
          source: "preview",
          is_deleted: false,
          cover_path: "/static/cover/JAVDB/900001.png",
          thumbnail_images: [],
        },
      }),
    });
  });

  await page.route(`**/api/v1/video/recommendation/${RECOMMENDATION_ID}/play-urls**`, async (route) => {
    playUrlHits.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          video_id: RECOMMENDATION_ID,
          code: "REC-9001",
          title: "Recommendation Seed Video",
          sources: [
            {
              source: "missav",
              name: "MissAV",
              available: true,
              currentResolution: "720P",
              streams: [
                {
                  resolution: "720P",
                  proxy_url: "/proxy2?url=https%3A%2F%2Fmedia.example%2Frec-9001.m3u8",
                  url: "https://media.example/rec-9001.m3u8",
                },
              ],
            },
          ],
        },
      }),
    });
  });

  await page.route("**/api/v1/video/proxy2**", async (route) => {
    proxyHits.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/vnd.apple.mpegurl",
      body: "#EXTM3U\n#EXT-X-VERSION:3\n",
    });
  });

  await page.goto(`/video-recommendation/${RECOMMENDATION_ID}`);
  await expect(page.locator(".video-preview")).toBeVisible();

  await page.locator(".video-preview").click();

  await expect(page.locator(".video-player-section")).toBeVisible();
  await expect(page.locator(".source-selector .van-button")).toHaveCount(1);
  await expect(page.locator(".source-selector .van-button").first()).toContainText("MissAV");

  expect(detailHits).toHaveLength(1);
  expect(playUrlHits).toHaveLength(1);
  expect(proxyHits.length).toBeGreaterThan(0);
  expect(proxyHits[0]).toContain("/api/v1/video/proxy2?url=");
  expect(proxyHits[0]).toContain(encodeURIComponent("https://media.example/rec-9001.m3u8"));
  expect(
    hasApiCall(
      requests,
      (item) =>
        item.url.includes(`/api/v1/video/recommendation/${RECOMMENDATION_ID}/play-urls`) &&
        item.method === "GET",
    ),
  ).toBeTruthy();
  expect(
    hasApiCall(
      requests,
      (item) => item.url.includes("/api/v1/video/proxy2?url=") && item.method === "GET",
    ),
  ).toBeTruthy();
});
