// Actual Edge against isolated Java/Python/Vite; synthetic search/model only.
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { expect } from '../frontend/node_modules/@playwright/test/index.mjs';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';
const output = process.argv[2];
const browser = await chromium.launch({channel:'msedge',headless:true});
const context = await browser.newContext({viewport:{width:1366,height:900}});
const page = await context.newPage();
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
const results=[];
try {
  for (const question of ['Public topic','fail report','supplement','empty']) {
    await page.goto('http://127.0.0.1:15173/#/research/new');
    await page.getByLabel('你想探索什么主题？').fill(question);
    await page.getByLabel('检索方式').click();
    await page.getByTitle('模型研究',{exact:true}).click();
    await page.getByRole('button',{name:'开始研究',exact:true}).click();
    await expect(page.getByRole('heading',{name:'研究计划与过程'})).toBeVisible({timeout:25000});
    const panel = page.getByRole('region',{name:'阶段复查'});
    await panel.getByRole('button',{name:'查看阶段记录'}).click();
    await expect(panel.getByText('合成样例 · 不代表真实回答质量')).toBeVisible();
    await panel.getByRole('button',{name:'离线回放完整流程'}).click();
    await expect(panel.getByText('本次离线复查完成，外部请求 0 次。原任务未改动。')).toBeVisible();
    if (question==='fail report') {
      await expect(panel.getByText('回放复现了原研究的失败，不代表研究成功。')).toBeVisible();
      await panel.getByRole('button',{name:'检查已保存报告'}).click();
      await expect(panel.getByRole('alert').filter({hasText:'记录暂不可用'})).toBeVisible();
    } else if (question!=='empty') {
      await panel.getByRole('button',{name:'重新选择证据'}).click();
      await expect(panel.locator('pre').first()).toContainText('offline-reselection');
      await panel.getByRole('button',{name:'检查已保存报告'}).click();
      await expect(panel.locator('pre').first()).toContainText('offline-report-validation');
    }
    if (question==='supplement') {
      await expect(page.getByText(/已完成允许的一轮补搜/)).toBeVisible();
      await page.getByRole('link',{name:'[E1]',exact:true}).click();
      await expect(page.locator('article:focus')).toContainText('Public topic evidence');
    }
    await page.reload();
    await expect(page.getByRole('heading',{name:'研究计划与过程'})).toBeVisible();
    await page.getByRole('button',{name:'查看第 1 次资料'}).click();
    const dialog=page.getByRole('dialog');
    await dialog.getByRole('button',{name:'查看阶段记录'}).click();
    await expect(dialog.getByText('合成样例 · 不代表真实回答质量')).toBeVisible();
    await page.keyboard.press('Escape');
    await page.getByRole('region',{name:'阶段复查'}).getByRole('button',{name:'查看阶段记录'}).click();
    if(question==='Public topic') {
      await page.getByRole('region',{name:'阶段复查'}).scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(output,'trace-desktop.png')});
      await page.setViewportSize({width:390,height:844});
      await page.getByRole('region',{name:'阶段复查'}).scrollIntoViewIfNeeded();
      await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({path:path.join(output,'trace-mobile.png')});
      await page.setViewportSize({width:1366,height:900});
    }
    results.push({question,passed:true,url:page.url()});
  }
  expect(errors).toEqual([]);
  await writeFile(path.join(output,'browser-result.json'),JSON.stringify({passed:true,results,errors},null,2));
  console.log('DEBUG_UI success_failure_supplement_empty_history_refresh_mobile=passed');
} finally { await browser.close(); }
