#!/usr/bin/env node
// Browser-level acceptance probe (P3-7).
//
// Exercises the behaviour that unit tests cannot see: highlight.js runs,
// copy/zoom/top buttons are injected, focus is restored, the no-JS baseline
// has no dead controls, and the page makes no external requests.
//
// Usage:
//   node tests/browser-probe.mjs
//   MDVIEW_BIN=target/release/mdview CHROME=... node tests/browser-probe.mjs
//
// Requires Node 22 (global WebSocket/fetch) and a Chrome/Chromium binary.

import { spawn, spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = dirname(HERE);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let pass = 0;
let fail = 0;
function check(name, ok, detail = '') {
  if (ok) {
    pass += 1;
    console.log(`  \x1b[32mok\x1b[0m   ${name}`);
  } else {
    fail += 1;
    console.log(`  \x1b[31mFAIL\x1b[0m ${name}${detail ? ` (${detail})` : ''}`);
  }
}

function findChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
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
  const exe = process.platform === 'win32' ? '.exe' : '';
  const debug = join(REPO, `target/debug/mdview${exe}`);
  if (existsSync(debug)) return debug;
  const release = join(REPO, `target/release/mdview${exe}`);
  if (existsSync(release)) return release;
  const built = spawnSync('cargo', ['build', '--quiet'], { cwd: REPO, stdio: 'inherit' });
  if (built.status !== 0) throw new Error('cargo build failed');
  return debug;
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
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      // server still starting
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
    this.listeners = new Map();
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
      if (message.id && cdp.pending.has(message.id)) {
        const { resolve, reject } = cdp.pending.get(message.id);
        cdp.pending.delete(message.id);
        if (message.error) reject(new Error(`${message.error.message} (${message.error.code})`));
        else resolve(message.result);
        return;
      }
      const handler = cdp.listeners.get(message.method);
      if (handler) handler(message.params, message.sessionId);
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

  on(method, handler) {
    this.listeners.set(method, handler);
  }

  close() {
    try { this.ws.close(); } catch { /* already closed */ }
  }
}

