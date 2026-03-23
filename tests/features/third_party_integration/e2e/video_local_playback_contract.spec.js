const { test, expect, hasApiCall, startApiRequestRecorder } = require("../../../shared/e2e_helpers");

const VIDEO_ID = "JAVDB900001";

/**
 * 用例描述:
 * - 用例目的: 看护“本地视频详情页点击播放”端到端链路，确保用户点击后会请求后端播放源接口，并将第三方代理地址映射到播放器。
 * - 测试步骤:
 *   1. 进入 `/video/JAVDB900001`，等待详情页渲染。
 *   2. mock `/api/v1/video/JAVDB900001/play-urls` 返回包含 `proxy_url=/proxy2?...` 的播放源。
 *   3. 用户点击封面播放区域 `.video-preview`。
 *   4. 断言播放器区域出现、播放源按钮渲染，并命中 `/api/v1/video/proxy2?...` 请求。
 * - 预期结果:
 *   1. 前端发起 `/api/v1/video/JAVDB900001/play-urls` 请求。
 *   2. 页面切换到播放器态（`.video-player-section` 可见）。
 *   3. 播放链路实际命中后端代理地址（而非裸第三方地址）。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，覆盖本地视频播放链路 E2E 第三方代理契约。
 */
test("local video detail click-to-play triggers play-urls and proxy src mapping", async ({ page }) => {
  const requests = startApiRequestRecorder(page);
  const playUrlHits = [];
  const proxyHits = [];

  await page.addInitScript(() => {
    // Stabilize media behavior in headless browsers.
    // eslint-disable-next-line no-extend-native
    HTMLMediaElement.prototype.play = () => Promise.resolve();
  });

  await page.route(`**/api/v1/video/${VIDEO_ID}/play-urls**`, async (route) => {
    playUrlHits.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "ok",
        data: {
          video_id: VIDEO_ID,
          code: "TEST-900001",
          title: "Seed Video",
          sources: [
            {
              source: "missav",
              name: "MissAV",
              available: true,
              currentResolution: "1080P",
              streams: [
                {
                  resolution: "1080P",
                  proxy_url: "/proxy2?url=https%3A%2F%2Fmedia.example%2Fseed-900001.m3u8",
                  url: "https://media.example/seed-900001.m3u8",
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

  await page.goto(`/video/${VIDEO_ID}`);
  await expect(page.locator(".video-preview")).toBeVisible();

  await page.locator(".video-preview").click();

  await expect(page.locator(".video-player-section")).toBeVisible();
  await expect(page.locator(".source-selector .van-button")).toHaveCount(1);
  await expect(page.locator(".source-selector .van-button").first()).toContainText("MissAV");

  expect(playUrlHits).toHaveLength(1);
  expect(proxyHits.length).toBeGreaterThan(0);
  expect(proxyHits[0]).toContain("/api/v1/video/proxy2?url=");
  expect(proxyHits[0]).toContain(encodeURIComponent("https://media.example/seed-900001.m3u8"));
  expect(
    hasApiCall(
      requests,
      (item) => item.url.includes(`/api/v1/video/${VIDEO_ID}/play-urls`) && item.method === "GET",
    ),
  ).toBeTruthy();
  expect(
    hasApiCall(
      requests,
      (item) => item.url.includes("/api/v1/video/proxy2?url=") && item.method === "GET",
    ),
  ).toBeTruthy();
});
