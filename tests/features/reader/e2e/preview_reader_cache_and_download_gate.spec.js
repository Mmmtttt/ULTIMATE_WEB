const path = require("node:path");
const fs = require("node:fs/promises");

const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const BACKEND_BASE_URL = process.env.E2E_BACKEND_BASE_URL || "http://127.0.0.1:5010";
const CACHED_RECOMMENDATION_ID = "JM910001";
const UNCACHED_RECOMMENDATION_ID = "JM910002";
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgN6QHdwAAAAASUVORK5CYII=",
  "base64",
);

async function apiJson(response) {
  const payload = await response.json();
  return payload;
}

async function getRuntimeDataDir(request) {
  const response = await request.get(`${BACKEND_BASE_URL}/api/v1/config/system`);
  expect(response.ok()).toBeTruthy();
  const payload = await apiJson(response);
  expect(payload.code).toBe(200);
  expect(payload.data.current_runtime_data_dir).toBeTruthy();
  return payload.data.current_runtime_data_dir;
}

async function deleteRecommendationIfExists(request, recommendationId) {
  await request.delete(`${BACKEND_BASE_URL}/api/v1/recommendation/delete`, {
    params: { recommendation_id: recommendationId },
  });
}

async function addRecommendation(request, recommendationId, title, totalPage = 3) {
  await deleteRecommendationIfExists(request, recommendationId);
  const response = await request.post(`${BACKEND_BASE_URL}/api/v1/recommendation/add`, {
    data: {
      id: recommendationId,
      title,
      author: "Reader Gate Bot",
      total_page: totalPage,
      current_page: 1,
      score: 8.5,
      cover_path: "/static/cover/JM/100001.png",
      tag_ids: ["tag_action"],
    },
  });
  expect(response.ok()).toBeTruthy();
  const payload = await apiJson(response);
  expect(payload.code).toBe(200);
}

async function seedRecommendationCache(runtimeDataDir, recommendationId, pageCount) {
  const originalId = recommendationId.replace(/^JM/, "");
  const cacheDir = path.join(
    runtimeDataDir,
    "recommendation_cache",
    "comic",
    "JM",
    originalId,
  );
  await fs.mkdir(cacheDir, { recursive: true });
  for (let page = 1; page <= pageCount; page += 1) {
    const file = path.join(cacheDir, `${String(page).padStart(3, "0")}.png`);
    await fs.writeFile(file, PNG_1X1);
  }
}

async function openReaderAndShowMenu(page, url) {
  await page.goto(url);
  await expect(page.locator(".reader-content")).toBeVisible();
  const image = page.locator(".comic-image").first();
  await expect(image).toBeVisible();
  await page.keyboard.press("m");
  await expect(page.locator(".control-bar")).toBeVisible();
}

async function waitPageIndicator(page, expectedText) {
  const indicator = page.locator(".page-indicator");
  await expect(indicator).toBeVisible();
  await expect
    .poll(async () => {
      const raw = (await indicator.textContent()) || "";
      return raw.replace(/\s+/g, "");
    })
    .toContain(expectedText.replace(/\s+/g, ""));
}

/**
 * 用例描述:
 * - 用例目的: 看护“预览阅读页命中本地缓存”分支，确保不会误触发整本下载，并保持进度上报链路。
 * - 测试步骤:
 *   1. 通过后端接口新增一个预览漫画，并在 runtime recommendation_cache 写入 3 页真实图片。
 *   2. 打开 /recommendation-reader/{id}?page=2。
 *   3. 校验页码恢复、缓存图片 URL、模式切换后的锚点页与进度上报。
 *   4. 校验请求链路包含 cache/status，不包含 cache/download。
 * - 预期结果:
 *   1. 阅读页直接可读，页码为 2/3。
 *   2. 图片来源是 /api/v1/recommendation/cache/image。
 *   3. 不触发 /api/v1/recommendation/cache/download。
 *   4. 下一页后触发 /api/v1/recommendation/progress 且 current_page=3。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，建立预览缓存命中路径的端到端看护。
 */
test("preview reader uses cached pages and skips full download call", async ({
  page,
  request,
}) => {
  const runtimeDataDir = await getRuntimeDataDir(request);
  await addRecommendation(request, CACHED_RECOMMENDATION_ID, "Reader Gate Cached", 3);
  await seedRecommendationCache(runtimeDataDir, CACHED_RECOMMENDATION_ID, 3);

  const apiRequests = startApiRequestRecorder(page);
  await openReaderAndShowMenu(
    page,
    `/recommendation-reader/${CACHED_RECOMMENDATION_ID}?page=2`,
  );
  await waitPageIndicator(page, "2/3");

  await expect
    .poll(async () => {
      const src = await page.locator(".comic-image").nth(1).getAttribute("src");
      return src || "";
    })
    .toContain(`/api/v1/recommendation/cache/image?recommendation_id=${CACHED_RECOMMENDATION_ID}&page_num=2`);

  const progressRequestPromise = page.waitForRequest(
    (req) =>
      req.method() === "PUT" &&
      req.url().includes("/api/v1/recommendation/progress") &&
      (req.postData() || "").includes(`"recommendation_id":"${CACHED_RECOMMENDATION_ID}"`) &&
      (req.postData() || "").includes('"current_page":3'),
    { timeout: 8000 },
  );

  await page.keyboard.press("ArrowRight");
  await waitPageIndicator(page, "3/3");
  await progressRequestPromise;

  await page.locator(".mode-btn").click();
  await expect(page.locator(".up-down-mode")).toBeVisible();
  await waitPageIndicator(page, "3/3");

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "GET" &&
        item.url.includes("/api/v1/recommendation/cache/status") &&
        item.url.includes(`recommendation_id=${CACHED_RECOMMENDATION_ID}`),
    ),
  ).toBeTruthy();
  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "POST" &&
        item.url.includes("/api/v1/recommendation/cache/download"),
    ),
  ).toBeFalsy();
});

/**
 * 用例描述:
 * - 用例目的: 看护当前“未缓存 + 第三方关闭”下的失败回退行为，防止阅读页卡死或无提示。
 * - 测试步骤:
 *   1. 新增一个未缓存的预览漫画。
 *   2. 打开 /recommendation-reader/{id}。
 *   3. 校验请求链路触发 cache/status 与 cache/download，并进入错误态。
 * - 预期结果:
 *   1. 发起 /api/v1/recommendation/cache/download 请求。
 *   2. 页面显示 error 容器，不渲染 reader-content。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，锁定现阶段未缓存失败分支表现。
 */
test("preview reader falls back to error state when uncached download is unavailable", async ({
  page,
  request,
}) => {
  await addRecommendation(request, UNCACHED_RECOMMENDATION_ID, "Reader Gate Uncached", 3);
  await deleteRecommendationIfExists(request, CACHED_RECOMMENDATION_ID);

  const apiRequests = startApiRequestRecorder(page);
  await page.goto(`/recommendation-reader/${UNCACHED_RECOMMENDATION_ID}`);

  await expect(page.locator(".error")).toBeVisible();
  await expect(page.locator(".reader-content")).toHaveCount(0);

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "GET" &&
        item.url.includes("/api/v1/recommendation/cache/status") &&
        item.url.includes(`recommendation_id=${UNCACHED_RECOMMENDATION_ID}`),
    ),
  ).toBeTruthy();
  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "POST" &&
        item.url.includes("/api/v1/recommendation/cache/download") &&
        item.body.includes(`"recommendation_id":"${UNCACHED_RECOMMENDATION_ID}"`),
    ),
  ).toBeTruthy();
});