function launchChrome(chrome, profile) {
  const args = [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--no-first-run',
    '--no-default-browser-check',
    '--remote-debugging-port=0',
    `--user-data-dir=${profile}`,
    'about:blank',
  ];
  const child = spawn(chrome, args, { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = new Promise((resolve, reject) => {
    let buffer = '';
    const timer = setTimeout(() => reject(new Error(`Chrome did not expose DevTools:\n${buffer}`)), 30000);
    child.stderr.on('data', (chunk) => {
      buffer += chunk.toString();
      const match = buffer.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
    child.once('exit', (code) => {
      clearTimeout(timer);
      reject(new Error(`Chrome exited early (${code}):\n${buffer}`));
    });
  });
  return { child, wsUrl };
}

const PNG_1X1 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

async function writeFixture(root) {
  await mkdir(join(root, 'sub'), { recursive: true });
  const image = Buffer.from(PNG_1X1, 'base64');
  await writeFile(join(root, 'img.png'), image);
  await writeFile(join(root, 'sub', 'img.png'), image);
  const filler = Array.from({ length: 120 }, (_, i) => `第 ${i + 1} 段，用来把页面撑到可滚动。`).join('\n\n');
  await writeFile(
    join(root, 'page.md'),
    `# Probe\n\n中文 **粗体**。\n\n## Section A\n\n\`\`\`python\ndef f():\n    return 1\n\`\`\`\n\n\`\`\`\nplain fence text\n\`\`\`\n\n### Sub\n\n![图](img.png)\n\n[目录](/)\n\n## Section B\n\n末尾段落。\n\n${filler}\n`,
  );
  await writeFile(join(root, 'sub', 'page.md'), '# Sub\n\n[上级](/) · ![图](img.png)\n');
  await writeFile(
    join(root, 'page.html'),
    '<!doctype html><html><head><meta charset="utf-8"><title>HTML Probe</title><link rel="stylesheet" href="probe.css"></head><body><h1>HTML Probe</h1><p>htmlneedle</p><script>document.body.dataset.script="yes"</script></body></html>\n',
  );
  await writeFile(join(root, 'probe.css'), 'body { background-color: rgb(1, 2, 3); }\n');
  await writeFile(
    join(root, 'evil.svg'),
    '<svg xmlns="http://www.w3.org/2000/svg"><script>document.documentElement.dataset.x=1</script></svg>\n',
  );
  await writeFile(join(root, 'plain.txt'), 'plain text without a language\nsecond line\n');
  await writeFile(join(root, 'small.rs'), 'fn main() {\n    let x = 1;\n    println!("{}", x);\n}\n');
  await writeFile(join(root, 'single.md'), '# Single\n\nOnly a heading.\n');
  await writeFile(join(root, 'huge-code.md'), `# Huge\n\n\`\`\`js\n${'const x = 1;\n'.repeat(22000)}\`\`\`\n`);
  const bigLines = Array.from({ length: 15000 }, (_, i) => `line ${i + 1} the quick brown fox jumps over the lazy dog`).join('\n') + '\n';
  await writeFile(join(root, 'big.txt'), bigLines);
  const bigRust = Array.from({ length: 12000 }, (_, i) => `fn f${i + 1}() { let x = ${i + 1}; println!("hello"); }`).join('\n') + '\n';
  await writeFile(join(root, 'big.rs'), bigRust);
  const wideText = `${'wide-line-'.repeat(450)}\n${Array.from({ length: 12000 }, (_, i) => `row ${i + 1} ${'x'.repeat(30)}`).join('\n')}\n`;
  await writeFile(join(root, 'wide.txt'), wideText);
  for (let i = 0; i < 40; i += 1) {
    await writeFile(join(root, 'sub', `f${String(i).padStart(2, '0')}.md`), `# ${i}\n`);
  }
}

async function main() {
  const chrome = findChrome();
  if (!chrome) {
    console.error('Chrome/Chromium not found; set CHROME=...');
    process.exit(2);
  }
  const binary = findBinary();
  const version = spawnSync(chrome, ['--version'], { encoding: 'utf8' }).stdout.trim();
  console.log(`Chrome: ${version || chrome}`);
  const tmp = await mkdtemp(join(tmpdir(), 'mdview-browser-'));
  const root = join(tmp, 'root');
  const profile = join(tmp, 'chrome');
  await mkdir(root, { recursive: true });
  await writeFixture(root);

  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const server = spawn(
    binary,
    ['--root', root, '--host', '127.0.0.1', '--port', String(port), '--port-tries', '0', '--trust'],
    { stdio: ['ignore', 'ignore', 'pipe'] },
  );
  let serverErr = '';
  server.stderr.on('data', (chunk) => { serverErr += chunk.toString(); });

  const untrustedPort = await freePort();
  const untrustedBase = `http://127.0.0.1:${untrustedPort}`;
  const untrustedServer = spawn(
    binary,
    ['--root', root, '--host', '127.0.0.1', '--port', String(untrustedPort), '--port-tries', '0', '--untrusted'],
    { stdio: ['ignore', 'ignore', 'pipe'] },
  );
  let untrustedErr = '';
  untrustedServer.stderr.on('data', (chunk) => { untrustedErr += chunk.toString(); });

  const { child: chromeChild, wsUrl } = launchChrome(chrome, profile);
  let browser;
  try {
    if (!(await waitHttp(`${base}/`))) {
      throw new Error(`server did not start: ${serverErr}`);
    }
    if (!(await waitHttp(`${untrustedBase}/`))) {
      throw new Error(`untrusted server did not start: ${untrustedErr}`);
    }
    browser = await CDP.connect(await wsUrl);
    const { targetId } = await browser.send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await browser.send('Target.attachToTarget', { targetId, flatten: true });
    const page = {
      send: (method, params = {}) => browser.send(method, params, sessionId),
    };
    const requests = [];
    browser.on('Network.requestWillBeSent', (params, sid) => {
      if (sid === sessionId) requests.push(params.request.url);
    });
    await page.send('Page.enable');
    await page.send('Runtime.enable');
    await page.send('Network.enable');
    await page.send('Page.bringToFront');
    await page.send('Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {});
    await page.send('Page.setWebLifecycleState', { state: 'active' }).catch(() => {});
    await page.send('Emulation.setDeviceMetricsOverride', {
      width: 1200, height: 320, deviceScaleFactor: 1, mobile: false,
    });
    try {
      await browser.send('Browser.grantPermissions', {
        origin: base,
        permissions: ['clipboardReadWrite', 'clipboardSanitizedWrite'],
      });
    } catch (err) {
      console.log(`  (warn) clipboard permission: ${err.message}`);
    }

    const evaluate = async (expression) => {
      const result = await page.send('Runtime.evaluate', {
        expression,
        returnByValue: true,
        awaitPromise: true,
        userGesture: true,
      });
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.exception?.description || 'evaluate failed');
      }
      return result.result.value;
    };
    const crumbsComplete = (selector, needle) => evaluate(`(() => {
      const crumbs = document.querySelector(${JSON.stringify(selector)});
      if (!crumbs) return false;
      const root = Array.from(crumbs.querySelectorAll('a')).find((a) => a.getAttribute('href') === '/');
      return Boolean(root) && crumbs.textContent.includes(${JSON.stringify(needle)});
    })()`);
    const goto = async (path) => {
      requests.length = 0;
      await page.send('Page.navigate', { url: `${base}${path}` });
      const deadline = Date.now() + 8000;
      while (Date.now() < deadline) {
        if ((await evaluate('document.readyState')) === 'complete') break;
        await sleep(50);
      }
      await sleep(500);
    };
    const waitFor = async (expression, timeoutMs = 3000) => {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        if (await evaluate(expression)) return true;
        await sleep(50);
      }
      return false;
    };

    console.log('== preview page ==');
    await goto('/page.md');
    check('标题渲染', (await evaluate('document.querySelector("article.markdown-body h1").textContent')) === 'Probe');
    check('文档面包屑完整', await crumbsComplete('.doc-head .crumbs', 'page.md'));
    check('文档岛已按需水合', await waitFor('["toc", "linetarget", "code", "zoom"].every((name) => window.__mdviewIslands?.mounted.includes(name))', 3000));
    check('渲染页带行定位数据', (await evaluate('document.querySelectorAll(".markdown-body [data-sourcepos]").length')) > 0);
    check(
      '文档页头铺满内容面',
      (await evaluate(`(() => {
        const card = document.querySelector('.content-card').getBoundingClientRect();
        const crumbs = document.querySelector('.doc-head .crumbs').getBoundingClientRect();
        const pad = getComputedStyle(document.querySelector('.doc-head .head-inner')).paddingLeft;
        return pad === '30px' && Math.round(crumbs.x - card.x) <= 32;
      })()`)) === true,
    );
    check('代码块数量', (await evaluate('document.querySelectorAll("pre code").length')) === 2);
    check('highlight.js 着色', await waitFor('document.querySelectorAll("pre code.hljs span").length > 0', 3000));
    check('复制按钮已注入', (await evaluate('document.querySelectorAll(".copy-btn").length')) === 2);
    check('代码块语言条', (await evaluate('document.querySelector(".code-block .code-bar .lang")?.textContent')) === 'python');
    check('无语言围栏不高亮', (await evaluate('[...document.querySelectorAll(".code-block")].some(b => b.querySelector(".lang")?.textContent === "代码" && !b.querySelector("code.hljs"))')) === true);
    check('页内目录已生成', (await evaluate('document.querySelectorAll("#toc-slot .toc-link").length')) === 3);
    check('导航默认关闭', (await evaluate('document.documentElement.dataset.navOpen === undefined && getComputedStyle(document.getElementById("nav-panel")).display === "none"')) === true);
    check('导航树未预渲染', (await evaluate('document.querySelectorAll("#nav-panel .nav-file").length')) === 0);
    check(
      '导航空闲预取完成',
      await waitFor('performance.getEntriesByType("resource").some((entry) => entry.name.endsWith("/_nav") && entry.responseEnd > 0)', 3000),
    );
    check('导航预取后仍关闭', (await evaluate('getComputedStyle(document.getElementById("nav-panel")).display')) === 'none');
    check('无外部资源请求', requests.every((url) => url.startsWith(base) || url.startsWith('data:')), requests.join(', '));

    await evaluate('document.querySelector(".copy-btn").click()');
    await sleep(300);
    const copyText = await evaluate('document.querySelector(".copy-btn").textContent');
    check('复制按钮反馈', copyText === '已复制', copyText);
    const clipboard = await evaluate('navigator.clipboard.readText()').catch(() => '');
    check('剪贴板内容', clipboard.includes('def f():'), JSON.stringify(clipboard.slice(0, 40)));

    const zoom = await evaluate(`(() => {
      const a = document.querySelector('a.zoom');
      if (!a) return null;
      const img = a.querySelector('img');
      return { href: a.getAttribute('href'), src: img.getAttribute('src'), alt: img.alt };
    })()`);
    check('图片包裹存在', !!zoom, 'a.zoom missing');
    if (!zoom) throw new Error('fixture is missing a.zoom');
    check('href 与 src 相同', zoom.href === zoom.src, JSON.stringify(zoom));
    check('图片放大岛已水合', await waitFor('window.__mdviewIslands?.mounted.includes("zoom")', 3000));

    const modifierPrevented = await evaluate(`(() => {
      const a = document.querySelector('a.zoom');
      let preventedByApp = null;
      const guard = (event) => {
        preventedByApp = event.defaultPrevented;
        event.preventDefault();           // stop the synthetic click from navigating
        a.removeEventListener('click', guard);
      };
      a.addEventListener('click', guard);
      a.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ctrlKey: true }));
      return preventedByApp === false;
    })()`);
    check('修饰键点击不拦截', modifierPrevented === true);
    check('修饰键不打开遮罩', (await evaluate('document.querySelector("dialog.zoomdlg")?.open !== true')) === true);

    await evaluate(`document.querySelector('a.zoom').dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }))`);
    check('遮罩打开', await waitFor('document.querySelector("dialog.zoomdlg")?.open === true', 2000));
    check('遮罩使用 modal', (await evaluate('document.querySelector("dialog.zoomdlg")?.matches(":modal")')) === true);
    check('遮罩图片地址正确', (await evaluate('document.querySelector("dialog.zoomdlg img")?.getAttribute("src")')) === zoom.href);
    check('遮罩焦点在 dialog', await waitFor('document.activeElement === document.querySelector("dialog.zoomdlg")', 2000));
    await evaluate('document.querySelector(".zoom-close").click()');
    check('关闭按钮生效', await waitFor('document.querySelector("dialog.zoomdlg")?.open === false', 2000));
    check('焦点归还图片链接', await waitFor('document.activeElement === document.querySelector("a.zoom")', 2000));

    console.log('== theme ==');
    await evaluate('document.getElementById("theme-toggle").click()');
    check('主题切到浅色', (await evaluate('document.documentElement.dataset.themeMode')) === 'light');
    check('主题状态反馈', await waitFor('document.getElementById("theme-status")?.classList.contains("is-visible") && document.getElementById("theme-status").textContent === "主题：浅色"', 1000));
    await evaluate('document.getElementById("theme-toggle").click()');
    check('主题切到深色', (await evaluate('document.documentElement.dataset.themeMode')) === 'dark');
    await evaluate('document.getElementById("theme-toggle").click()');
    check('主题回到系统', (await evaluate('document.documentElement.dataset.themeMode')) === 'system');
    const rapidModes = await evaluate(`(() => {
      const button = document.getElementById('theme-toggle');
      const out = [];
      for (let i = 0; i < 6; i += 1) {
        button.click();
        out.push(document.documentElement.dataset.themeMode);
      }
      return out;
    })()`);
    check('主题快速连点循环', JSON.stringify(rapidModes) === JSON.stringify(['light', 'dark', 'system', 'light', 'dark', 'system']), JSON.stringify(rapidModes));
    const resilientModes = await evaluate(`(() => {
      const original = Storage.prototype.setItem;
      Storage.prototype.setItem = () => { throw new Error('blocked'); };
      const button = document.getElementById('theme-toggle');
      const out = [];
      button.click();
      out.push(document.documentElement.dataset.themeMode);
      button.click();
      out.push(document.documentElement.dataset.themeMode);
      Storage.prototype.setItem = original;
      return out;
    })()`);
    check('主题写入失败仍前进', JSON.stringify(resilientModes) === JSON.stringify(['light', 'dark']), JSON.stringify(resilientModes));
    await evaluate('document.getElementById("theme-toggle").click()');
    check('主题恢复系统', (await evaluate('document.documentElement.dataset.themeMode')) === 'system');
    const beforeNavWidth = await evaluate('document.querySelector(".doc-card").getBoundingClientRect().width');
    await evaluate('document.getElementById("nav-toggle").click()');
    check('导航打开', await waitFor('document.documentElement.dataset.navOpen === "1" && getComputedStyle(document.getElementById("nav-panel")).display !== "none"', 2000));
    check('导航不挤压正文', Math.abs((await evaluate('document.querySelector(".doc-card").getBoundingClientRect().width')) - beforeNavWidth) < 1);
    await evaluate('document.getElementById("nav-close").click()');
    check('导航关闭', await waitFor('document.documentElement.dataset.navOpen === "0"', 2000));
    await page.send('Emulation.setDeviceMetricsOverride', { width: 800, height: 600, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    await evaluate('document.getElementById("nav-toggle").click()');
    check('移动端导航抽屉', await waitFor('document.documentElement.dataset.navOpen === "1" && getComputedStyle(document.getElementById("nav-panel")).display !== "none"', 2000));
    check('移动端导航遮罩', (await evaluate('getComputedStyle(document.getElementById("nav-scrim")).display')) === 'block');
    await evaluate('document.getElementById("nav-scrim").click()');
    check('移动端遮罩关闭导航', await waitFor('document.documentElement.dataset.navOpen === "0"', 2000));
    await page.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    await goto('/page.md');
    check('390 无横向溢出', (await evaluate('document.documentElement.scrollWidth <= innerWidth + 1')) === true);

    console.log('== three columns ==');
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    check('正文与 TOC 两列', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 2);
    check('1440 无横向溢出', (await evaluate('document.documentElement.scrollWidth <= innerWidth + 1')) === true);
    check('TOC 细轨可见', (await evaluate('getComputedStyle(document.querySelector(".toc-rail")).display')) !== 'none');
    check('正文面使用宽布局', (await evaluate('Math.round(document.querySelector(".doc-card").getBoundingClientRect().width)')) >= 1000);
    check('TOC 当前项', await waitFor('!!document.querySelector(".toc-tick.is-active")', 3000));
    check('TOC 面板初始关闭', (await evaluate('document.querySelector(".toc-pop") === null')) === true);
    await evaluate('document.getElementById("toc-rail").dispatchEvent(new PointerEvent("pointerenter"))');
    check('TOC 悬停展开文字大纲', await waitFor('document.querySelectorAll(".toc-pop .toc-link").length === 3', 2000));
    check('TOC 大纲标题可读', (await evaluate('document.querySelector(".toc-pop .toc-link")?.textContent')) === 'Section A');
    await evaluate('document.getElementById("toc-rail").dispatchEvent(new PointerEvent("pointerleave"))');
    check('TOC 移出收起', await waitFor('document.querySelector(".toc-pop") === null', 2000));
    await evaluate('document.querySelector(".toc-rail-btn").click()');
    check('TOC 可固定', await waitFor('document.querySelector(".toc-pop") !== null', 2000));
    await evaluate('document.getElementById("toc-rail").dispatchEvent(new PointerEvent("pointerleave"))');
    await sleep(250);
    check('TOC 固定后移出不收起', (await evaluate('document.querySelector(".toc-pop") !== null')) === true);
    await evaluate('document.querySelector(".toc-close").click()');
    check('TOC 固定可关闭', await waitFor('document.querySelector(".toc-pop") === null', 2000));
    await evaluate('document.getElementById("toc-rail").querySelector(".toc-rail-btn").click()');
    check('TOC 面板可展开', await waitFor('document.querySelectorAll(".toc-pop .toc-link").length === 3', 2000));
    await evaluate('document.getElementById("toc-3").scrollIntoView({ block: "start" })');
    check('TOC 定位到 Section B', await waitFor('document.getElementById("toc-3").getBoundingClientRect().top < 120', 3000));
    await evaluate('window.dispatchEvent(new Event("scroll")); window.dispatchEvent(new Event("resize"))');
    const tocActive = await waitFor('document.querySelector(".toc-tick.is-active")?.getAttribute("data-target") === "toc-3"', 3000);
    check(
      'TOC 跟随滚动',
      tocActive,
      await evaluate('JSON.stringify({ y: window.scrollY, active: document.querySelector(".toc-tick.is-active")?.getAttribute("data-target"), top: document.getElementById("toc-3").getBoundingClientRect().top })'),
    );
    await evaluate('document.querySelector(".toc-close").click()');
    check('TOC 面板可收起', await waitFor('document.querySelector(".toc-pop") === null', 2000));
    await evaluate('document.querySelector(".toc-rail-btn").click()');
    await waitFor('document.querySelector(".toc-pop") !== null', 2000);
    await evaluate('document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))');
    check('TOC Esc 关闭', await waitFor('document.querySelector(".toc-pop") === null', 2000));
    await evaluate('document.querySelector(".toc-rail-btn").click()');
    await waitFor('document.querySelector(".toc-pop") !== null', 2000);
    await evaluate('document.querySelector(".doc-prose p").click()');
    check('TOC 点外部关闭', await waitFor('document.querySelector(".toc-pop") === null', 2000));
    await goto('/page.md');
    const articleWidth = await evaluate('document.querySelector(".doc-card").getBoundingClientRect().width');
    check('导航默认关闭', (await evaluate('document.documentElement.dataset.navOpen === undefined && getComputedStyle(document.getElementById("nav-panel")).display === "none"')) === true);
    await evaluate('document.getElementById("nav-toggle").click()');
    check('导航树加载完成', await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000));
    check('导航浮层不挤压正文', Math.abs((await evaluate('document.querySelector(".doc-card").getBoundingClientRect().width')) - articleWidth) < 1);
    check('导航浮岛位置', (await evaluate('Math.round(document.getElementById("nav-panel").getBoundingClientRect().top)')) === 84);
    await evaluate('document.querySelector(".doc-prose p").click()');
    check('导航点外部关闭', await waitFor('document.documentElement.dataset.navOpen !== "1"', 2000));
    await evaluate('document.getElementById("nav-toggle").click()');
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    await evaluate('document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))');
    check('导航 Esc 关闭', await waitFor('document.documentElement.dataset.navOpen !== "1"', 2000));
    await evaluate('document.getElementById("nav-toggle").click()');
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    check('导航包含所有文件', await evaluate(`!!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/img.png')`));
    check('导航无分组文字', (await evaluate('(() => { const t = document.querySelector("#nav-panel .nav-tree").textContent; return !t.includes("文件") && !t.includes("目录"); })()')) === true);
    check('导航当前文件高亮', (await evaluate('document.querySelector("#nav-panel .nav-file.is-active")?.textContent')) === 'page.md');
    await evaluate('(() => { const row = [...document.querySelectorAll("#nav-panel .nav-dir > .nav-row")].find((b) => b.textContent.includes("sub")); row.click(); })()');
    check('目录行只展开', await waitFor('(() => { const row = [...document.querySelectorAll("#nav-panel .nav-dir > .nav-row")].find((b) => b.textContent.includes("sub")); return row?.getAttribute("aria-expanded") === "true" && document.body.dataset.currentPath === "page.md"; })()', 2000));
    check('目录展开显示文件', await evaluate(`!!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/sub/page.md')`));
    await evaluate('document.getElementById("nav-close").click()');
    await goto('/page.md');
    await evaluate('document.getElementById("nav-toggle").click()');
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    check('展开状态记忆', await waitFor('(() => { const row = [...document.querySelectorAll("#nav-panel .nav-dir > .nav-row")].find((b) => b.textContent.includes("sub")); return row?.getAttribute("aria-expanded") === "true"; })()', 2000));
    await evaluate(`Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/sub/page.md').click()`);
    check('点击文件导航', await waitFor('document.body?.dataset.currentPath === "sub/page.md"', 5000));
    check('文件导航后导航收起', (await evaluate('document.documentElement.dataset.navOpen !== "1"')) === true);
    check('新页面导航空闲预取', await waitFor('performance.getEntriesByType("resource").some((entry) => entry.name.endsWith("/_nav") && entry.responseEnd > 0)', 3000));
    await evaluate('document.getElementById("nav-toggle").click()');
    check('新页面打开无加载中', (await evaluate('document.querySelector("#nav-panel .nav-status") === null')) === true);
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    check('当前路径自动展开', await waitFor('(() => { const row = [...document.querySelectorAll("#nav-panel .nav-dir > .nav-row")].find((b) => b.textContent.includes("sub")); return row?.getAttribute("aria-expanded") === "true" && document.querySelector("#nav-panel .nav-file.is-active")?.textContent === "page.md"; })()', 2000));
    await goto('/single.md');
    check('无标题时不显示 TOC' , await waitFor('document.getElementById("toc-rail")?.hidden === true && document.getElementById("toc-slot")?.hidden === true', 2000));
    check('无标题时正文单列', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 1);
    await goto('/page.md');
    await evaluate('window.scrollTo(0, 500)');
    await sleep(250);
    check('顶栏 sticky', (await evaluate('Math.round(document.querySelector(".topbar").getBoundingClientRect().top)')) === 12);
    check('TOC 细轨 sticky', (await evaluate('Math.round(document.querySelector(".toc-rail").getBoundingClientRect().top)')) === 84);
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 320, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    check('1200 单列', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 1);
    check('1200 细轨隐藏', (await evaluate('getComputedStyle(document.querySelector(".toc-rail")).display')) === 'none');
    check('1200 内联目录', (await evaluate('getComputedStyle(document.querySelector(".toc-inline")).display')) !== 'none');
    check('1200 无横向溢出', (await evaluate('document.documentElement.scrollWidth <= innerWidth + 1')) === true);

    console.log('== chunked source ==');
    await goto('/plain.txt');
    check('无语言源码不自动高亮', (await evaluate('document.querySelectorAll("pre code.hljs").length')) === 0);
    await goto('/small.rs');
    check('小源码按语言高亮', await waitFor('document.querySelectorAll(".source .code code.hljs span").length > 0', 3000));
    const chunkedStarted = Date.now();
    await goto('/big.txt');
    check('源码全文分块容器', (await evaluate('document.querySelectorAll(".source-chunked .source-chunk").length')) === 31);
    check('源码页只挂 source 岛', await waitFor('window.__mdviewIslands?.mounted.includes("source") && !window.__mdviewIslands.mounted.includes("toc")', 3000));
    check('源码末行在页面内', (await evaluate('document.querySelector(".source-chunked")?.textContent.includes("line 15000")')) === true);
    check('源码全文提示', (await evaluate('document.querySelector(".source-note")?.textContent.includes("15001 行") && document.querySelector(".source-note")?.textContent.includes("已加载完整内容")')) === true);
    check('源码提示无实现说明', (await evaluate('!document.querySelector(".source-note")?.textContent.includes("浏览器按可视区域")')) === true);
    check('源码分块按需绘制', (await evaluate('getComputedStyle(document.querySelector(".source-chunk")).contentVisibility')) === 'auto');
    check('源码分块加载 < 3000ms', Date.now() - chunkedStarted < 3000);
    await evaluate('window.scrollTo(0, document.body.scrollHeight)');
    check('源码滚动到末行', await waitFor('!!document.getElementById("L15001")', 3000));
    await goto('/big.txt#L12000');
    check('源码行锚点', await waitFor('!!document.querySelector(".source-chunk .gutter a.target")', 3000));
    check('源码行高亮', (await evaluate('!!document.querySelector(".source-target-line")')) === true);
    check('源码锚点滚动', (await evaluate('window.scrollY')) > 0);
    await goto('/wide.txt');
    check('源码长行横向滚动', await waitFor('document.querySelector(".source-wrap").scrollWidth > document.querySelector(".source-wrap").clientWidth + 100', 3000));
    await goto('/big.rs');
    check('大源码按块着色', await waitFor('document.querySelectorAll(".source-chunk code.hljs").length > 0', 3000));
    check('大源码着色有界', (await evaluate('document.querySelectorAll(".source-chunk code.hljs").length')) < 10);
    await goto('/huge-code.md');
    check('超大代码块标记未高亮', await waitFor('document.querySelector(".code-block .lang")?.textContent.includes("高亮已关闭")', 3000));
    check('超大代码块不着色', (await evaluate('document.querySelectorAll(".code-block code.hljs").length')) === 0);
    await goto('/page.md');

    console.log('== search ==');
    await goto('/page.md');
    check('搜索岛已水合', await waitFor('window.__mdviewIslands?.mounted.includes("search")', 3000));
    await evaluate('document.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true }))');
    check('搜索快捷键打开', await waitFor('document.getElementById("search-pop")?.hidden === false', 2000));
    await evaluate('document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))');
    check('搜索 Esc 关闭', await waitFor('document.getElementById("search-pop")?.hidden === true', 2000));
    await evaluate('document.getElementById("search-open").click()');
    check('搜索弹层打开', await waitFor('document.getElementById("search-pop")?.hidden === false', 2000));
    const searchHints = await evaluate('Array.from(document.querySelectorAll(".search-hint .kbd")).map((node) => node.textContent)');
    check('搜索键帽统一', searchHints.length === 2 && searchHints[0] === 'Enter' && searchHints[1] === 'Esc', JSON.stringify(searchHints));
    await evaluate('document.getElementById("search-input").focus()');
    await page.send('Input.insertText', { text: 'Probe' });
    await page.send('Input.dispatchKeyEvent', {
      type: 'keyDown', key: 'Enter', code: 'Enter', text: '\r', unmodifiedText: '\r',
      windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
    });
    await page.send('Input.dispatchKeyEvent', {
      type: 'keyUp', key: 'Enter', code: 'Enter',
      windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
    });
    check('搜索 Enter 提交', await waitFor('document.body?.dataset.page === "search"', 5000));
    check('搜索命中分组', (await evaluate('document.querySelectorAll(".result-group").length')) > 0);
    check('搜索词高亮', await waitFor('document.querySelectorAll(".hit-snippet mark").length > 0', 3000));
    check('搜索页有独立表单', (await evaluate('!!document.querySelector(".search-page-form input")')) === true);
    check('搜索页面包屑完整', await crumbsComplete('.search-head .crumbs', '搜索'));
    check('搜索摘要用结果计数', (await evaluate(`(() => {
      const text = document.querySelector('.search-head p')?.textContent || '';
      return text.includes('条结果') && !text.includes('命中') && !text.includes('实时扫描');
    })()`)) === true);
    check('搜索无命中字样', (await evaluate('!document.body.innerText.includes("命中")')) === true);
    check('搜索无文件名命中行', (await evaluate('!document.body.innerText.includes("文件名命中")')) === true);
    const groupHref = await evaluate(`document.querySelector('.result-group .result-head')?.getAttribute('href')`);
    check('文件标题整行链接', groupHref === '/page.md', groupHref);
    check('搜索结果无源码行入口', (await evaluate('!document.body.innerText.includes("源码 Ln")')) === true);
    check('搜索结果无打开文档', (await evaluate('!document.body.innerText.includes("打开文档")')) === true);
    check('搜索页 H1 无下划线', (await evaluate('getComputedStyle(document.querySelector(".search-head h1")).borderBottomWidth')) === '0px');
    const searchGeom = await evaluate(`(() => {
      const card = document.querySelector('.content-card').getBoundingClientRect();
      const title = document.querySelector('.search-head h1').getBoundingClientRect();
      const form = document.querySelector('.search-page-form').getBoundingClientRect();
      return { cardX: card.x, cardRight: card.right, titleX: title.x, formX: form.x, formRight: form.right };
    })()`);
    check('搜索页头铺满内容面', Math.round(searchGeom.titleX - searchGeom.cardX) <= 32, JSON.stringify(searchGeom));
    check('搜索页头表单在右侧', searchGeom.formX > searchGeom.titleX && searchGeom.formRight >= searchGeom.cardRight - 40, JSON.stringify(searchGeom));
    const docHit = await evaluate(`(() => {
      const link = document.querySelector('.result-group .hit[href*="#L"]');
      return link ? link.getAttribute('href') : null;
    })()`);
    check('Markdown 命中行是链接', /^\/page\.md#L\d+$/.test(docHit || ''), docHit);
    await goto(`/search?q=${encodeURIComponent('末尾段落')}`);
    const lateHit = await evaluate(`(() => {
      const link = document.querySelector('.result-group .hit[href*="#L"]');
      return link ? link.getAttribute('href') : null;
    })()`);
    check('Markdown 后段行链接', /^\/page\.md#L\d+$/.test(lateHit || ''), lateHit);
    await goto(lateHit || '/page.md');
    check('渲染页行定位高亮', await waitFor('!!document.querySelector(".line-target")', 2000));
    check('渲染页滚动到命中行', (await evaluate('window.scrollY')) > 0);
    await goto('/search?q=plain');
    const textHit = await evaluate(`(() => {
      const group = Array.from(document.querySelectorAll('.result-group')).find((node) => node.textContent.includes('plain.txt'));
      const link = group?.querySelector('.hit[href*="#L"]');
      return link ? { text: link.textContent, href: link.getAttribute('href') } : null;
    })()`);
    check('文本命中行可点击', /^\/plain\.txt#L\d+$/.test(textHit?.href || '') && !textHit?.text.includes('打开'), JSON.stringify(textHit));
    await page.send('Emulation.setDeviceMetricsOverride', { width: 800, height: 600, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    await evaluate('document.getElementById("search-open").click()');
    check('窄屏搜索直达搜索页', await waitFor('document.body?.dataset.page === "search"', 5000));
    check('窄屏搜索页头紧凑', (await evaluate(`(() => {
      const title = document.querySelector('.search-head h1').getBoundingClientRect();
      const form = document.querySelector('.search-page-form').getBoundingClientRect();
      return form.top - title.bottom < 80;
    })()`)) === true);
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 320, deviceScaleFactor: 1, mobile: false });

    console.log('== directory and raw pages ==');
    await goto('/');
    const align = await evaluate(`(() => {
      const rects = (selector) => [...document.querySelectorAll(selector)].map((el) => Math.round(el.getBoundingClientRect().x));
      const width = (selector) => [...document.querySelectorAll(selector)].map((el) => Math.round(el.getBoundingClientRect().width));
      const sizes = rects('.dir-row .meta-size');
      const times = rects('.dir-row .meta-time');
      const actions = width('.dir-row .row-actions');
      const targetSizes = [...document.querySelectorAll('.dir-row .row-actions .dl')].map((el) => Math.round(el.getBoundingClientRect().width));
      return {
        sizes, times, actions, targetSizes,
        sizesAligned: sizes.length > 1 && sizes.every((x) => x === sizes[0]),
        timesAligned: times.length > 1 && times.every((x) => x === times[0]),
        actionsAligned: actions.length > 1 && actions.every((x) => x === actions[0]),
        targetsBig: targetSizes.length > 0 && targetSizes.every((x) => x >= 36),
      };
    })()`);
    check('目录大小列对齐', align.sizesAligned, JSON.stringify(align));
    check('目录时间列对齐', align.timesAligned, JSON.stringify(align));
    check('目录操作列等宽', align.actionsAligned, JSON.stringify(align));
    check('目录操作点击区足够大', align.targetsBig, JSON.stringify(align));
    await goto('/sub/');
    check('目录页回到顶部按钮', (await evaluate('document.querySelectorAll(".totop").length')) === 1);
    check('目录页无分组标题', (await evaluate('!document.querySelector(".dir-section h2") && !!document.querySelector(".dir-list")')) === true);
    check('目录页 H1 无下划线', (await evaluate('getComputedStyle(document.querySelector(".dir-head h1")).borderBottomWidth')) === '0px');
    check('目录页头铺满内容面', (await evaluate(`(() => {
      const card = document.querySelector('.content-card').getBoundingClientRect();
      const title = document.querySelector('.dir-head h1').getBoundingClientRect();
      return Math.round(title.x - card.x) <= 32 && getComputedStyle(document.querySelector('.dir-head .head-inner')).paddingLeft === '30px';
    })()`)) === true);
    check('目录页面包屑完整', await crumbsComplete('.dir-head .crumbs', 'sub'));
    check('目录页可滚动', (await evaluate('document.documentElement.scrollHeight > innerHeight')) === true);
    await evaluate('window.scrollTo(0, 500)');
    await sleep(100);
    check('目录页已滚动', (await evaluate('window.scrollY')) > 0);
    await evaluate('document.querySelector(".totop").click()');
    check('点击回到顶部', await waitFor('window.scrollY === 0', 3000));

    await goto('/page.md?raw=1');
    check('源码页回到顶部按钮', (await evaluate('document.querySelectorAll(".totop").length')) === 1);
    check('源码页标题文件名', (await evaluate('document.querySelector(".page-head h1")?.textContent')) === 'page.md');
    check('源码页浏览器标题', (await evaluate('document.title')) === 'page.md · 源码 · mdview');
    check('源码页类型标签', (await evaluate('document.querySelector(".source-kind")?.textContent.trim()')) === 'Markdown');
    check('源码页信息标签', (await evaluate('(() => { const text = document.querySelector(".source-tags")?.textContent || ""; return text.includes("KB") && text.includes("行") && text.includes("更新于"); })()')) === true);
    check('源码页预览按钮', (await evaluate('document.querySelector(".page-actions .action.primary")?.textContent.trim()')) === '预览');
    check('源码页 H1 无下划线', (await evaluate('getComputedStyle(document.querySelector(".page-head h1")).borderBottomWidth')) === '0px');
    check('源码页头铺满内容面', (await evaluate(`(() => {
      const card = document.querySelector('.content-card').getBoundingClientRect();
      const title = document.querySelector('.page-head h1').getBoundingClientRect();
      return Math.round(title.x - card.x) <= 32 && getComputedStyle(document.querySelector('.page-head .head-inner')).paddingLeft === '30px';
    })()`)) === true);
    check('源码页行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');
    check('源码页原始内容', (await evaluate('document.querySelector(".source code").textContent')).startsWith('# Probe'));
    check('源码页面包屑完整', await crumbsComplete('.page-head .crumbs', 'page.md'));

    console.log('== html trusted ==');
    await goto('/page.html');
    check('HTML 信任目录是原文', (await evaluate('document.querySelector("h1")?.textContent')) === 'HTML Probe');
    check('HTML 信任目录无外壳', (await evaluate('!document.querySelector(".html-toolbar") && !document.querySelector("iframe")')) === true);
    check('HTML 信任目录不是 mdview 页', (await evaluate('document.body.dataset.page === undefined')) === true);
    check('HTML 信任目录脚本同源运行', (await evaluate('document.body.dataset.script')) === 'yes');
    check(
      'HTML 信任目录 localStorage 可用',
      (await evaluate('(() => { try { localStorage.setItem("mdv", "1"); return localStorage.getItem("mdv") === "1"; } catch { return false; } })()')) === true,
    );
    check(
      'HTML 信任目录同源 fetch 可用',
      (await evaluate('fetch("/page.md").then((response) => response.status).catch(() => 0)')) === 200,
    );
    await goto('/page.html?view=1');
    check('HTML 信任目录 view=1 也是原文', (await evaluate('document.querySelector("h1")?.textContent')) === 'HTML Probe');
    check('HTML 信任目录 view=1 无外壳', (await evaluate('!document.querySelector(".html-toolbar") && !document.querySelector("iframe")')) === true);
    await goto('/page.html?raw=1');
    check('HTML 源码页 tabs', (await evaluate('document.querySelectorAll(".html-toolbar .seg").length')) === 2);
    check('HTML 源码页无 iframe', (await evaluate('!document.querySelector("iframe")')) === true);
    check('HTML 源码行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');

    console.log('== html untrusted sandbox ==');
    const gotoUntrusted = async (path) => {
      requests.length = 0;
      await page.send('Page.navigate', { url: `${untrustedBase}${path}` });
      const deadline = Date.now() + 8000;
      while (Date.now() < deadline) {
        if ((await evaluate('document.readyState')) === 'complete') break;
        await sleep(50);
      }
      await sleep(500);
    };
    await gotoUntrusted('/page.html');
    check('未信任 HTML 页外壳', (await evaluate('document.body.dataset.page')) === 'html');
    check('未信任 HTML 预览页 tabs', (await evaluate('document.querySelectorAll(".html-toolbar .seg").length')) === 2);
    check('未信任 HTML iframe 存在', (await evaluate('document.querySelector("iframe.html-frame")?.getAttribute("src")')) === '/page.html?view=1');
    check('未信任 HTML iframe sandbox', (await evaluate('document.querySelector("iframe.html-frame")?.getAttribute("sandbox")')) === 'allow-scripts allow-forms allow-modals allow-popups');
    check('未信任 HTML 预览页无 TOC', (await evaluate('!document.querySelector(".toc-rail")')) === true);
    await sleep(1200);
    const htmlTargets = await browser.send('Target.getTargets');
    const iframeTarget = htmlTargets.targetInfos.find((target) => target.type === 'iframe' && target.url.startsWith(untrustedBase) && target.url.includes('/page.html?view=1'));
    check('未信任 HTML 沙箱 iframe 已加载', !!iframeTarget, JSON.stringify(htmlTargets.targetInfos.map((target) => target.url)));
    if (iframeTarget) {
      const attached = await browser.send('Target.attachToTarget', { targetId: iframeTarget.targetId, flatten: true });
      await browser.send('Runtime.enable', {}, attached.sessionId);
      const childEval = async (expression) => {
        const result = await browser.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, attached.sessionId);
        if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || 'child eval failed');
        return result.result.value;
      };
      check('未信任 HTML 脚本在沙箱运行', (await childEval('document.body.dataset.script')) === 'yes');
      check('未信任 HTML 相对 CSS 生效', (await childEval('getComputedStyle(document.body).backgroundColor')) === 'rgb(1, 2, 3)');
      check('未信任 HTML 沙箱屏蔽 localStorage', (await childEval('(() => { try { localStorage.getItem("x"); return false } catch { return true } })()')) === true);
      check('未信任 HTML 沙箱屏蔽同源 fetch', (await childEval('fetch("/_nav").then(() => false).catch(() => true)')) === true);
    }
    await gotoUntrusted('/page.html?raw=1');
    check('未信任 HTML 源码页 tabs', (await evaluate('document.querySelectorAll(".html-toolbar .seg").length')) === 2);
    check('未信任 HTML 源码页无 iframe', (await evaluate('!document.querySelector("iframe")')) === true);
    check('未信任 HTML 源码行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');
    await gotoUntrusted('/evil.svg');
    check('SVG 直开脚本不执行', (await evaluate('document.documentElement.getAttribute("data-x") === null')) === true);

    console.log('== no-JS baseline ==');
    await page.send('Emulation.setScriptExecutionDisabled', { value: true });
    await goto('/page.md');
    check('无 JS 无遮罩', (await evaluate('document.querySelectorAll("dialog").length')) === 0);
    check('无 JS 无复制按钮', (await evaluate('document.querySelectorAll(".copy-btn").length')) === 0);
    check('无 JS 无语言条', (await evaluate('document.querySelectorAll(".code-block").length')) === 0);
    check('无 JS 无回顶按钮', (await evaluate('document.querySelectorAll(".totop").length')) === 0);
    check('无 JS 无目录', (await evaluate('document.querySelector(".toc-inline")?.offsetParent === null')) === true);
    check('无 JS 保留回顶标记', (await evaluate('document.body.hasAttribute("data-totop")')) === true);
    check('无 JS 正文可读', (await evaluate('document.querySelector("article.markdown-body h1").textContent')) === 'Probe');
    check('无 JS 服务端不着色', (await evaluate('document.querySelectorAll("pre code span").length')) === 0);
    check('无 JS 隐藏主题按钮', (await evaluate('getComputedStyle(document.getElementById("theme-toggle")).display')) === 'none');
    check('无 JS 隐藏导航', (await evaluate('getComputedStyle(document.getElementById("nav-toggle")).display === "none" && getComputedStyle(document.getElementById("nav-panel")).display === "none"')) === true);
    check('无 JS 搜索入口是链接', (await evaluate('document.getElementById("search-open")?.getAttribute("href") === "/search" && document.getElementById("search-pop")?.hidden === true')) === true);
    await goto('/big.txt');
    check('无 JS 大源码全文', (await evaluate('document.querySelector(".source-chunked")?.textContent.includes("line 15000")')) === true);
    check('无 JS 大源码总行数', (await evaluate('document.querySelector(".source-note")?.textContent.includes("15001 行")')) === true);
    check('无 JS 大源码未截断', (await evaluate('document.querySelectorAll(".source-chunked .source-chunk").length')) === 31);
    await page.send('Emulation.setScriptExecutionDisabled', { value: false });
  } finally {
    try { await browser?.send('Browser.close'); } catch { /* closing */ }
    browser?.close();
    const chromeExited = new Promise((resolve) => {
      if (chromeChild.exitCode !== null) resolve();
      else chromeChild.once('exit', resolve);
    });
    chromeChild.kill('SIGKILL');
    server.kill('SIGKILL');
    untrustedServer.kill('SIGKILL');
    await Promise.race([chromeExited, sleep(2000)]);
    // Chrome may still be flushing its profile; retry instead of failing the
    // probe after every assertion has already passed.
    try {
      await rm(tmp, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
    } catch {
      // best-effort cleanup
    }
  }

  console.log(`\nPASS=${pass} FAIL=${fail}`);
  if (fail > 0) process.exit(1);
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(2);
});
