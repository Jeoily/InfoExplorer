import {test,expect} from '@playwright/test';

test('追踪主题保存、两轮比较、暂停与刷新',async({page})=>{
 await page.goto('/#/topics');
 await page.getByRole('button',{name:'新建追踪主题'}).click();
 await page.getByLabel('主题名称').fill('公开网页持续追踪');
 await page.getByLabel('持续关注的问题').fill('PUBLIC_WEB_TOPIC');
 await page.getByRole('button',{name:'保存主题',exact:true}).click();
 await expect(page.getByRole('heading',{name:'公开网页持续追踪'})).toBeVisible();
 await page.getByRole('button',{name:'现在检查',exact:true}).click();
 await expect(page.getByText('首次发现',{exact:true})).toBeVisible({timeout:20000});
 await expect(page.locator('article img')).toHaveCount(0);
 await page.getByRole('button',{name:'现在检查',exact:true}).click();
 await expect(page.getByText('正文未变',{exact:true})).toBeVisible({timeout:20000});
 await expect(page.getByRole('link',{name:'查看本轮报告与来源 →'})).toHaveCount(2);
 await page.getByText('查看上次保存的摘录').click();
 await expect(page.getByText('Public evidence <img src=x onerror=alert(1)>',{exact:true}).first()).toBeVisible();
 await page.getByRole('button',{name:'暂停追踪',exact:true}).click();
 await expect(page.getByRole('button',{name:'现在检查',exact:true})).toBeDisabled();
 await page.reload();
 await expect(page.getByRole('button',{name:'恢复追踪',exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('自动模型检查被拒绝，不发起研究',async({page})=>{
 await page.goto('/#/topics');await page.getByRole('button',{name:'新建追踪主题'}).click();
 await page.getByLabel('主题名称').fill('仅手动模型');await page.getByLabel('持续关注的问题').fill('public topic');
 await page.getByLabel('检查方式').click();await page.getByTitle('模型研究 · 每轮会调用模型').click();
 await page.getByLabel('自动检查频率').click();await page.getByTitle('每小时',{exact:true}).click();
 await page.getByRole('button',{name:'保存主题',exact:true}).click();
 await expect(page.getByText('模型研究仅支持手动检查',{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'新建主题',exact:true})).toBeVisible();
});
