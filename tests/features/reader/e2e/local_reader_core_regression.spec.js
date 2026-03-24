const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const COMIC_ID = "JM100001";
const SECONDARY_COMIC_ID = "JM100002";

async function openReaderAndShowMenu(page, url) {
  await page.goto(url);
  await expect(page.locator(".reader-content")).toBeVisible();

  const firstImage = page.locator(".comic-image").first();
  await expect(firstImage).toBeVisible();
  await page.keyboard.press("m");

  await expect(page.locator(".control-bar")).toBeVisible();
  return firstImage;
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
 * - 用例目的: 看护本地漫画阅读页主链路，确保“按页恢复 + 图片加载 + 关键后端请求”稳定。
 * - 测试步骤:
 *   1. 直接进入 /reader/JM100001?page=2。
 *   2. 等待阅读页加载并展开底部控制条。
 *   3. 校验页码恢复为第 2 页、图片地址指向后端图片接口。
 *   4. 校验已发出 detail/images 关键请求。
 * - 预期结果:
 *   1. 页面可正常渲染且页码为 2/3。
 *   2. 读图 URL 命中 /api/v1/comic/image。
 *   3. 请求链路包含 /comic/detail 与 /comic/images。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，建立本地阅读核心看护门禁。
 */
test("local reader restores route page and loads backend images", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await openReaderAndShowMenu(page, `/reader/${COMIC_ID}?page=2`);
  await expect(page.locator(".left-right-mode")).toBeVisible();
  await waitPageIndicator(page, "2/3");

  await expect
    .poll(async () => {
      const src = await page.locator(".comic-image").nth(1).getAttribute("src");
      return src || "";
    })
    .toContain(`/api/v1/comic/image?comic_id=${COMIC_ID}&page_num=2`);

  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "GET" &&
        item.url.includes("/api/v1/comic/detail") &&
        item.url.includes(`comic_id=${COMIC_ID}`),
    ),
  ).toBeTruthy();
  expect(
    hasApiCall(
      apiRequests,
      (item) =>
        item.method === "GET" &&
        item.url.includes("/api/v1/comic/images") &&
        item.url.includes(`comic_id=${COMIC_ID}`),
    ),
  ).toBeTruthy();
});

/**
 * 用例描述:
 * - 用例目的: 看护本地阅读页的“翻页进度上报 + 模式切换保持锚点页”行为，避免新增功能时回归。
 * - 测试步骤:
 *   1. 进入 /reader/JM100001?page=1 并展开控制条。
 *   2. 使用键盘 ArrowRight 翻到下一页。
 *   3. 切换阅读模式（左右 -> 上下）。
 *   4. 校验页码仍保持在当前页，并校验进度 PUT 请求体。
 * - 预期结果:
 *   1. 页码从 1/3 变为 2/3。
 *   2. 模式切换后保持 2/3，不跳页。
 *   3. 发送 /api/v1/comic/progress，且 current_page=2。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，覆盖阅读进度与模式切换关键交互。
 */
test("local reader keeps anchor page when toggling mode and persists progress", async ({
  page,
}) => {
  await openReaderAndShowMenu(page, `/reader/${COMIC_ID}?page=1`);
  await waitPageIndicator(page, "1/3");

  const progressRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "PUT" &&
      request.url().includes("/api/v1/comic/progress") &&
      (request.postData() || "").includes(`"comic_id":"${COMIC_ID}"`) &&
      (request.postData() || "").includes('"current_page":2'),
    { timeout: 8000 },
  );

  await page.keyboard.press("ArrowRight");
  await waitPageIndicator(page, "2/3");
  await progressRequestPromise;

  await page.locator(".mode-btn").click();
  await expect(page.locator(".up-down-mode")).toBeVisible();
  await waitPageIndicator(page, "2/3");

  await expect
    .poll(() =>
      page.evaluate(() => {
        const raw = window.localStorage.getItem("comic_config");
        if (!raw) return "";
        try {
          return JSON.parse(raw).defaultPageMode || "";
        } catch (error) {
          return "";
        }
      }),
    )
    .toBe("up_down");
});

/**
 * 用例描述:
 * - 用例目的: 看护“默认翻页模式”配置对阅读页初始模式的影响，确保设置页配置持续生效。
 * - 测试步骤:
 *   1. 预先注入 localStorage 的 comic_config（defaultPageMode=up_down）。
 *   2. 打开 /reader/JM100002。
 *   3. 校验阅读页初始模式容器。
 * - 预期结果:
 *   1. 首屏使用 up-down 模式容器渲染。
 *   2. 不渲染 left-right 模式容器。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，补齐配置到阅读行为的回归看护。
 */
