const path = require("path");

const repoRoot = path.resolve(__dirname, "../..");
const { test, expect } = require(
  path.join(repoRoot, "comic_frontend", "node_modules", "@playwright/test"),
);

function startApiRequestRecorder(page) {
  const requests = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/api/v1/")) {
      requests.push({
        method: request.method(),
        url,
        body: request.postData() || "",
      });
    }
  });
  return requests;
}

function hasApiCall(requests, matcher) {
  if (typeof matcher === "function") {
    return requests.some(matcher);
  }
  return requests.some((item) => item.url.includes(matcher));
}

async function getMediaTitles(page) {
  const titles = await page.locator(".media-card .media-title").allTextContents();
  return titles.map((item) => item.trim()).filter(Boolean);
}

async function confirmDialog(page) {
  await page.waitForTimeout(300);

  const overlay = page.locator(".van-overlay").first();
  try {
    if (await overlay.isVisible({ timeout: 500 })) {
      await overlay.waitFor({ state: "hidden", timeout: 3000 }).catch(() => {});
    }
  } catch {
  }

  await page.waitForTimeout(200);

  const candidates = [
    page.getByRole("button", { name: /确认|确定|Confirm|OK/i }),
    page.locator(".van-dialog__confirm"),
    page.locator(".van-button--primary"),
  ];

  for (const locator of candidates) {
    const first = locator.first();
    const visible = await first.isVisible().catch(() => false);
    if (visible) {
      await first.click({ force: true });
      return;
    }
  }

  throw new Error("confirm dialog button not found");
}

module.exports = {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  getMediaTitles,
  confirmDialog,
};
