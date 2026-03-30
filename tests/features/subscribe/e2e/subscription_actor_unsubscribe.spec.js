const { test, expect, confirmDialog } = require("../../../shared/e2e_helpers");

function uniqueActorName() {
  return `E2E-Actor-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

test("subscribed actor can be unsubscribed from subscription page", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("app_mode", "video");
  });

  const actorName = uniqueActorName();

  await page.goto("/subscribe");
  await expect(page).toHaveURL(/\/subscribe$/);

  const addButton = page.locator(".header-buttons .van-button").last();
  await expect(addButton).toBeVisible();
  await addButton.click();

  const dialogInput = page.locator(".van-dialog input").first();
  await expect(dialogInput).toBeVisible();
  await dialogInput.fill(actorName);
  await page.locator(".van-dialog__confirm").click();

  const actorCard = page
    .getByTestId("subscription-actor-card")
    .filter({ hasText: actorName })
    .first();
  await expect(actorCard).toBeVisible();

  await actorCard.getByTestId("subscription-actor-unsubscribe").click();
  await confirmDialog(page);

  await expect(actorCard).toBeHidden();
});

