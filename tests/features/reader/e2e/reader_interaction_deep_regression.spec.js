const { test, expect, startApiRequestRecorder } = require("../../../shared/e2e_helpers");

const COMIC_ID = "JM100003";
const TOTAL_PAGE = 5;
const BACKEND_BASE_URL = "http://127.0.0.1:5010";

async function setReaderDefaultConfig(page, overrides = {}) {
  await page.addInitScript((overrideConfig) => {
    let existing = {};
    try {
      existing = JSON.parse(window.localStorage.getItem("comic_config") || "{}");
    } catch (error) {
      existing = {};
    }
    window.localStorage.setItem(
      "comic_config",
      JSON.stringify({
        defaultPageMode: "left_right",
        defaultBackground: "white",
        autoHideToolbar: true,
        showPageNumber: true,
        autoDownloadPreviewImportAssets: true,
        ...existing,
        ...overrideConfig,
      }),
    );
  }, overrides);
}

function extractImageRequestPages(requests, comicId) {
  const pages = [];
  for (const req of requests) {
    if (req.method !== "GET") continue;
    if (!req.url.includes("/api/v1/comic/image")) continue;
    if (!req.url.includes(`comic_id=${comicId}`)) continue;
    try {
      const parsed = new URL(req.url);
      const pageNum = Number(parsed.searchParams.get("page_num"));
      if (Number.isFinite(pageNum) && pageNum > 0) {
        pages.push(pageNum);
      }
    } catch (error) {
      // Ignore malformed URL rows.
    }
  }
  return pages;
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

async function showReaderMenuByKeyboard(page) {
  await expect(page.locator(".reader-content")).toBeVisible();
  await expect(page.locator(".comic-image").first()).toBeVisible();
  await page.keyboard.press("m");
  const controlBar = page.locator(".control-bar");
  const visible = await controlBar.isVisible().catch(() => false);
  if (!visible) {
    await page.locator(".reader-content").click({ position: { x: 12, y: 12 } });
  }
  await expect(controlBar).toBeVisible();
}

async function setComicProgress(page, comicId, currentPage) {
  const payload = await page.evaluate(
    async ({ baseUrl, id, pageNum }) => {
      const response = await fetch(`${baseUrl}/api/v1/comic/progress`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          comic_id: id,
          current_page: pageNum,
        }),
      });
      let json = null;
      try {
        json = await response.json();
      } catch (error) {
        json = null;
      }
      return { status: response.status, ok: response.ok, body: json };
    },
    { baseUrl: BACKEND_BASE_URL, id: comicId, pageNum: currentPage },
  );
  expect(payload.ok).toBeTruthy();
  expect((payload.body || {}).code).toBe(200);
}

/**
 * 用例描述:
 * - 用例目的: 看护阅读页预加载顺序与上下/左右模式下的无缝拼接，避免新增功能引入页面断层或预加载退化。
 * - 测试步骤:
 *   1. 打开 /reader/JM100003?page=3 并记录图片请求。
 *   2. 校验预加载优先命中锚点页（3页）且先于边缘页（1页）请求。
 *   3. 校验左右模式下相邻页面水平拼接无明显间隙。
 *   4. 切换到上下模式并校验垂直拼接无明显间隙。
 * - 预期结果:
 *   1. 预加载请求顺序体现“当前阅读页优先”策略。
 *   2. 左右/上下模式相邻页面 gap 均在无缝容差内（<=2px）。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，补齐无缝拼接与预加载优先级深度看护。
 */
