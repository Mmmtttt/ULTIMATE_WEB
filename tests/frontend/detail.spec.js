import { test, expect } from '@playwright/test';

test.describe('漫画详情页测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/comic/1024707');
  });

  test('页面加载成功', async ({ page }) => {
    await page.waitForSelector('.comic-detail', { timeout: 10000 });
    await expect(page.locator('.comic-detail')).toBeVisible();
  });

  test('封面图显示正确', async ({ page }) => {
    await page.waitForSelector('.cover-image', { timeout: 10000 });
    const cover = page.locator('.cover-image');
    await expect(cover).toBeVisible();
  });

  test('漫画标题显示', async ({ page }) => {
    await page.waitForSelector('.comic-info', { timeout: 10000 });
    const title = page.locator('.comic-title');
    await expect(title).toBeVisible();
    const titleText = await title.textContent();
    expect(titleText?.length).toBeGreaterThan(0);
  });

  test('作者信息显示', async ({ page }) => {
    await page.waitForSelector('.comic-info', { timeout: 10000 });
    const author = page.locator('.comic-author');
    await expect(author).toBeVisible();
  });

  test('标签显示', async ({ page }) => {
    await page.waitForSelector('.comic-tags', { timeout: 10000 });
    const tags = page.locator('.tag-item');
    const tagCount = await tags.count();
    expect(tagCount).toBeGreaterThanOrEqual(0);
  });

  test('阅读进度显示', async ({ page }) => {
    await page.waitForSelector('.comic-info', { timeout: 10000 });
    const progress = page.locator('.progress-text');
    await expect(progress).toBeVisible();
  });

  test('开始阅读按钮可用', async ({ page }) => {
    await page.waitForSelector('.comic-actions', { timeout: 10000 });
    const readButton = page.locator('.read-btn');
    await expect(readButton).toBeVisible();
    await expect(readButton).toBeEnabled();
  });

  test('点击开始阅读跳转到阅读器', async ({ page }) => {
    await page.waitForSelector('.read-btn', { timeout: 10000 });
    const readButton = page.locator('.read-btn');
    await readButton.click();
    await expect(page).toHaveURL(/\/reader\/\d+/);
  });

  test('返回按钮功能', async ({ page }) => {
    await page.waitForSelector('.back-btn', { timeout: 10000 });
    const backButton = page.locator('.back-btn');
    await expect(backButton).toBeVisible();
    await backButton.click();
    await expect(page).toHaveURL('/');
  });
});
