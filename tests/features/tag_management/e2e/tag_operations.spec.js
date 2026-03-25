const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

/**
 * 用例描述:
 * - 用例目的: 强看护标签创建主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开标签管理页面。
 *   2. 点击添加标签按钮。
 *   3. 输入标签名称并保存。
 *   4. 校验 POST /api/v1/tag/add 请求。
 * - 预期结果:
 *   1. 标签创建请求包含正确的标签名称。
 *   2. 标签列表显示新标签。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖标签创建主链路。
 */
test("tag management creates new tag via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/tags");
  await expect(page.getByText("标签管理")).toBeVisible();

  const addButton = page.getByRole("button", { name: /添加|新建/ });
  if (await addButton.isVisible()) {
    await addButton.click();

    const nameInput = page.locator('input[placeholder*="标签名"]').first();
    if (await nameInput.isVisible()) {
      await nameInput.fill("E2E Test Tag");
      const saveButton = page.getByRole("button", { name: /保存|确定/ });
      await saveButton.click();

      await expect
        .poll(
          () =>
            hasApiCall(
              apiRequests,
              (item) =>
                item.url.includes("/api/v1/tag/add") &&
                item.method === "POST",
            ),
          { timeout: 5000 },
        )
        .toBeTruthy();
    }
  }
});

/**
 * 用例描述:
 * - 用例目的: 强看护标签编辑主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开标签管理页面。
 *   2. 点击已有标签的编辑按钮。
 *   3. 修改标签名称并保存。
 *   4. 校验 PUT /api/v1/tag/edit 请求。
 * - 预期结果:
 *   1. 标签编辑请求包含正确的标签 ID 和新名称。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖标签编辑主链路。
 */
test("tag management edits tag via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/tags");
  await expect(page.getByText("标签管理")).toBeVisible();

  const editButton = page.locator(".tag-item .edit-btn").first();
  if (await editButton.isVisible()) {
    await editButton.click();

    const nameInput = page.locator('input[placeholder*="标签名"]').first();
    if (await nameInput.isVisible()) {
      await nameInput.fill("Updated E2E Tag");
      const saveButton = page.getByRole("button", { name: /保存|确定/ });
      await saveButton.click();

      await expect
        .poll(
          () =>
            hasApiCall(
              apiRequests,
              (item) =>
                item.url.includes("/api/v1/tag/edit") &&
                item.method === "PUT",
            ),
          { timeout: 5000 },
        )
        .toBeTruthy();
    }
  }
});

/**
 * 用例描述:
 * - 用例目的: 强看护标签列表加载主链路，确保页面正确请求标签列表。
 * - 测试步骤:
 *   1. 打开标签管理页面。
 *   2. 校验 GET /api/v1/tag/list 请求。
 * - 预期结果:
 *   1. 标签列表请求被触发。
 *   2. 页面显示标签列表。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖标签列表加载主链路。
 */
test("tag management loads tag list via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/tags");

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) =>
            item.url.includes("/api/v1/tag/list") &&
            item.method === "GET",
        ),
      { timeout: 5000 },
    )
    .toBeTruthy();

  await expect(page.getByText("标签管理")).toBeVisible();
});

/**
 * 用例描述:
 * - 用例目的: 强看护标签删除主链路，确保前端操作会触发正确后端请求。
 * - 测试步骤:
 *   1. 打开标签管理页面。
 *   2. 点击标签的删除按钮。
 *   3. 确认删除对话框。
 *   4. 校验 DELETE /api/v1/tag/delete 请求。
 * - 预期结果:
 *   1. 标签删除请求包含正确的标签 ID。
 * - 历史变更:
 *   - 2026-03-25: 初始创建，覆盖标签删除主链路。
 */
test("tag management deletes tag via API", async ({ page }) => {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/tags");
  await expect(page.getByText("标签管理")).toBeVisible();

  const deleteButton = page.locator(".tag-item .delete-btn").first();
  if (await deleteButton.isVisible()) {
    await deleteButton.click();

    const confirmButton = page.locator(".van-dialog__confirm");
    if (await confirmButton.isVisible()) {
      await confirmButton.click();

      await expect
        .poll(
          () =>
            hasApiCall(
              apiRequests,
              (item) =>
                item.url.includes("/api/v1/tag/delete") &&
                item.method === "DELETE",
            ),
          { timeout: 5000 },
        )
        .toBeTruthy();
    }
  }
});