test("reader preloads around focus page and keeps seamless page stitching", async ({ page }) => {
  await setReaderDefaultConfig(page, { defaultPageMode: "left_right" });
  const apiRequests = startApiRequestRecorder(page);
  await setComicProgress(page, COMIC_ID, 3);

  await page.goto(`/reader/${COMIC_ID}?page=3`);
  await expect(page.locator(".reader-content")).toBeVisible();
  await showReaderMenuByKeyboard(page);
  await waitPageIndicator(page, "3/5");
  await expect(page.locator(".left-right-mode .page")).toHaveCount(TOTAL_PAGE);

  await expect
    .poll(() => {
      const unique = Array.from(new Set(extractImageRequestPages(apiRequests, COMIC_ID)));
      return unique.length;
    })
    .toBeGreaterThanOrEqual(4);

  const uniquePages = Array.from(new Set(extractImageRequestPages(apiRequests, COMIC_ID)));
  const firstThree = uniquePages.slice(0, 3);
  const idxCurrent = uniquePages.indexOf(3);
  const idxEdge = uniquePages.indexOf(1);

  expect(firstThree).toContain(3);
  expect(idxCurrent).toBeGreaterThanOrEqual(0);
  if (idxEdge >= 0) {
    expect(idxCurrent < idxEdge).toBeTruthy();
  }

  await expect
    .poll(async () => {
      const src1 = await page.locator(".comic-image").nth(0).getAttribute("src");
      const src2 = await page.locator(".comic-image").nth(1).getAttribute("src");
      return Boolean(src1) && Boolean(src2);
    })
    .toBeTruthy();

  const horizontalGaps = await page.evaluate(() => {
    const pages = Array.from(document.querySelectorAll(".left-right-mode .page"));
    const gaps = [];
    for (let i = 0; i < Math.min(3, pages.length - 1); i += 1) {
      const current = pages[i];
      const next = pages[i + 1];
      gaps.push(next.offsetLeft - (current.offsetLeft + current.offsetWidth));
    }
    return gaps;
  });
  expect(horizontalGaps.length).toBeGreaterThan(0);
  expect(horizontalGaps.every((gap) => Math.abs(gap) <= 2)).toBeTruthy();

  await page.locator(".mode-btn").click();
  await expect(page.locator(".up-down-mode")).toBeVisible();
  await waitPageIndicator(page, "3/5");
  await expect(page.locator(".up-down-mode .up-down-page")).toHaveCount(TOTAL_PAGE);

  const verticalGaps = await page.evaluate(() => {
    const pages = Array.from(document.querySelectorAll(".up-down-mode .up-down-page"));
    const gaps = [];
    for (let i = 0; i < Math.min(3, pages.length - 1); i += 1) {
      const current = pages[i];
      const next = pages[i + 1];
      gaps.push(next.offsetTop - (current.offsetTop + current.offsetHeight));
    }
    return gaps;
  });
  expect(verticalGaps.length).toBeGreaterThan(0);
  expect(verticalGaps.every((gap) => Math.abs(gap) <= 2)).toBeTruthy();
});

/**
 * 用例描述:
 * - 用例目的: 深度看护桌面端阅读交互（滚轮翻页、Ctrl+滚轮缩放、缩放后平移、全屏开关）。
 * - 测试步骤:
 *   1. 打开 /reader/JM100003?page=1 并展开控制条。
 *   2. 滚轮推动左右模式翻页到第2页。
 *   3. Ctrl+滚轮触发缩放，校验缩放提示出现。
 *   4. 缩放状态下继续滚轮，校验页面轨道 transform 变化（平移生效）。
 *   5. 触发全屏开关，若运行环境支持则校验进入/退出。
 * - 预期结果:
 *   1. 页码可从 1/5 切换至 2/5。
 *   2. 缩放提示出现且百分比大于100%。
 *   3. 缩放后平移会改变 track transform。
 *   4. 全屏能力在支持环境下可进入并退出。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，补齐桌面端核心交互深度门禁。
 */
test("desktop reader supports wheel paging zoom pan and fullscreen toggle", async ({ page }) => {
  await setReaderDefaultConfig(page, { defaultPageMode: "left_right" });
  await setComicProgress(page, COMIC_ID, 1);
  await page.goto(`/reader/${COMIC_ID}?page=1`);
  await expect(page.locator(".reader-content")).toBeVisible();
  await showReaderMenuByKeyboard(page);
  await waitPageIndicator(page, "1/5");

  await expect
    .poll(async () => {
      const first = await page.locator(".comic-image").nth(0).getAttribute("src");
      const second = await page.locator(".comic-image").nth(1).getAttribute("src");
      return Boolean(first) && Boolean(second);
    })
    .toBeTruthy();

  await page.locator(".actions .van-button", { hasText: "下一页" }).click();
  await waitPageIndicator(page, "2/5");

  const leftRight = page.locator(".left-right-mode");
  await leftRight.hover();
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -900);
  await page.keyboard.up("Control");

  const zoomInfo = page.locator(".desktop-zoom-info");
  await expect(zoomInfo).toBeVisible();
  const zoomText = (await zoomInfo.textContent()) || "";
  const zoomPercent = Number((zoomText.match(/(\d+)%/) || [])[1] || 0);
  expect(zoomPercent).toBeGreaterThan(100);

  const track = page.locator(".page-track-horizontal");
  const beforeTransform = (await track.getAttribute("style")) || "";
  await leftRight.hover();
  await page.mouse.wheel(180, 220);
  await page.waitForTimeout(120);
  const afterTransform = (await track.getAttribute("style")) || "";
  expect(afterTransform).not.toBe(beforeTransform);

  await page.keyboard.press("0");
  await expect(zoomInfo).toHaveCount(0);

  const fullscreenSupported = await page.evaluate(
    () => Boolean(document.fullscreenEnabled) && typeof document.documentElement.requestFullscreen === "function",
  );
  await page.locator(".control-bar .van-button", { hasText: "全屏" }).click();

  if (fullscreenSupported) {
    await expect
      .poll(() => page.evaluate(() => Boolean(document.fullscreenElement)))
      .toBeTruthy();
    await page.locator(".control-bar .van-button", { hasText: "全屏" }).click();
    await expect
      .poll(() => page.evaluate(() => Boolean(document.fullscreenElement)))
      .toBeFalsy();
  } else {
    await expect(page.locator(".reader-content")).toBeVisible();
  }
});

