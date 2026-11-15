const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
const out='/workspaces/DR7-Studio/work/characters/shenron/idle-v1/evidence';
const browser=await chromium.launch({headless:true,executablePath:'/home/codespace/.cache/ms-playwright/chromium-1254/chrome-linux64/chrome',args:['--no-sandbox']});
const context=await browser.newContext({viewport:{width:1600,height:1200},recordVideo:{dir:out+'/browser-video',size:{width:1600,height:1200}}});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://localhost:8080/?character=shenron&clip=idle');
await page.waitForFunction(()=>state.activeChar?.character_id==='shenron' && state.images.size>0).catch(async()=>{await page.waitForTimeout(1500)});
const results=[];
for(const bg of ['light','dark','checker']){
await page.evaluate(bg=>{state.bgMode=bg;state.stepIdx=0;state.elapsed=0;state.playing=true;},bg);
const samples=await page.evaluate(()=>new Promise(resolve=>{const a=[];let previous=-1;const start=performance.now();function sample(){if(state.stepIdx!==previous){a.push({ms:performance.now()-start,frame:state.stepIdx});previous=state.stepIdx;}if(performance.now()-start<1700)requestAnimationFrame(sample);else resolve(a);}sample();}));
results.push({background:bg,samples});
await page.locator('#inspectorCanvas').screenshot({path:out+`/browser-${bg}.png`});
for(let i=0;i<4;i++){await page.evaluate(i=>{state.playing=false;state.stepIdx=i;renderInspector();},i);await page.locator('#inspectorCanvas').screenshot({path:out+`/browser-${bg}-frame${i}.png`});}
}
console.log(await page.evaluate(()=>({character:state.activeChar.character_id,clip:state.activeClipName,playing:state.playing,error:document.getElementById('runtimeErrorBanner').textContent})));
fs.writeFileSync(out+'/browser-playback.json',JSON.stringify({errors,results},null,2));
await context.close();await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
