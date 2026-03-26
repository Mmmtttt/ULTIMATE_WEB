const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const frontendRoot = path.join(repoRoot, "comic_frontend");
const { defineConfig, devices } = require(path.join(frontendRoot, "node_modules", "@playwright/test"));

const backendPort = 5010;
const frontendPort = 4173;
const isHeaded = process.env.PW_HEADED === "1";
const defaultWorkers = 1;
const workerCount = Number.parseInt(process.env.PW_WORKERS || String(defaultWorkers), 10);
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
  // Tests share one backend/runtime and mutate overlapping seed data.
  // Keep deterministic by default; allow local override via PW_WORKERS.
  // Suggested upper bound for local trials: maxSuggestedWorkers.
  workers: Number.isFinite(workerCount) && workerCount > 0 ? workerCount : 1,
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
