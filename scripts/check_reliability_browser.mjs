import {chromium} from '../frontend/node_modules/playwright/index.mjs';
import {expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {writeFile} from 'node:fs/promises';
const directory=process.argv[2];
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try {
 await page.goto('http://127.0.0.1:15174/#/research/new');
 await page.locator('#question').fill('browser slow');
 await page.getByRole('combobox',{name:'检索方式'}).click();
 await page.getByTitle('模型研究',{exact:true}).click();
 // Let server persist, then lose only the response, as a browser disconnect would.
 let id;
 await page.route('**/api/v1/research-tasks',async route=>{
  if(route.request().method()!=='POST')return route.continue();
  const response=await route.fetch();id=(await response.json()).id;
  await route.abort('failed');
 });
 await page.getByRole('button',{name:'开始研究',exact:true}).click();
 await expect(page.getByRole('alert')).toBeVisible();
 await page.unroute('**/api/v1/research-tasks');
 await page.reload();
 await expect(page.locator('#question')).toHaveValue('browser slow');
 await page.getByRole('button',{name:'开始研究',exact:true}).click();
 await expect(page).toHaveURL(new RegExp(id+'$'));
 await expect(page.getByText('正在生成报告',{exact:true})).toBeVisible({timeout:12000});
 await page.reload();
 await expect(page.getByText('正在生成报告',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'取消研究',exact:true}).click();
 await page.getByRole('dialog').getByRole('button',{name:'取消研究',exact:true}).click();
 await expect(page.getByText('本次研究已取消',{exact:true}).first()).toBeVisible({timeout:15000});
 const runs=await (await page.request.get('http://127.0.0.1:15174/api/v1/research-tasks/'+id+'/runs')).json();
 expect(runs).toHaveLength(1);
 await page.screenshot({path:directory+'/cancelled.png',fullPage:true});
 expect(errors).toEqual([]);
 await writeFile(directory+'/browser-result.json',JSON.stringify({id,errors,refresh:true,cancel:true,ambiguousSubmissionRecovered:true}));
} finally {await browser.close();}