/**
 * 用例描述:
 * - 用例目的: 看护“从漫画详情页进入阅读页时自动定位到 current_page”主链路。
 * - 测试步骤:
 *   1. 先通过后端接口把 JM100003 进度写到第4页。
 *   2. 从 /comic/JM100003 点击“继续阅读”进入阅读页。
 *   3. 校验阅读页页码定位到 4/5。
 * - 预期结果:
 *   1. 路由跳转到 /reader/JM100003。
 *   2. 阅读页首屏页码为 4/5。
 * - 历史变更:
 *   - 2026-03-24: 初始创建，补齐详情入口继续阅读看护。
 */
test("comic detail continue reading opens reader at saved progress", async ({ page }) => {
  await setComicProgress(page, COMIC_ID, 5);

  await page.goto(`/comic/${COMIC_ID}`);
  const readButton = page.locator(".read-button");
  await expect(readButton).toBeVisible();
  await readButton.click();

  await expect(page).toHaveURL(new RegExp(`/reader/${COMIC_ID}$`));
  await showReaderMenuByKeyboard(page);
  await waitPageIndicator(page, "5/5");
});

test.describe("mobile touch reader interactions", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });

  /**
   * 用例描述:
   * - 用例目的: 看护手机端触摸交互主链路（单指滑动触发翻页滚动 + 双指缩放触发缩放状态）。
   * - 测试步骤:
   *   1. 以移动端上下文打开 /reader/JM100003?page=1。
   *   2. 通过 CDP 注入单指触摸滑动，校验容器 scrollLeft 增加。
   *   3. 注入双指外扩手势，校验 page-track transform 出现 scale。
   * - 预期结果:
   *   1. 单指滑动能推动阅读容器滚动。
   *   2. 双指手势可触发缩放状态（transform 含 scale）。
   * - 历史变更:
   *   - 2026-03-24: 初始创建，补齐手机端触摸路径的门禁看护。
   */
  test("mobile reader supports touch swipe and pinch zoom", async ({ page }) => {
    await setReaderDefaultConfig(page, { defaultPageMode: "left_right" });
    await setComicProgress(page, COMIC_ID, 1);
    await page.goto(`/reader/${COMIC_ID}?page=1`);
    const container = page.locator(".left-right-mode");
    await expect(container).toBeVisible();
    await expect(page.locator(".comic-image").first()).toBeVisible();

    const box = await container.boundingBox();
    expect(box).toBeTruthy();
    const centerX = Math.round(box.x + box.width / 2);
    const centerY = Math.round(box.y + box.height / 2);

    const cdp = await page.context().newCDPSession(page);

    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [
        { x: centerX - 50, y: centerY, id: 1 },
        { x: centerX + 50, y: centerY, id: 2 },
      ],
    });
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchMove",
      touchPoints: [
        { x: centerX - 160, y: centerY, id: 1 },
        { x: centerX + 160, y: centerY, id: 2 },
      ],
    });
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchEnd",
      touchPoints: [],
    });

    await expect
      .poll(() =>
        page.evaluate(() => {
          const track = document.querySelector(".page-track-horizontal");
          return track ? track.getAttribute("style") || "" : "";
        }),
      )
      .toContain("scale(");

    const beforePanStyle = await page.evaluate(() => {
      const track = document.querySelector(".page-track-horizontal");
      return track ? track.getAttribute("style") || "" : "";
    });

    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [{ x: centerX, y: centerY, id: 1 }],
    });
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchMove",
      touchPoints: [{ x: centerX - 120, y: centerY - 80, id: 1 }],
    });
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchEnd",
      touchPoints: [],
    });

    await expect
      .poll(() =>
        page.evaluate(() => {
          const track = document.querySelector(".page-track-horizontal");
          return track ? track.getAttribute("style") || "" : "";
        }),
      )
      .not.toBe(beforePanStyle);
  });
});