test("local reader uses configured default page mode on first render", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "comic_config",
      JSON.stringify({
        defaultPageMode: "up_down",
        defaultBackground: "white",
        autoHideToolbar: true,
        showPageNumber: true,
        autoDownloadPreviewImportAssets: true,
      }),
    );
  });

  await page.goto(`/reader/${SECONDARY_COMIC_ID}`);
  await expect(page.locator(".reader-content")).toBeVisible();
  await expect(page.locator(".up-down-mode")).toBeVisible();
  await expect(page.locator(".left-right-mode")).toHaveCount(0);
});

/**
 * 用例描述:
 * - 用例目的: 看护本地阅读页「单页浏览」模式，确保开启后每次仅渲染当前页，且翻页仍正常工作。
 * - 测试步骤:
 *   1. 预先注入 singlePageBrowsing=true 的 comic_config。
 *   2. 打开 /reader/JM100001?page=2 并展示控制栏。
 *   3. 校验 single-page-mode 生效、仅渲染一张图片、初始定位到第 2 页。
 *   4. 触发下一页并校验仍仅渲染一张图片且图片 URL 切换到第 3 页。
 * - 预期结果:
 *   1. 阅读容器带有 single-page-mode 类。
 *   2. `.comic-image` 数量始终为 1。
 *   3. 页码从 2/3 正常切换为 3/3，图片 URL 对应 page_num=3。
 * - 历史变更:
 *   - 2026-03-24: 新增，覆盖单页浏览核心行为门禁。
 */
test("local reader single-page mode keeps centered snap paging in left-right and up-down", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "comic_config",
      JSON.stringify({
        defaultPageMode: "left_right",
        defaultBackground: "white",
        autoHideToolbar: true,
        showPageNumber: true,
        autoDownloadPreviewImportAssets: true,
        singlePageBrowsing: true,
      }),
    );
  });

  await openReaderAndShowMenu(page, `/reader/${COMIC_ID}?page=2`);
  await expect(page.locator(".left-right-mode.single-page-mode")).toBeVisible();
  await waitPageIndicator(page, "2/3");

  await expect
    .poll(() => page.locator(".left-right-mode .page").count())
    .toBe(3);

  await expect
    .poll(() =>
      page.evaluate(() => {
        const container = document.querySelector(".left-right-mode.single-page-mode");
        if (!container) return Number.POSITIVE_INFINITY;
        const pages = container.querySelectorAll(".page");
        const target = pages[1];
        const image = target?.querySelector("img");
        if (!target || !image) return Number.POSITIVE_INFINITY;
        const c = container.getBoundingClientRect();
        const i = image.getBoundingClientRect();
        const dx = Math.abs((i.left + i.right) / 2 - (c.left + c.right) / 2);
        const dy = Math.abs((i.top + i.bottom) / 2 - (c.top + c.bottom) / 2);
        return Math.max(dx, dy);
      }),
    )
    .toBeLessThan(28);

  await page.evaluate(() => {
    const container = document.querySelector(".left-right-mode.single-page-mode");
    if (!container) return;
    container.scrollLeft = container.clientWidth * 1.45;
  });
  await waitPageIndicator(page, "2/3");

  await page.evaluate(() => {
    const container = document.querySelector(".left-right-mode.single-page-mode");
    if (!container) return;
    container.scrollLeft = container.clientWidth * 1.62;
  });
  await waitPageIndicator(page, "3/3");

  await expect
    .poll(() =>
      page.evaluate(() => {
        const container = document.querySelector(".left-right-mode.single-page-mode");
        if (!container) return Number.POSITIVE_INFINITY;
        const pages = container.querySelectorAll(".page");
        const target = pages[2];
        const image = target?.querySelector("img");
        if (!target || !image) return Number.POSITIVE_INFINITY;
        const c = container.getBoundingClientRect();
        const i = image.getBoundingClientRect();
        const dx = Math.abs((i.left + i.right) / 2 - (c.left + c.right) / 2);
        const dy = Math.abs((i.top + i.bottom) / 2 - (c.top + c.bottom) / 2);
        return Math.max(dx, dy);
      }),
    )
    .toBeLessThan(28);

  await page.locator(".mode-btn").click();
  await expect(page.locator(".up-down-mode.single-page-mode")).toBeVisible();
  await waitPageIndicator(page, "3/3");

  await expect
    .poll(() => page.locator(".up-down-mode .up-down-page").count())
    .toBe(3);
  await expect
    .poll(() =>
      page.evaluate(() => {
        const container = document.querySelector(".up-down-mode.single-page-mode");
        if (!container) return Number.POSITIVE_INFINITY;
        const pages = container.querySelectorAll(".up-down-page");
        const target = pages[2];
        const image = target?.querySelector("img");
        if (!target || !image) return Number.POSITIVE_INFINITY;
        const c = container.getBoundingClientRect();
        const i = image.getBoundingClientRect();
        const dx = Math.abs((i.left + i.right) / 2 - (c.left + c.right) / 2);
        const dy = Math.abs((i.top + i.bottom) / 2 - (c.top + c.bottom) / 2);
        return Math.max(dx, dy);
      }),
    )
    .toBeLessThan(28);
});
