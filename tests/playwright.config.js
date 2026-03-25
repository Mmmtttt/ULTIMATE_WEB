const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const frontendRoot = path.join(repoRoot, "comic_frontend");
const { defineConfig, devices } = require(path.join(frontendRoot, "node_modules", "@playwright/test"));

const backendPort = 5010;
const frontendPort = 4173;
const isHeaded = process.env.PW_HEADED === "1";
const slowMo = Number.parseInt(process.env.PW_SLOWMO || "0", 10);
const launchOptions = {};
if (Number.isFinite(slowMo) && slowMo > 0) {
  launchOptions.slowMo = slowMo;
}

module.exports = defineConfig({
  testDir: path.join(__dirname, "features"),
  testMatch: "**/e2e/**/*.spec.js",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // E2E cases share the same isolated runtime backend process; keep single worker for determinism.
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: path.join(__dirname, "playwright-report"), open: "never" }],
  ],
  outputDir: path.join(__dirname, "test-results"),
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    headless: !isHeaded,
    launchOptions,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
