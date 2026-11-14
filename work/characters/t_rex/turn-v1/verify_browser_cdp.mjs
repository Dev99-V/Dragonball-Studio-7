#!/usr/bin/env node
/** Live headless Chromium CDP verification of T-rex turn-v1 on http://localhost:8080. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const CHROME_BIN = '/home/codespace/.cache/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-linux64/chrome-headless-shell';
const VERIF_DIR = path.resolve('work/characters/t_rex/turn-v1/verification');
const BASE_URL = 'http://localhost:8080';

fs.mkdirSync(VERIF_DIR, { recursive: true });
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dr7-cdp-'));
const port = 9229;

const chrome = spawn(CHROME_BIN, [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',
  '--disable-gpu',
  '--disable-software-rasterizer',
  '--remote-allow-origins=*',
  '--remote-debugging-address=127.0.0.1',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${userDataDir}`,
  '--window-size=1440,1200',
  'about:blank',
], { stdio: ['ignore', 'pipe', 'pipe'] });
chrome.stderr.on('data', d => { const s = String(d); if (s.includes('ERROR') || s.includes('DevTools')) console.error('[chrome]', s.trim()); });

async function getWsUrl() {
  for (let i = 0; i < 80; i++) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = targets.find(t => t.type === 'page');
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {}
    await new Promise(r => setTimeout(r, 150));
  }
  throw new Error('Timed out waiting for Chromium CDP endpoint');
}

class CDP {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.pending = new Map();
    this.consoleErrors = [];
    this.exceptions = [];
    this.failedRequests = [];
    this.ready = new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });
    this.ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      } else if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
        this.consoleErrors.push(msg.params.args.map(a => a.value ?? a.description).join(' '));
      } else if (msg.method === 'Runtime.exceptionThrown') {
        this.exceptions.push(msg.params.exceptionDetails.text);
      } else if (msg.method === 'Network.responseReceived' && msg.params.response.status >= 400) {
        this.failedRequests.push(`${msg.params.response.status} ${msg.params.response.url}`);
      } else if (msg.method === 'Network.loadingFailed') {
        this.failedRequests.push(`FAILED ${msg.params.errorText}`);
      }
    };
  }
  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async evalExpr(expression) {
    const res = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (res.exceptionDetails) {
      throw new Error(`Eval exception: ${JSON.stringify(res.exceptionDetails)}`);
    }
    return res.result?.value;
  }
  async screenshot(outFile, clip = null) {
    const params = { format: 'png', captureBeyondViewport: true };
    if (clip) params.clip = { ...clip, scale: 1 };
    const { data } = await this.send('Page.captureScreenshot', params);
    fs.writeFileSync(path.join(VERIF_DIR, outFile), Buffer.from(data, 'base64'));
  }
  close() {
    this.ws.close();
  }
}

const wait = (ms) => new Promise(r => setTimeout(r, ms));

try {
  const wsUrl = await getWsUrl();
  const cdp = new CDP(wsUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Network.enable');

  // 1) Navigate directly to T-rex dead-front turn frame (frame 2) paused on 3 backgrounds
  await cdp.send('Page.navigate', { url: `${BASE_URL}/?character=t_rex&clip=turn&frame=2&paused=1` });
  for (let i = 0; i < 60; i++) {
    const ready = await cdp.evalExpr(`(() => {
      const c = document.getElementById('inspectorCanvas');
      if (!c) return false;
      const d = c.getContext('2d').getImageData(Math.floor(c.width/2)-40, Math.floor(c.height/2)-40, 80, 80).data;
      const baseR = d[0], baseG = d[1], baseB = d[2];
      let diff = 0;
      for (let p = 0; p < d.length; p += 4) {
        if (Math.abs(d[p]-baseR) + Math.abs(d[p+1]-baseG) + Math.abs(d[p+2]-baseB) > 25) diff++;
      }
      return diff > 50;
    })()`);
    if (ready) break;
    await wait(150);
  }
  await cdp.evalExpr(`document.getElementById('inspectorCanvas').scrollIntoView({ block: 'center' })`);
  await wait(250);

  const initInfo = await cdp.evalExpr(`(() => {
    const err = document.getElementById('runtimeErrorBanner')?.textContent || '';
    const canvas = document.getElementById('inspectorCanvas').getBoundingClientRect();
    const bgOpts = Array.from(document.getElementById('selBg').options).map(o => o.value);
    return {
      err,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      rect: { x: canvas.left + window.scrollX, y: canvas.top + window.scrollY, width: canvas.width, height: canvas.height },
      bgOpts
    };
  })()`);
  assert.equal(initInfo.err, '', 'Runtime error banner must be empty');
  console.error('[cdp-debug] initInfo:', JSON.stringify(initInfo));

  const inspectorClip = {
    x: Math.max(0, Math.floor(initInfo.rect.x)),
    y: Math.max(0, Math.floor(initInfo.rect.y)),
    width: Math.ceil(initInfo.rect.width),
    height: Math.ceil(initInfo.rect.height),
  };

  for (const bg of ['dark', 'light', 'checker']) {
    await cdp.evalExpr(`(() => new Promise(resolve => {
      const sel = document.getElementById('selBg');
      sel.value = '${bg}';
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      requestAnimationFrame(() => requestAnimationFrame(resolve));
    }))()`);
    await wait(120);
    await cdp.screenshot(`browser-turn-front-${bg}.png`, inspectorClip);
  }
  await cdp.screenshot('browser-turn-front-fullpage.png');

  // Also capture turn_00 (+65 deg right) & turn_04 (-65 deg left) on dark
  for (const [fIdx, fname] of [[0, 'browser-turn-00-dark.png'], [4, 'browser-turn-04-dark.png']]) {
    await cdp.send('Page.navigate', { url: `${BASE_URL}/?character=t_rex&clip=turn&frame=${fIdx}&paused=1` });
    for (let i = 0; i < 40; i++) {
      const ready = await cdp.evalExpr(`(() => {
        const c = document.getElementById('inspectorCanvas');
        if (!c) return false;
        const d = c.getContext('2d').getImageData(Math.floor(c.width/2)-40, Math.floor(c.height/2)-40, 80, 80).data;
        const baseR = d[0], baseG = d[1], baseB = d[2];
        let diff = 0;
        for (let p = 0; p < d.length; p += 4) {
          if (Math.abs(d[p]-baseR) + Math.abs(d[p+1]-baseG) + Math.abs(d[p+2]-baseB) > 25) diff++;
        }
        return diff > 50;
      })()`);
      if (ready) break;
      await wait(150);
    }
    await cdp.evalExpr(`(() => new Promise(resolve => {
      document.getElementById('inspectorCanvas').scrollIntoView({ block: 'center' });
      const sel = document.getElementById('selBg');
      sel.value = 'dark';
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      requestAnimationFrame(() => requestAnimationFrame(resolve));
    }))()`);
    await wait(150);
    const r = await cdp.evalExpr(`(() => { const c = document.getElementById('inspectorCanvas').getBoundingClientRect(); return { x: Math.max(0, Math.floor(c.left + window.scrollX)), y: Math.max(0, Math.floor(c.top + window.scrollY)), width: Math.ceil(c.width), height: Math.ceil(c.height) }; })()`);
    await cdp.screenshot(fname, { ...r });
  }

  // 2) Switch to Tab 3 Arena and inspect R->L turn, L->R turn, and patrol motion live
  await cdp.evalExpr(`document.querySelector('.tab-btn[data-tab="tab-arena"]').click()`);
  await wait(300);
  const arenaRect = await cdp.evalExpr(`(() => { const c = document.getElementById('arenaCanvas').getBoundingClientRect(); return { x: Math.floor(c.left), y: Math.floor(c.top), width: Math.ceil(c.width), height: Math.ceil(c.height) }; })()`);

  // Trigger manual move Left via real keydown/keyup ('KeyA') so turn plays R->L
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyDown', code: 'KeyA', key: 'a', windowsVirtualKeyCode: 65 });
  await wait(160); // right near dead-front mid-turn!
  await cdp.screenshot('browser-arena-r2l-turn.png', arenaRect);
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', code: 'KeyA', key: 'a', windowsVirtualKeyCode: 65 });
  await wait(450);

  // Now T-rex faces left (-X); press KeyD to trigger L->R turn!
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyDown', code: 'KeyD', key: 'd', windowsVirtualKeyCode: 68 });
  await wait(160);
  await cdp.screenshot('browser-arena-l2r-turn.png', arenaRect);
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', code: 'KeyD', key: 'd', windowsVirtualKeyCode: 68 });
  await wait(400);

  // Toggle Two-Endpoint Patrol live!
  await cdp.evalExpr(`document.getElementById('btnPatrol').click()`);
  await wait(350);
  await cdp.screenshot('browser-arena-patrol.png', arenaRect);
  const patrolActive = await cdp.evalExpr(`document.getElementById('btnPatrol').textContent`);
  await cdp.evalExpr(`document.getElementById('btnPatrol').click()`);

  const finalErr = await cdp.evalExpr(`document.getElementById('runtimeErrorBanner')?.textContent || ''`);
  assert.equal(finalErr, '', 'Final runtimeErrorBanner must be empty');
  assert.deepEqual(cdp.consoleErrors, [], `Console errors: ${cdp.consoleErrors}`);
  assert.deepEqual(cdp.exceptions, [], `JS exceptions: ${cdp.exceptions}`);
  assert.deepEqual(cdp.failedRequests, [], `Failed HTTP requests: ${cdp.failedRequests}`);

  const summary = {
    url: `${BASE_URL}/?character=t_rex&clip=turn&frame=2&paused=1`,
    runtimeErrorBanner: finalErr,
    patrolButtonAfterStart: patrolActive,
    consoleErrors: cdp.consoleErrors,
    exceptions: cdp.exceptions,
    failedRequests: cdp.failedRequests,
    screenshots: [
      'browser-turn-front-dark.png',
      'browser-turn-front-light.png',
      'browser-turn-front-checker.png',
      'browser-turn-00-dark.png',
      'browser-turn-04-dark.png',
      'browser-arena-r2l-turn.png',
      'browser-arena-l2r-turn.png',
      'browser-arena-patrol.png',
    ],
  };
  fs.writeFileSync(path.join(VERIF_DIR, 'browser-turn-live.json'), JSON.stringify(summary, null, 2) + '\n');
  console.log(JSON.stringify(summary, null, 2));
  cdp.close();
} finally {
  chrome.kill('SIGKILL');
  fs.rmSync(userDataDir, { recursive: true, force: true });
}
