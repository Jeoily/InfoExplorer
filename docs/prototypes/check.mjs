// Checks only this self-contained design prototype, never the running app.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const output = new URL('../../frontend/test-results/prototype/', import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const checks = [];
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route(/^https?:/, route => route.abort());
  await page.goto(new URL('./workbench.html', import.meta.url).href);
  await page.screenshot({ path: fileURLToPath(new URL('desktop.png', output)), fullPage: true });
  assert.equal(await page.locator('#panel-answer').isVisible(), true);
  checks.push('Initial answer view and desktop screenshot');
  await page.locator('[data-cite="source-one"]').first().click();
  assert.equal(await page.locator('#panel-evidence').isVisible(), true);
  assert.equal(await page.evaluate(() => document.activeElement.id), 'source-one');
  await page.locator('#source-one .back-answer').click();
  assert.equal(await page.locator('#panel-answer').isVisible(), true);
  checks.push('Citation focus and return to reading');
  await page.locator('#tab-answer').focus();
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.locator('#tab-evidence').getAttribute('aria-selected'), 'true');
  checks.push('Keyboard tab navigation');
  for (const value of ['failure', 'empty', 'complete', 'partial']) {
    await page.selectOption('#scenario', value);
    await page.locator('#tab-answer').click();
    assert.equal(await page.locator('#failure-content').isVisible(), value === 'failure');
    assert.equal(await page.locator('#empty-content').isVisible(), value === 'empty');
    await page.locator('#tab-evidence').click();
    assert.equal(await page.locator('#source-one').isVisible(), value !== 'empty');
    assert.equal(await page.locator('#empty-evidence').isVisible(), value === 'empty');
  }
  checks.push('Four outcome scenarios preserve correct evidence visibility');
  await page.locator('#nav-tracking').click();
  assert.equal(await page.locator('#tracking-view').isVisible(), true);
  await page.locator('#preview-pause').click();
  assert.equal(await page.locator('#preview-refresh').isDisabled(), true);
  await page.locator('#preview-pause').click();
  assert.equal(await page.locator('#preview-refresh').isDisabled(), false);
  await page.locator('#preview-refresh').click();
  assert.match(await page.locator('#toast').textContent(), /没有发送任何请求/);
  await page.locator('.event summary').click();
  assert.equal(await page.locator('.change').isVisible(), true);
  await page.screenshot({ path: fileURLToPath(new URL('tracking.png', output)), fullPage: true });
  checks.push('Tracking pause/resume, mock refresh and revision comparison');
  await page.locator('#nav-research').click();
  await page.locator('#tab-answer').click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#toast').waitFor({ state: 'hidden', timeout: 10000 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: fileURLToPath(new URL('mobile.png', output)), fullPage: true });
  checks.push('390px viewport has no horizontal overflow');
  assert.deepEqual(errors, []);
  checks.push('No page script errors');
  await writeFile(new URL('checks.json', output), JSON.stringify({ passed: checks, pageErrors: errors }, null, 2));
  console.log(JSON.stringify({ passed: checks.length, checks }));
} finally {
  await browser.close();
}
