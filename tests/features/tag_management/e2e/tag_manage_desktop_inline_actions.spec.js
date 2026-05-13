const { test, expect } = require("../../../shared/e2e_helpers");

test("desktop tag management exposes inline edit and delete actions", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });

  await page.route("**/api/v1/tag/list**", async (route) => {
    const requestUrl = route.request().url();
    const isVideo = requestUrl.includes("content_type=video");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: isVideo
          ? [{ id: "vtag-1", name: "视频标签", video_count: 8 }]
          : [{ id: "tag-1", name: "桌面可操作标签", comic_count: 12 }],
      }),
    });
  });

  await page.route("**/api/v1/tag/all-comics**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: {
          home_comics: [],
          recommendation_comics: [],
        },
      }),
    });
  });

  await page.goto("/tags");

  await expect(page.getByText("标签管理")).toBeVisible();
  await expect(page.getByText("桌面可操作标签")).toBeVisible();
  await expect(page.getByTestId("tag-edit-inline")).toBeVisible();
  await expect(page.getByTestId("tag-delete-inline")).toBeVisible();
});
