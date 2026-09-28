import { spawn } from 'node:child_process';
export const sleep = ms => new Promise(r => setTimeout(r, ms));
export async function open(url, port = 9334) {
  const chrome = spawn('chromium-browser', ['--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
    `--remote-debugging-port=${port}`, '--window-size=1600,1000', `--user-data-dir=${process.env.HOME}/snapshots/cdp/profile${port}`, 'about:blank'], { stdio: 'ignore' });
  let ws;
  for (let i = 0; i < 40; i++) {
    try { const l = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); const p = l.find(t => t.type === 'page');
      if (p) { ws = new WebSocket(p.webSocketDebuggerUrl); break; } } catch {}
    await sleep(500);
  }
  await new Promise(r => ws.onopen = r);
  let id = 0; const pending = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m.result ?? m.error); pending.delete(m.id); } };
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.value;
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 2, mobile: false });
  await send('Page.navigate', { url });
  await sleep(6000);
  return { send, ev, close: () => { ws.close(); chrome.kill(); } };
}
