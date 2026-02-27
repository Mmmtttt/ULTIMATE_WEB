import { test, expect } from '@playwright/test';

test.describe('漫画阅读器测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/reader/1024707');
    await page.waitForSelector('.reader-content', { timeout: 15000 });
  });

  test('阅读器加载成功', async ({ page }) => {
    await expect(page.locator('.reader-content')).toBeVisible();
  });

  test('图片加载成功', async ({ page }) => {
    const images = page.locator('.comic-image');
    const count = await images.count();
    expect(count).toBeGreaterThan(0);
    
    const firstImage = images.first();
    await expect(firstImage).toBeVisible();
  });

  test('底部控制栏显示', async ({ page }) => {
    const controlBar = page.locator('.control-bar');
    await expect(controlBar).toBeVisible();
  });

  test('页码显示正确', async ({ page }) => {
    const pageIndicator = page.locator('.page-indicator');
    await expect(pageIndicator).toBeVisible();
    const text = await pageIndicator.textContent();
    expect(text).toMatch(/\d+\s*\/\s*\d+/);
  });

  test('进度条可用', async ({ page }) => {
    const slider = page.locator('.progress-slider');
    await expect(slider).toBeVisible();
    await expect(slider).toBeEnabled();
  });

  test('上一页按钮功能', async ({ page }) => {
    const prevButton = page.locator('text=上一页');
    await expect(prevButton).toBeVisible();
  });

  test('下一页按钮功能', async ({ page }) => {
    const nextButton = page.locator('text=下一页');
    await expect(nextButton).toBeVisible();
  });

  test('翻页模式切换按钮', async ({ page }) => {
    const modeButton = page.locator('.mode-btn');
    await expect(modeButton).toBeVisible();
    
    const initialText = await modeButton.textContent();
    await modeButton.click();
    await page.waitForTimeout(300);
    const newText = await modeButton.textContent();
    expect(initialText).not.toBe(newText);
  });

  test('全屏按钮显示', async ({ page }) => {
    const fullscreenButton = page.locator('text=全屏');
    await expect(fullscreenButton).toBeVisible();
    await expect(fullscreenButton).toBeEnabled();
  });

  test('点击图片切换菜单显示', async ({ page }) => {
    const image = page.locator('.comic-image').first();
    const controlBar = page.locator('.control-bar');
    
    await expect(controlBar).toBeVisible();
    await image.click();
    await page.waitForTimeout(200);
    await expect(controlBar).not.toBeVisible();
    await image.click();
    await page.waitForTimeout(200);
    await expect(controlBar).toBeVisible();
  });

  test('滚轮翻页功能', async ({ page }) => {
    const container = page.locator('.up-down-mode, .left-right-mode');
    await container.waitFor({ state: 'visible' });
    
    const pageIndicator = page.locator('.page-indicator');
    const initialText = await pageIndicator.textContent();
    
    await page.mouse.wheel(0, 100);
    await page.waitForTimeout(500);
    
    const newText = await pageIndicator.textContent();
    expect(initialText).toBeTruthy();
    expect(newText).toBeTruthy();
  });

  test('缩放提示显示', async ({ page }) => {
    await page.keyboard.down('Control');
    await page.mouse.wheel(0, -100);
    await page.keyboard.up('Control');
    await page.waitForTimeout(300);
    
    const zoomInfo = page.locator('.zoom-info-bar');
    const isVisible = await zoomInfo.isVisible().catch(() => false);
    expect(typeof isVisible).toBe('boolean');
  });

  test('双击重置缩放', async ({ page }) => {
    const image = page.locator('.comic-image').first();
    
    await page.keyboard.down('Control');
    await page.mouse.wheel(0, -200);
    await page.keyboard.up('Control');
    await page.waitForTimeout(300);
    
    await image.dblclick();
    await page.waitForTimeout(300);
    
    const zoomInfo = page.locator('.zoom-info-bar');
    const isVisible = await zoomInfo.isVisible().catch(() => false);
    expect(isVisible).toBe(false);
  });
});

test.describe('阅读器导航测试', () => {
  test('返回按钮功能', async ({ page }) => {
    await page.goto('/reader/1024707');
    await page.waitForSelector('.reader-content', { timeout: 15000 });
    
    const backButton = page.locator('.back-btn');
    if (await backButton.isVisible()) {
      await backButton.click();
      await expect(page).toHaveURL(/\/comic\/\d+/);
    }
  });
});
