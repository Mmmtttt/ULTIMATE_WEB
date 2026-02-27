import { test, expect } from '@playwright/test';

test.describe('主页测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('页面标题正确显示', async ({ page }) => {
    await expect(page).toHaveTitle(/漫画阅读/);
  });

  test('漫画列表加载成功', async ({ page }) => {
    await page.waitForSelector('.comic-grid', { timeout: 10000 });
    const comicCards = await page.locator('.comic-card').count();
    expect(comicCards).toBeGreaterThan(0);
  });

  test('漫画卡片显示封面图', async ({ page }) => {
    await page.waitForSelector('.comic-card', { timeout: 10000 });
    const firstCard = page.locator('.comic-card').first();
    const img = firstCard.locator('img');
    await expect(img).toBeVisible();
  });

  test('漫画卡片悬停显示标题', async ({ page }) => {
    await page.waitForSelector('.comic-card', { timeout: 10000 });
    const firstCard = page.locator('.comic-card').first();
    await firstCard.hover();
    const title = page.locator('.comic-title-tooltip');
    await expect(title).toBeVisible();
  });

  test('点击漫画卡片跳转到详情页', async ({ page }) => {
    await page.waitForSelector('.comic-card', { timeout: 10000 });
    const firstCard = page.locator('.comic-card').first();
    await firstCard.click();
    await expect(page).toHaveURL(/\/comic\/\d+/);
  });

  test('底部导航栏显示正确', async ({ page }) => {
    const navBar = page.locator('.bottom-nav');
    await expect(navBar).toBeVisible();
    
    const homeTab = page.locator('.nav-item').first();
    await expect(homeTab).toHaveText('首页');
    
    const mineTab = page.locator('.nav-item').last();
    await expect(mineTab).toHaveText('我的');
  });
});
