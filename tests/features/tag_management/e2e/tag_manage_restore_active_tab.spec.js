const { test, expect } = require("../../../shared/e2e_helpers");

test("tag manage restores the previously active tab after back navigation", async ({ page }) => {
  await page.route("https://api.github.com/repos/Mmmtttt/ULTIMATE_WEB/releases/latest", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tag_name: "0.0.0",
        html_url: "https://github.com/Mmmtttt/ULTIMATE_WEB/releases",
      }),
    });
  });

  await page.route("**/api/v1/tag/list**", async (route) => {
    const url = new URL(route.request().url());
    const contentType = url.searchParams.get("content_type");
    const data = contentType === "video"
      ? [{ id: "tag-video-restore", name: "Video Restore Tag", video_count: 3 }]
      : [{ id: "tag-comic-restore", name: "Comic Restore Tag", comic_count: 5 }];

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, data }),
    });
  });

  await page.route("**/api/v1/tag/videos**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        data: {
          tag: { id: "tag-video-restore", name: "Video Restore Tag" },
          home_videos: [],
          recommendation_videos: [],
        },
      }),
    });
  });

  await page.goto("/tags");
  await expect(page.getByText("标签管理")).toBeVisible();

  const videoTab = page.getByRole("tab", { name: "视频标签" });
  await videoTab.click();
  await expect(videoTab).toHaveAttribute("aria-selected", "true");

  await page.getByText("Video Restore Tag").click();
  await expect(page).toHaveURL(/\/video-tag\/tag-video-restore$/);
  await expect(page.getByText("Video Restore Tag")).toBeVisible();

  await page.goBack();

  await expect(page.getByText("标签管理")).toBeVisible();
  await expect(page.locator(".van-tab").filter({ hasText: "视频标签" }).first()).toHaveClass(/van-tab--active/);
  await expect(page.getByText("Video Restore Tag")).toBeVisible();
});
