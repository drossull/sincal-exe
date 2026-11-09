// Isolated real-browser checks of the parameter/viewer divider. No CAD or user data.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const harness=`<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/app.css">
<style>body{margin:0;padding:20px}.rebar-live-editor{min-height:600px}.rebar-live-preview{min-height:400px}</style></head>
<body><section class="rebar-live-page"></section><script type="module">
import {mountRebarSplitter} from '/rebar_splitter.js';
const page=document.querySelector('section');let dispose;
window.mount=()=>{dispose?.();page.innerHTML='<div class="rebar-live-shell"><div class="rebar-live-editor"><h2>Parámetros</h2><label>Largo<input value="750"></label></div><aside class="rebar-live-preview"><h2>Visor</h2><svg viewBox="0 0 1000 680" data-zoom="2.4" data-yaw="0.7"><line x1="100" y1="300" x2="900" y2="300" stroke="#ffb400"/></svg></aside></div>';
 const shell=page.firstChild;dispose=mountRebarSplitter(shell,shell.children[0],shell.children[1]);};
window.leave=()=>{window.oldDivider=document.querySelector('[role=separator]');window.oldShell=page.firstChild;page.replaceChildren();};
mount();window.ready=true;
</script></body></html>`;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html'});
   if(['app.css','rebar_splitter.js'].includes(name)||name.endsWith('.ttf'))return route.fulfill({body:fs.readFileSync(path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-splitter.test/');await page.waitForFunction(()=>window.ready);
  const divider=page.getByRole('separator',{name:'Ancho de parámetros y visor',includeHidden:true});
  const editor=page.locator('.rebar-live-editor'),preview=page.locator('.rebar-live-preview');
  const widths=async()=>Promise.all([editor,preview].map(el=>el.evaluate(e=>e.getBoundingClientRect().width)));
  const initial=await widths(),box=await divider.boundingBox();
  await page.getByLabel('Largo').fill('860');
  await page.mouse.move(box.x+box.width/2,box.y+180);await page.mouse.down();
  await page.mouse.move(box.x+box.width/2+150,box.y+180,{steps:5});await page.mouse.up();
  const moved=await widths();assert(Math.abs(moved[0]-initial[0]-150)<1);assert(Math.abs(initial[1]-moved[1]-150)<1);
  assert.equal(await page.getByLabel('Largo').inputValue(),'860');
  assert.equal(await preview.locator('svg').getAttribute('data-zoom'),'2.4');
  assert.equal(await preview.locator('svg').getAttribute('data-yaw'),'0.7');
  assert.equal(await page.locator('.rebar-panels-resizing').count(),0);

  // Pointer capture continues resizing outside the handle and clamps both panels.
  const updated=await divider.boundingBox();await page.mouse.move(updated.x+12,updated.y+180);await page.mouse.down();
  await page.mouse.move(10,updated.y+180);assert(Math.abs((await widths())[0]-320)<1);
  await page.mouse.move(1430,updated.y+180);await page.mouse.up();assert(Math.abs((await widths())[1]-420)<1);

  // The separator is accessible without a mouse and never shrinks a panel below its limit.
  await divider.focus();await divider.press('Home');assert(Math.abs((await widths())[0]-320)<1);
  await divider.press('ArrowRight');assert(Math.abs((await widths())[0]-330)<1);
  await divider.press('Shift+ArrowRight');assert(Math.abs((await widths())[0]-380)<1);
  await divider.press('End');assert(Math.abs((await widths())[1]-420)<1);
  await divider.press('ArrowLeft');const saved=await widths();
  assert(Number(await divider.getAttribute('aria-valuenow'))>0);
  assert((await divider.getAttribute('aria-valuetext')).includes('visor'));

  // Recreating the entry/exit panels remembers their split, without changing project state.
  await page.evaluate(()=>mount());const remounted=await widths();assert(Math.abs(remounted[0]-saved[0])<1);
  await page.setViewportSize({width:760,height:1000});await page.waitForTimeout(50);
  assert.equal(await divider.isVisible(),false);assert.equal(await divider.getAttribute('tabindex'),'-1');
  assert.equal(await preview.evaluate(e=>getComputedStyle(e).position),'static');
  assert((await preview.boundingBox()).y>=(await editor.boundingBox()).y+(await editor.boundingBox()).height);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:1440,height:1000});await page.waitForTimeout(50);
  assert.equal(await divider.isVisible(),true);assert(Math.abs((await widths())[0]-saved[0])<1);
  fs.mkdirSync(path.join(root,'tmp'),{recursive:true});await page.screenshot({path:path.join(root,'tmp/rebar-splitter.png')});

  // Cancelled gestures and removing the page release capture and listeners.
  const final=await divider.boundingBox();await page.mouse.move(final.x+12,final.y+120);await page.mouse.down();
  await page.evaluate(()=>window.dispatchEvent(new Event('blur')));assert.equal(await page.locator('.rebar-panels-resizing').count(),0);await page.mouse.up();
  await page.evaluate(()=>leave());await page.waitForTimeout(30);
  const detached=await page.evaluate(()=>{const before=oldShell.style.getPropertyValue('--rebar-editor-width');oldDivider.dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true}));return [before,oldShell.style.getPropertyValue('--rebar-editor-width')];});
  assert.equal(detached[0],detached[1]);assert.deepEqual(errors,[]);
  console.log('PASS: drag and keyboard resize, width limits, state preservation, responsive stack, remount and cleanup');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
