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

async function confirmDialog(page) {
  const confirmButton = page.getByRole("button", { name: /确认|确定/ });
  await expect(confirmButton.first()).toBeVisible();
  await confirmButton.first().click();
}

module.exports = {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
  confirmDialog,
};
