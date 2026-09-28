import { open, sleep } from './lib.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';
const [,, url, outDir, specJson] = process.argv;
mkdirSync(outDir, { recursive: true });
const specs = JSON.parse(specJson);
const b = await open(url);
for (let y = 0; y < 14000; y += 600) { await b.ev(`window.scrollTo(0,${y})`); await sleep(200); }
const hide = `(() => { for (const e of document.querySelectorAll('body *')) { const s = getComputedStyle(e);
  if ((s.position==='fixed'||s.position==='sticky') && !e.closest('.capabilities-pin')) e.style.visibility='hidden'; } })()`;
for (const s of specs) {
  if (s.scroll != null) { await b.ev(`window.scrollTo(0,${s.scroll})`); await sleep(s.wait ?? 1800); }
  await b.ev(hide);
  const find = s.sel ? `document.querySelector(${JSON.stringify(s.sel)})`
    : `(() => { let e=[...document.querySelectorAll('body *')].find(e=>e.children.length<4 && e.textContent.trim().startsWith(${JSON.stringify(s.text)})); for(let i=0;i<${s.up||0}&&e;i++) e=e.parentElement; return e; })()`;
  if (s.scroll == null && !s.rect) { await b.ev(`(${find}).scrollIntoView({block:'center'})`); await sleep(s.wait ?? 1800); await b.ev(hide); }
  if (s.layer != null) { await b.ev(`document.querySelectorAll('.capabilities-pin__layer').forEach((e,i)=>{e.style.opacity = i===${s.layer} ? '1' : '0'; e.style.transform='none';})`); await sleep(600); }
  if (s.click) { await b.ev(`(() => { const e=[...document.querySelectorAll('button,a,[role=tab],div,span')].find(e=>e.textContent.trim()===${JSON.stringify(s.click)}); e && e.click(); })()`); await sleep(1500); }
  const r = s.rect ? {x:s.rect[0],y:s.rect[1],w:s.rect[2],h:s.rect[3]} : await b.ev(`(() => { const e=${find}; if(!e) return null; const r=e.getBoundingClientRect(); return {x:r.left+scrollX,y:r.top+scrollY,w:r.width,h:r.height}; })()`);
  if (!r) { console.log(s.name, 'NOTFOUND'); continue; }
  const pad = s.pad ?? 0;
  const shot = await b.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
    clip: { x: r.x - pad, y: r.y - pad, width: r.w + 2 * pad, height: r.h + 2 * pad, scale: 1 } });
  writeFileSync(`${outDir}/${s.name}.png`, Buffer.from(shot.data, 'base64'));
  console.log(s.name, Math.round(r.w), 'x', Math.round(r.h));
}
b.close();
