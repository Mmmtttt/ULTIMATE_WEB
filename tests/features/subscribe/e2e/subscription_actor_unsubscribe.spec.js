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

test("actor subscription add dialog can submit a manual actor source", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("app_mode", "video");
  });

  const actorName = uniqueActorName();
  const subscribeRequests = [];
  let actorList = [];

  await page.route("**/api/v1/actor/list", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "成功",
        data: actorList,
      }),
    });
  });

  await page.route("**/api/v1/actor/subscribe", async (route) => {
    const payload = route.request().postDataJSON();
    subscribeRequests.push(payload);
    actorList = [
      {
        id: "actor-manual-source",
        name: payload.name,
        actor_id: payload.actor_refs?.[0]?.actor_id || "",
        actor_refs: payload.actor_refs || [],
        last_work_title: "",
        new_work_count: 0,
      },
    ];

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 200,
        msg: "订阅成功",
        data: actorList[0],
      }),
    });
  });

  await page.goto("/subscribe");
  await expect(page).toHaveURL(/\/subscribe$/);

  await page.locator(".header-buttons .van-button").last().click();
  await expect(page.getByText("手动指定来源")).toBeVisible();
  await page.getByText("手动指定来源").click();

  const dialogInputs = page.locator(".van-dialog input");
  await dialogInputs.nth(0).fill(actorName);
  await dialogInputs.nth(1).fill("javdb");
  await dialogInputs.nth(2).fill("https://javdb.com/actors/J2EwW");
  await page.locator(".van-dialog__confirm").click();

  await expect.poll(() => subscribeRequests.length).toBe(1);
  expect(subscribeRequests[0]).toMatchObject({
    name: actorName,
    actor_refs: [
      {
        platform: "javdb",
        actor_id: "J2EwW",
        actor_name: actorName,
        actor_url: "https://javdb.com/actors/J2EwW",
      },
    ],
  });

  await expect(
    page.getByTestId("subscription-actor-card").filter({ hasText: actorName })
  ).toBeVisible();
});
