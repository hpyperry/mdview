#!/usr/bin/env node
// Performance budget for non-Markdown source pages.
//
// The regression this guards against: a 1 MB .txt source page used to take
// ~42 s because highlight.js auto-detected the language for the whole file.
// Large source pages are now virtualized (server fallback + client windowing).
//
// Usage: node tests/perf-source.mjs

import { spawn, spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = dirname(HERE);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ];
  for (const path of candidates) if (existsSync(path)) return path;
  for (const name of ['google-chrome', 'chromium', 'chromium-browser']) {
    const found = spawnSync('which', [name], { encoding: 'utf8' });
    if (found.status === 0) return found.stdout.trim();
  }
  return null;
}

function findBinary() {
  if (process.env.MDVIEW_BIN) return process.env.MDVIEW_BIN;
  const release = join(REPO, 'target/release/mdview');
  const built = spawnSync('cargo', ['build', '--release', '--quiet'], {
    cwd: REPO,
    stdio: 'inherit',
  });
  if (built.status !== 0) throw new Error('cargo build --release failed');
  return release;
}

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

async function waitHttp(url, timeoutMs = 8000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url)).ok) return true;
    } catch {
      // starting
    }
    await sleep(100);
  }
  return false;
}

class CDP {
  constructor(url) {
    this.url = url;
    this.nextId = 1;
    this.pending = new Map();
  }

  static async connect(url) {
    const cdp = new CDP(url);
    cdp.ws = new WebSocket(url);
    await new Promise((resolve, reject) => {
      cdp.ws.addEventListener('open', resolve, { once: true });
      cdp.ws.addEventListener('error', reject, { once: true });
    });
    cdp.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !cdp.pending.has(message.id)) return;
      const { resolve, reject } = cdp.pending.get(message.id);
      cdp.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    });
    return cdp;
  }

  send(method, params = {}, sessionId) {
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify(payload));
    });
  }

  close() {
    try { this.ws.close(); } catch { /* closed */ }
  }
}

function launchChrome(chrome, profile) {
  const child = spawn(
    chrome,
    [
      '--headless',
      '--no-sandbox',
      '--disable-gpu',
      '--remote-debugging-port=0',
      `--user-data-dir=${profile}`,
      'about:blank',
    ],
    { stdio: ['ignore', 'ignore', 'pipe'] },
  );
  const wsUrl = new Promise((resolve, reject) => {
    let buffer = '';
    const timer = setTimeout(() => reject(new Error(buffer)), 15000);
    child.stderr.on('data', (chunk) => {
      buffer += chunk.toString();
      const match = buffer.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
  });
  return { child, wsUrl };
}

async function main() {
  const chrome = findChrome();
  if (!chrome) {
    console.error('Chrome/Chromium not found; set CHROME=...');
    process.exit(2);
  }
  const binary = findBinary();
  const tmp = await mkdtemp(join(tmpdir(), 'mdview-perf-'));
  const root = join(tmp, 'root');
  const profile = join(tmp, 'chrome');
  await mkdir(root, { recursive: true });
  const line = 'the quick brown fox jumps over the lazy dog 0123456789\n';
  const oneMb = line.repeat(Math.ceil(1048576 / line.length)).slice(0, 1048576);
  const tenMb = line.repeat(Math.ceil(10485760 / line.length)).slice(0, 10485760);
  const rsLine = 'fn main() { let x = 1; println!("hello"); }\n';
  const rsMb = rsLine.repeat(Math.ceil(1048576 / rsLine.length)).slice(0, 1048576);
  await writeFile(join(root, 'small.txt'), line.repeat(2000));
  await writeFile(join(root, 'big-1m.txt'), oneMb);
  await writeFile(join(root, 'big-10m.txt'), tenMb);
  await writeFile(join(root, 'big-1m.rs'), rsMb);

  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const server = spawn(
    binary,
    ['--root', root, '--host', '127.0.0.1', '--port', String(port), '--port-tries', '0', '--trust'],
    { stdio: ['ignore', 'ignore', 'pipe'] },
  );
  const { child: chromeChild, wsUrl } = launchChrome(chrome, profile);
  let browser;
  let failed = 0;
  try {
    if (!(await waitHttp(`${base}/`))) throw new Error('server did not start');
    browser = await CDP.connect(await wsUrl);
    const { targetId } = await browser.send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await browser.send('Target.attachToTarget', { targetId, flatten: true });
    const page = (method, params) => browser.send(method, params, sessionId);
    await page('Page.enable');
    await page('Runtime.enable');
    await page('Emulation.setDeviceMetricsOverride', {
      width: 1280, height: 900, deviceScaleFactor: 1, mobile: false,
    });
    const evaluate = async (expression) => {
      const result = await page('Runtime.evaluate', {
        expression, returnByValue: true, awaitPromise: true,
      });
      if (result.exceptionDetails) throw new Error('evaluate failed');
      return result.result.value;
    };

    const cases = [
      { path: '/small.txt', selector: 'pre code', budget: 1500, label: '100 KB text' },
      { path: '/big-1m.txt', selector: '.vs-scroll .vs-row', budget: 1500, label: '1 MB text' },
      { path: '/big-10m.txt', selector: '.vs-scroll .vs-row', budget: 3000, label: '10 MB text' },
      { path: '/big-1m.rs', selector: '.vs-scroll .vs-row', budget: 1500, label: '1 MB Rust' },
    ];
    for (const item of cases) {
      const started = Date.now();
      await page('Page.navigate', { url: base + item.path });
      let ready = false;
      while (Date.now() - started < 15000) {
        if (await evaluate(
          `document.readyState === 'complete' && document.querySelector(${JSON.stringify(item.selector)}) !== null`,
        ).catch(() => false)) {
          ready = true;
          break;
        }
        await sleep(50);
      }
      const elapsed = Date.now() - started;
      const ok = ready && elapsed <= item.budget;
      if (!ok) failed += 1;
      console.log(
        `  ${ok ? '\x1b[32mok\x1b[0m  ' : '\x1b[31mFAIL\x1b[0m'} ${item.label}: ${elapsed} ms (budget ${item.budget} ms)`,
      );
    }
  } finally {
    try { await browser?.send('Browser.close'); } catch { /* closing */ }
    browser?.close();
    chromeChild.kill('SIGKILL');
    server.kill('SIGKILL');
    await sleep(200);
    await rm(tmp, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 }).catch(() => {});
  }

  if (failed > 0) process.exit(1);
  console.log('\nperformance budgets passed');
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(2);
});
