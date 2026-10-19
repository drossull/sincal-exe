// Exercise the real HTTP asset allowlist, without intercepting browser requests.
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
(async()=>{
  const child=spawn('python',['-u','-c',`from tempfile import TemporaryDirectory
from pathlib import Path
from sincal.web.server import Server
with TemporaryDirectory(prefix='sincal-http-') as folder:
 with Server(0,Path(folder)) as server:
  print(server.origin+'/#token='+server.token,flush=True)
  server.serve_forever()`],{cwd:require('node:path').resolve(__dirname,'..')});
  let browser;
  try{
    const url=await new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>reject(Error('Server startup timed out')),20000);
      child.once('error',reject);child.once('exit',code=>reject(Error('Server exit '+code)));
      child.stdout.once('data',data=>{clearTimeout(timeout);resolve(data.toString().trim());});
    });
    browser=await chromium.launch({channel:'msedge',headless:true});
    const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],failed=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',r=>{if(r.status()>=400)failed.push([new URL(r.url()).pathname,r.status()]);});
    await page.goto(url);
    await page.locator('#sidebar button[data-page="project"]').waitFor();
    await page.locator('#main h2').first().waitFor();
    await page.locator('#sidebar button[data-page="prospecciones"]').click();
    await page.locator('.module-tabs button[data-page="prospect"]').click();
    await page.getByRole('heading',{name:'Perfiles geofísicos',exact:true}).waitFor();
    assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
    if(process.env.SINCAL_UI_SCREENSHOT)await page.screenshot({path:process.env.SINCAL_UI_SCREENSHOT});
    console.log('OK: real HTTP startup, populated navigation, Home and Perfiles geofisicos; no JS or HTTP errors.');
  }finally{if(browser)await browser.close();child.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
