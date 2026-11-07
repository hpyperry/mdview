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
import { copyFile, mkdtemp, mkdir, readdir, rm, writeFile } from 'node:fs/promises';
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
  await mkdir(join(root, 'level1/level2/level3/level4/other'), { recursive: true });
  await writeFile(join(root, 'level1/note.md'), '# Level 1\n');
  await writeFile(join(root, 'level1/level2/note.md'), '# Level 2\n');
  await writeFile(join(root, 'level1/level2/level3/note.md'), '# Level 3\n');
  await writeFile(join(root, 'level1/level2/level3/sibling.md'), '# Sibling\n');
  await writeFile(join(root, 'level1/level2/level3/level4/deep.md'), '# Deep\n');
  await writeFile(join(root, 'level1/level2/level3/level4/other/other.md'), '# Other\n');
  const image = Buffer.from(PNG_1X1, 'base64');
  await writeFile(join(root, 'img.png'), image);
  await writeFile(join(root, 'sub', 'img.png'), image);
  const filler = Array.from({ length: 120 }, (_, i) => `第 ${i + 1} 段，用来把页面撑到可滚动。`).join('\n\n');
  await writeFile(
    join(root, 'page.md'),
    `# Probe\n\n中文 **粗体**。\n\n## Section A\n\n\`\`\`python\ndef f():\n    return 1\n\`\`\`\n\n\`\`\`\nplain fence text\n\`\`\`\n\n### Sub\n\n![图](img.png)\n\n[目录](/)\n\n#### Detail\n\n细节段落。\n\n##### Note\n\n注释段落。\n\n###### Tiny\n\n最小段落。\n\n## Section B\n\n末尾段落。\n\n${filler}\n`,
  );
  const longSections = Array.from(
    { length: 60 },
    (_, i) => `## Long Section ${String(i + 1).padStart(2, '0')}\n\n第 ${i + 1} 节正文。`,
  ).join('\n\n');
  await writeFile(join(root, 'long.md'), `# Long Document\n\n${longSections}\n\n${filler}\n`);
  await writeFile(join(root, 'sub', 'page.md'), '# Sub\n\n[上级](/) · ![图](img.png)\n');
  await writeFile(
    join(root, 'page.html'),
    '<!doctype html><html><head><meta charset="utf-8"><title>HTML Probe</title><link rel="stylesheet" href="probe.css"></head><body><h1>HTML Probe</h1><p>htmlneedle</p><script>document.body.dataset.script="yes"</script></body></html>\n',
  );
  await writeFile(join(root, 'probe.css'), 'body { background-color: rgb(1, 2, 3); }\n');
  await writeFile(
    join(root, 'origin.html'),
    '<!doctype html><html><head><meta charset="utf-8"><title>Origin Probe</title><link rel="stylesheet" href="origin.css"></head><body><h1 id="origin-title">pending</h1><p id="origin-module">module: pending</p><p id="origin-storage">storage: pending</p><p id="origin-fetch">fetch: pending</p><p id="origin-sw">sw: pending</p><script type="module" src="origin.js"></script></body></html>\n',
  );
  await writeFile(join(root, 'origin.css'), 'body { background-color: rgb(4, 5, 6); }\n');
  await writeFile(join(root, 'origin-module.js'), 'export const value = "ok";\n');
  await writeFile(join(root, 'origin.json'), '{"value":"ok"}\n');
  await writeFile(
    join(root, 'origin-sw.js'),
    'self.addEventListener("install", () => self.skipWaiting());\nself.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));\n',
  );
  await writeFile(
    join(root, 'origin.js'),
    [
      'import { value } from "./origin-module.js";',
      'const set = (id, text) => { const node = document.getElementById(id); if (node) node.textContent = text; };',
      'set("origin-module", "module: " + value);',
      'try { sessionStorage.setItem("origin", "ok"); set("origin-storage", "storage: " + sessionStorage.getItem("origin")); }',
      'catch (error) { set("origin-storage", "storage: " + error.name); }',
      'fetch("./origin.json", { cache: "no-store" }).then((response) => response.json())',
      '  .then((data) => set("origin-fetch", "fetch: " + data.value))',
      '  .catch((error) => set("origin-fetch", "fetch: " + error.name));',
      'if ("serviceWorker" in navigator) {',
      '  navigator.serviceWorker.register("./origin-sw.js").then(() => set("origin-sw", "sw: registered"))',
      '    .catch((error) => set("origin-sw", "sw: " + error.name));',
      '} else { set("origin-sw", "sw: unavailable"); }',
      'set("origin-title", "HTML second origin ok");',
      '',
    ].join('\n'),
  );
  await writeFile(
    join(root, 'evil.svg'),
    '<svg xmlns="http://www.w3.org/2000/svg"><script>document.documentElement.dataset.x=1</script></svg>\n',
  );
  for (const name of ['sample.zip', 'sample.jar', 'sample.epub', 'sample.cbz', 'sample.tar.bz2', 'sample.tar.xz']) {
    await copyFile(join(REPO, 'tests', 'fixtures', 'archives', name), join(root, name));
  }
  await copyFile(join(REPO, 'tests', 'fixtures', 'archives', 'docs', 'page.xhtml'), join(root, 'page.xhtml'));
  await copyFile(join(REPO, 'tests', 'fixtures', 'blockquote-spacing', 'quote.md'), join(root, 'quote.md'));
  await copyFile(join(REPO, 'tests', 'fixtures', 'export-artifact', 'doc.md'), join(root, 'export.md'));
  await copyFile(join(REPO, 'tests', 'fixtures', 'export-artifact', 'pic.png'), join(root, 'pic.png'));
  await copyFile(join(REPO, 'tests', 'fixtures', 'toc-all-levels', 'root', 'multi-h1.md'), join(root, 'multi-h1.md'));
  const encodingFixtures = join(REPO, 'tests', 'fixtures', 'encodings');
  for (const name of await readdir(encodingFixtures)) {
    if (name === 'README.md') continue;
    await copyFile(join(encodingFixtures, name), join(root, name));
  }
  await writeFile(join(root, 'plain.txt'), 'plain text without a language\nsecond line\n');
  await writeFile(join(root, 'small.rs'), 'fn main() {\n    let x = 1;\n    println!("{}", x);\n}\n');
  await writeFile(join(root, 'single.md'), '只有正文，没有标题。\n');
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
  await mkdir(join(root, 'search-many'), { recursive: true });
  for (let i = 0; i < 45; i += 1) {
    await writeFile(join(root, 'search-many', `batch-${String(i).padStart(2, '0')}.md`), `# batchneedle ${i}\n`);
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
  let htmlPort = await freePort();
  while (htmlPort === untrustedPort || htmlPort === port) {
    htmlPort = await freePort();
  }
  const htmlBase = `http://127.0.0.1:${htmlPort}`;
  const untrustedServer = spawn(
    binary,
    [
      '--root', root,
      '--host', '127.0.0.1',
      '--port', String(untrustedPort),
      '--port-tries', '0',
      '--untrusted',
      '--html-port', String(htmlPort),
    ],
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
    const scrollContentTo = (top) => evaluate(`(() => {
      const card = document.querySelector('.content-card');
      if (card && getComputedStyle(card).overflowY === 'auto') {
        card.scrollTop = ${Number(top)};
        return card.scrollTop;
      }
      window.scrollTo(0, ${Number(top)});
      return window.scrollY;
    })()`);
    const scrollContentToBottom = () => evaluate(`(() => {
      const card = document.querySelector('.content-card');
      if (card && getComputedStyle(card).overflowY === 'auto') {
        card.scrollTop = card.scrollHeight;
        return card.scrollTop;
      }
      window.scrollTo(0, document.body.scrollHeight);
      return window.scrollY;
    })()`);
    const currentScrollTop = () => evaluate(`(() => {
      const card = document.querySelector('.content-card');
      return card && getComputedStyle(card).overflowY === 'auto' ? card.scrollTop : window.scrollY;
    })()`);

    console.log('== preview page ==');
    await goto('/page.md');
    check('标题渲染', (await evaluate('document.querySelector("article.markdown-body h1").textContent')) === 'Probe');
    check('文档面包屑完整', await crumbsComplete('.topbar-path .crumbs', 'page.md'));
    check('文档页头显示文件名', (await evaluate('document.querySelector(".topbar-context h1")?.textContent')) === 'page.md');
    check(
      '文档页头元信息徽标',
      (await evaluate(`(() => {
        const badges = [...document.querySelectorAll('.topbar-context .page-meta .badge')];
        return badges.length >= 3 && badges.some((badge) => badge.textContent.includes('Markdown'));
      })()`)) === true,
    );
    check('文档页头操作齐全', (await evaluate('[...document.querySelectorAll(".action-panel .page-actions .action")].map((a) => a.textContent.trim()).join(",")')) === '源码,下载,导出图片,导出 PDF');
    check('页头操作岛已水合', await waitFor('window.__mdviewIslands?.mounted.includes("actions")', 3000));
    check('操作菜单默认关闭', (await evaluate('document.querySelector(".action-panel")?.hidden')) === true);
    await evaluate('document.querySelector(".action-menu-btn").click()');
    check(
      '操作菜单展开',
      (await evaluate(`(() => {
        const panel = document.querySelector('.action-panel');
        const items = [...panel.querySelectorAll('.action')].map((node) => node.textContent.trim());
        return panel.hidden === false && items.join(',') === '源码,下载,导出图片,导出 PDF';
      })()`)) === true,
    );
    await evaluate('document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))');
    check('操作菜单 Esc 关闭', (await evaluate('document.querySelector(".action-panel")?.hidden')) === true);
    await evaluate('document.querySelector(".action-menu-btn").click()');
    await evaluate('document.querySelector(".markdown-body").click()');
    check('操作菜单点外部关闭', (await evaluate('document.querySelector(".action-panel")?.hidden')) === true);
    check('文档岛已按需水合', await waitFor('["toc", "linetarget", "code", "zoom"].every((name) => window.__mdviewIslands?.mounted.includes(name))', 3000));
    check('渲染页带行定位数据', (await evaluate('document.querySelectorAll(".markdown-body [data-sourcepos]").length')) > 0);
    check(
      '文档页头使用顶栏',
      (await evaluate(`(() => {
        const bar = document.querySelector('.topbar.has-context');
        return Boolean(bar) && Boolean(bar.querySelector('.topbar-path .crumbs')) &&
          Boolean(bar.querySelector('.topbar-context h1')) && Boolean(bar.querySelector('.action-menu-btn'));
      })()`)) === true,
    );
    check('代码块数量', (await evaluate('document.querySelectorAll("pre code").length')) === 2);
    check('highlight.js 着色', await waitFor('document.querySelectorAll("pre code.hljs span").length > 0', 3000));
    check('复制按钮已注入', (await evaluate('document.querySelectorAll(".copy-btn").length')) === 2);
    check('代码块语言条', (await evaluate('document.querySelector(".code-block .code-bar .lang")?.textContent')) === 'python');
    check('无语言围栏不高亮', (await evaluate('[...document.querySelectorAll(".code-block")].some(b => b.querySelector(".lang")?.textContent === "代码" && !b.querySelector("code.hljs"))')) === true);
    check('页内目录已生成', (await evaluate('document.querySelectorAll("#toc-slot .toc-link").length')) === 7);
    check(
      '页内目录覆盖 h1–h6',
      (await evaluate(`(() => {
        const links = [...document.querySelectorAll('#toc-slot .toc-link')];
        return links.length === 7 && ['toc-h1', 'toc-h2', 'toc-h3', 'toc-h4', 'toc-h5', 'toc-h6'].every((cls) => links.some((a) => a.classList.contains(cls)));
      })()`)) === true,
    );
    const tocIndents = await evaluate(`(() => {
      const width = (cls) => parseFloat(getComputedStyle(document.querySelector('#toc-slot .toc-link.' + cls)).paddingLeft);
      return ['toc-h2', 'toc-h3', 'toc-h4', 'toc-h5', 'toc-h6'].map(width);
    })()`);
    check('页内目录逐级缩进', tocIndents.every((value, index) => index === 0 || value > tocIndents[index - 1]), JSON.stringify(tocIndents));
    check('导航默认关闭', (await evaluate('document.documentElement.dataset.navOpen === undefined && getComputedStyle(document.getElementById("nav-panel")).display === "none"')) === true);
    check('导航树未预渲染', (await evaluate('document.querySelectorAll("#nav-panel .nav-file").length')) === 0);
    check(
      '导航空闲预取完成',
      await waitFor('performance.getEntriesByType("resource").some((entry) => entry.name.includes("/_nav?__mdview=nav") && entry.responseEnd > 0)', 3000),
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
    const modalState = await evaluate(`(() => {
      try { return document.querySelector('dialog.zoomdlg')?.matches(':modal') === true; }
      catch { return null; }
    })()`);
    check('遮罩使用 modal', modalState === true || modalState === null, String(modalState));
    check('遮罩图片地址正确', (await evaluate('document.querySelector("dialog.zoomdlg img")?.getAttribute("src")')) === zoom.href);
    check('遮罩焦点在 dialog', await waitFor('document.activeElement === document.querySelector("dialog.zoomdlg")', 2000));
    await evaluate('document.querySelector(".zoom-close").click()');
    check('关闭按钮生效', await waitFor('document.querySelector("dialog.zoomdlg")?.open === false', 2000));
    check('焦点归还图片链接', await waitFor('document.activeElement === document.querySelector("a.zoom")', 2000));

    console.log('== blockquote spacing ==');
    await goto('/quote.md');
    const blockquoteMetrics = await evaluate(`(() => {
      const quotes = [...document.querySelectorAll('.markdown-body blockquote')];
      return quotes.map((b) => {
        const box = b.getBoundingClientRect();
        const cs = getComputedStyle(b);
        const first = b.firstElementChild.getBoundingClientRect();
        const last = b.lastElementChild.getBoundingClientRect();
        const after = b.nextElementSibling ? b.nextElementSibling.getBoundingClientRect().top - box.bottom : null;
        const kids = [...b.children];
        const paraGap = kids.length > 1 && kids[0].tagName === 'P' && kids[1].tagName === 'P'
          ? kids[1].getBoundingClientRect().top - kids[0].getBoundingClientRect().bottom
          : null;
        return {
          top: Math.round(first.top - box.top),
          bottom: Math.round(box.bottom - last.bottom),
          padTop: Math.round(parseFloat(cs.paddingTop)),
          padBottom: Math.round(parseFloat(cs.paddingBottom)),
          after: after === null ? null : Math.round(after),
          paraGap: paraGap === null ? null : Math.round(paraGap),
        };
      });
    })()`);
    check('引用块夹具完整', blockquoteMetrics.length === 5, JSON.stringify(blockquoteMetrics));
    check(
      '引用块文字上下居中',
      blockquoteMetrics.every((m) => m.top === m.padTop && m.bottom === m.padBottom && m.padTop === m.padBottom),
      JSON.stringify(blockquoteMetrics),
    );
    check(
      '引用块与后续段落间距不变',
      blockquoteMetrics.filter((m) => m.after !== null).every((m) => m.after === 16),
      JSON.stringify(blockquoteMetrics),
    );
    check(
      '引用块内段间距保留',
      blockquoteMetrics.filter((m) => m.paraGap !== null).every((m) => m.paraGap === 16),
      JSON.stringify(blockquoteMetrics),
    );
    await goto('/page.md');

    console.log('== export ==');
    await goto('/export.md');
    check('导出按钮存在', (await evaluate('document.querySelectorAll(".export-action").length')) === 2);
    check('导出岛已水合', await waitFor('window.__mdviewIslands?.mounted.includes("export")', 3000));
    const printed = await evaluate(`(() => {
      let count = 0;
      const original = window.print;
      window.print = () => { count += 1; };
      document.getElementById('export-pdf').click();
      window.print = original;
      return count;
    })()`);
    check('导出 PDF 调用打印', printed === 1, String(printed));
    const exported = await evaluate(`(async () => {
      const originalCreate = URL.createObjectURL;
      const originalClick = HTMLAnchorElement.prototype.click;
      let blob = null;
      URL.createObjectURL = (value) => { blob = value; return originalCreate.call(URL, value); };
      HTMLAnchorElement.prototype.click = function () {};
      try {
        const png = document.getElementById('export-png');
        window.__exportDoneSeen = false;
        window.__exportDonePath = '';
        window.__exportDoneDisabled = false;
        window.__exportDoneStatus = '';
        const doneObserver = new MutationObserver(() => {
          if (png.classList.contains('is-done')) {
            window.__exportDoneSeen = true;
            window.__exportDonePath = png.querySelector('svg.icon path')?.getAttribute('d') || '';
            window.__exportDoneDisabled = png.disabled;
            window.__exportDoneStatus = document.querySelector('.export-status')?.textContent || '';
          }
        });
        doneObserver.observe(png, { attributes: true, attributeFilter: ['class'] });
        png.click();
        const deadline = Date.now() + 15000;
        while (!blob && Date.now() < deadline) await new Promise((resolve) => setTimeout(resolve, 100));
      } finally {
        URL.createObjectURL = originalCreate;
        HTMLAnchorElement.prototype.click = originalClick;
      }
      if (!blob) return { ok: false, status: document.querySelector('.export-status')?.textContent };
      const bytes = new Uint8Array(await blob.arrayBuffer());
      const signature = [...bytes.slice(0, 8)].map((value) => value.toString(16).padStart(2, '0')).join('');
      const bitmap = await createImageBitmap(blob);
      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const context = canvas.getContext('2d');
      context.drawImage(bitmap, 0, 0);
      const corner = [...context.getImageData(1, 1, 1, 1).data];
      return {
        ok: true,
        type: blob.type,
        signature,
        width: bitmap.width,
        height: bitmap.height,
        corner,
        status: document.querySelector('.export-status')?.textContent,
      };
    })()`);
    check(
      '导出图片生成 PNG',
      exported.ok === true && exported.type === 'image/png' && exported.signature === '89504e470d0a1a0a',
      JSON.stringify(exported),
    );
    check(
      '导出图片浅色背景',
      Array.isArray(exported.corner) && exported.corner[0] === 255 && exported.corner[1] === 255 && exported.corner[2] === 255,
      JSON.stringify(exported.corner),
    );
    check('导出图片有尺寸', exported.width > 500 && exported.height > 500, JSON.stringify({ width: exported.width, height: exported.height }));
    check('导出 PNG 完成图标', await waitFor('window.__exportDoneSeen === true', 3000));
    check('导出 PNG 完成图标是勾', (await evaluate('window.__exportDonePath')) === 'M20 6 9 17l-5-5');
    check('导出完成期间禁用按钮', (await evaluate('window.__exportDoneDisabled')) === true);
    check('导出完成无状态文案', (await evaluate('window.__exportDoneStatus')) === '');
    await sleep(650);
    check('导出按钮图标恢复', (await evaluate('(() => { const png = document.getElementById("export-png"); return png?.disabled === false && png?.classList.contains("is-done") === false; })()')) === true);
    check('导出后仍无状态文案', (await evaluate('document.querySelector(".export-status")?.textContent || ""')) === '');
    const downloadDone = await evaluate(`(() => {
      const link = [...document.querySelectorAll('.page-actions a.action')].find((a) => a.href.includes('?download=1'));
      link.addEventListener('click', (event) => event.preventDefault(), { once: true });
      link.click();
      const path = link.querySelector('svg.icon path')?.getAttribute('d');
      const aria = link.getAttribute('aria-disabled');
      const pointerEvents = getComputedStyle(link).pointerEvents;
      let secondPrevented = null;
      const guard = (event) => { secondPrevented = event.defaultPrevented; link.removeEventListener('click', guard); };
      link.addEventListener('click', guard);
      link.click();
      return { path, aria, pointerEvents, secondPrevented, done: link.classList.contains('is-done') };
    })()`);
    check('下载完成图标是勾', downloadDone.path === 'M20 6 9 17l-5-5', JSON.stringify(downloadDone));
    check('下载完成期间禁用点击', downloadDone.done === true && downloadDone.aria === 'true' && downloadDone.pointerEvents === 'none' && downloadDone.secondPrevented === true, JSON.stringify(downloadDone));
    await sleep(650);
    check(
      '下载图标恢复',
      (await evaluate('(() => { const link = [...document.querySelectorAll(".page-actions a.action")].find((a) => a.href.includes("?download=1")); return link?.classList.contains("is-done") === false && link?.getAttribute("aria-disabled") === null && link?.querySelector("svg.icon path")?.getAttribute("d") === "M12 3v12"; })()')) === true,
    );

    await page.send('Emulation.setEmulatedMedia', { media: 'print' });
    await evaluate('document.documentElement.dataset.theme = "dark"');
    const printState = await evaluate(`(() => ({
      topbar: getComputedStyle(document.querySelector('.topbar')).display,
      head: getComputedStyle(document.querySelector('.topbar.has-context')).display,
      background: getComputedStyle(document.body).backgroundColor,
      maxWidth: getComputedStyle(document.querySelector('.markdown-body')).maxWidth,
    }))()`);
    await evaluate('delete document.documentElement.dataset.theme');
    await page.send('Emulation.setEmulatedMedia', { media: '' });
    check('打印隐藏顶栏与页头', printState.topbar === 'none' && printState.head === 'none', JSON.stringify(printState));
    check('打印强制浅色', printState.background === 'rgb(255, 255, 255)', JSON.stringify(printState));
    check('打印正文不限宽', printState.maxWidth === 'none', JSON.stringify(printState));
    await goto('/page.md');

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
    const lightChevron = await evaluate(`(() => {
      const svg = document.querySelector('#nav-panel .nav-chevron');
      const style = getComputedStyle(svg);
      return { classes: svg.getAttribute('class'), fill: style.fill, stroke: style.stroke, color: style.color };
    })()`);
    check(
      '导航三角保留 icon 基类',
      lightChevron.classes?.split(/\s+/).includes('icon') && lightChevron.fill === 'none' && lightChevron.stroke !== 'none',
      JSON.stringify(lightChevron),
    );
    await evaluate('document.documentElement.dataset.theme = "dark"');
    await sleep(50);
    const darkChevron = await evaluate(`(() => {
      const svg = document.querySelector('#nav-panel .nav-chevron');
      const style = getComputedStyle(svg);
      return { fill: style.fill, stroke: style.stroke, color: style.color };
    })()`);
    check(
      '深色导航三角不是黑块',
      darkChevron.fill === 'none' && darkChevron.stroke !== 'none' && darkChevron.color === 'rgb(145, 152, 161)',
      JSON.stringify(darkChevron),
    );
    await evaluate('delete document.documentElement.dataset.theme');
    await evaluate('document.getElementById("nav-close").click()');
    check('导航关闭', await waitFor('document.documentElement.dataset.navOpen === "0"', 2000));
    await goto('/search?__mdview=search&q=batchneedle');
    check('渐进搜索首批 40 个文件', await waitFor('document.querySelectorAll(".result-group").length === 40', 3000));
    check('渐进搜索显示继续按钮', (await evaluate('!!document.querySelector(".search-more")')) === true);
    await evaluate('document.querySelector(".search-more").click()');
    check('渐进搜索追加到 45 个文件', await waitFor('document.querySelectorAll(".result-group").length === 45', 5000));
    check(
      '渐进搜索结果不重复',
      (await evaluate(`(() => {
        const paths = [...document.querySelectorAll('.result-group .result-head .path span')].map((node) => node.textContent);
        return new Set(paths).size === 45;
      })()`)) === true,
    );
    check(
      '渐进搜索计数更新',
      (await evaluate(`(() => {
        const badges = [...document.querySelectorAll('.search-head .page-meta .badge')].map((node) => node.textContent.trim());
        return badges[0].includes('45 个文件') && badges[1].includes('45 条结果');
      })()`)) === true,
    );
    check('渐进搜索完成后移除按钮', (await evaluate('!document.querySelector(".search-more")')) === true);

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

    console.log('== shell alignment ==');
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    await goto('/sub/');
    const dirShell = await evaluate(`(() => {
      const card = document.querySelector('.content-card').getBoundingClientRect();
      const bar = document.querySelector('.topbar').getBoundingClientRect();
      return { cardLeft: Math.round(card.left), cardRight: Math.round(card.right), barLeft: Math.round(bar.left), barRight: Math.round(bar.right), cardWidth: Math.round(card.width), barWidth: Math.round(bar.width) };
    })()`);
    check(
      '目录主岛与顶栏左右对齐',
      Math.abs(dirShell.cardLeft - dirShell.barLeft) <= 1 && Math.abs(dirShell.cardRight - dirShell.barRight) <= 1 && Math.abs(dirShell.cardWidth - dirShell.barWidth) <= 2,
      JSON.stringify(dirShell),
    );
    await goto('/page.md');
    check('1440 常驻目录岛', await waitFor('document.body?.dataset.hasToc === "1" && getComputedStyle(document.getElementById("toc-island")).display === "flex"', 3000));
    const docShell = await evaluate(`(() => {
      const card = document.querySelector('.doc-card').getBoundingClientRect();
      const bar = document.querySelector('.topbar').getBoundingClientRect();
      const toc = document.getElementById('toc-island').getBoundingClientRect();
      const prose = document.querySelector('.markdown-body').getBoundingClientRect();
      return {
        cardLeft: Math.round(card.left), cardRight: Math.round(card.right),
        barLeft: Math.round(bar.left), barRight: Math.round(bar.right),
        tocRight: Math.round(toc.right), tocWidth: Math.round(toc.width),
        proseWidth: Math.round(prose.width),
        animation: getComputedStyle(document.getElementById('shell')).animationName,
      };
    })()`);
    check('文档主岛与顶栏左对齐', Math.abs(docShell.cardLeft - docShell.barLeft) <= 1, JSON.stringify(docShell));
    check('目录岛与顶栏右对齐', Math.abs(docShell.tocRight - docShell.barRight) <= 1 && docShell.tocWidth >= 180, JSON.stringify(docShell));
    check('文档主岛为目录岛收窄', docShell.cardRight < docShell.barRight - 180, JSON.stringify(docShell));
    check('文档正文保持宽阅读行', docShell.proseWidth >= 1000, JSON.stringify(docShell));
    check('文档分栏已启用', docShell.animation.includes('shell-split') || (await evaluate('document.body.dataset.split === "1"')), JSON.stringify(docShell));
    const fixedShell = await evaluate(`(() => {
      const card = document.querySelector('.content-card');
      const bar = document.querySelector('.topbar');
      const head = document.querySelector('.topbar.has-context');
      const before = { card: Math.round(card.getBoundingClientRect().top), bar: Math.round(bar.getBoundingClientRect().top), head: Math.round(head.getBoundingClientRect().top), bottom: Math.round(card.getBoundingClientRect().bottom) };
      card.scrollTop = 40;
      const after = { card: Math.round(card.getBoundingClientRect().top), bar: Math.round(bar.getBoundingClientRect().top), head: Math.round(head.getBoundingClientRect().top) };
      const style = getComputedStyle(card);
      return { before, after, winY: window.scrollY, scroll: card.scrollTop, viewport: innerHeight, overscrollX: style.overscrollBehaviorX, overscrollY: style.overscrollBehaviorY };
    })()`);
    check(
      '主岛固定只滚动内容',
      fixedShell.before.card === fixedShell.after.card && fixedShell.before.bar === fixedShell.after.bar && fixedShell.winY === 0 && fixedShell.scroll > 0,
      JSON.stringify(fixedShell),
    );
    check('主岛高度适配视口', fixedShell.before.bottom === fixedShell.viewport - 16, JSON.stringify(fixedShell));
    check('顶栏固定不随正文滚动', fixedShell.before.head === fixedShell.after.head, JSON.stringify(fixedShell));
    check('主岛放行横向回退手势', fixedShell.overscrollX === 'auto' && fixedShell.overscrollY === 'contain', JSON.stringify(fixedShell));
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    check('1280 仍为目录岛', await waitFor('document.body?.dataset.hasToc === "1" && getComputedStyle(document.getElementById("toc-island")).display === "flex"', 3000));
    check('1280 目录岛最小宽度', Math.round(await evaluate('document.getElementById("toc-island").getBoundingClientRect().width')) >= 160);

    console.log('== three columns ==');
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    check('正文与 TOC 两列', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 2);
    check('1200 无横向溢出', (await evaluate('document.documentElement.scrollWidth <= innerWidth + 1')) === true);
    check('TOC 细轨可见', (await evaluate('getComputedStyle(document.querySelector(".toc-rail")).display')) !== 'none');
    check('TOC 细轨与返回顶部错开', (await evaluate('getComputedStyle(document.querySelector(".totop")).right')) === '46px');
    check('正文面使用宽布局', (await evaluate('Math.round(document.querySelector(".doc-card").getBoundingClientRect().width)')) >= 1000);
    check('TOC 当前项', await waitFor('!!document.querySelector(".toc-tick.is-active")', 3000));
    check(
      'TOC 刻度覆盖 h1–h6',
      (await evaluate(`(() => {
        const ticks = [...document.querySelectorAll('.toc-tick')];
        return ticks.length === 7 && ['is-h1', 'is-h2', 'is-h3', 'is-h4', 'is-h5', 'is-h6'].every((cls) => ticks.some((tick) => tick.classList.contains(cls)));
      })()`)) === true,
    );
    const tickWidths = await evaluate(`(() => {
      const width = (cls) => parseFloat(getComputedStyle(document.querySelector('.toc-tick.' + cls), '::before').width);
      return ['is-h2', 'is-h3', 'is-h4', 'is-h5', 'is-h6'].map(width);
    })()`);
    check('TOC 刻度逐级变窄', tickWidths.every((value, index) => index === 0 || value < tickWidths[index - 1]), JSON.stringify(tickWidths));
    await evaluate('document.documentElement.dataset.theme = "dark"');
    await sleep(250);
    const darkTick = await evaluate(`(() => {
      const tick = document.querySelector('.toc-tick:not(.is-active)');
      const token = getComputedStyle(document.documentElement).getPropertyValue('--border-strong').trim();
      return { token, mark: getComputedStyle(tick, '::before').backgroundColor };
    })()`);
    check('深色 TOC 刻度用 --border-strong', darkTick.token === '#6e7a86' && darkTick.mark === 'rgb(110, 122, 134)', JSON.stringify(darkTick));
    await evaluate('delete document.documentElement.dataset.theme');
    check('TOC 面板初始关闭', (await evaluate('document.querySelector(".toc-pop") === null')) === true);
    await evaluate('document.querySelector(".toc-tick.is-h1").dispatchEvent(new PointerEvent("pointerenter", { bubbles: false }))');
    check('TOC 悬停刻度显示标题', await waitFor('document.querySelector(".toc-tip")?.textContent === "Probe"', 2000));
    check(
      'TOC 悬停标题横向可读',
      (await evaluate('(() => { const t = document.querySelector(".toc-tip"); if (!t) return false; const r = t.getBoundingClientRect(); return r.width > r.height; })()')) === true,
    );
    await evaluate('document.querySelector(".toc-tick.is-h1").dispatchEvent(new PointerEvent("pointerleave", { bubbles: false }))');
    check('TOC 移出隐藏标题', await waitFor('document.querySelector(".toc-tip") === null', 2000));
    check('TOC 悬停细轨不展开面板', (await evaluate('document.querySelector(".toc-pop") === null')) === true);
    await evaluate('document.querySelector(".toc-rail-btn").click()');
    check('TOC 可固定', await waitFor('document.querySelector(".toc-pop") !== null', 2000));
    await evaluate('document.getElementById("toc-rail").dispatchEvent(new PointerEvent("pointerleave"))');
    await sleep(250);
    check('TOC 固定后移出不收起', (await evaluate('document.querySelector(".toc-pop") !== null')) === true);
    await evaluate('document.querySelector(".toc-close").click()');
    check('TOC 固定可关闭', await waitFor('document.querySelector(".toc-pop") === null', 2000));
    await evaluate('document.getElementById("toc-rail").querySelector(".toc-rail-btn").click()');
    check('TOC 面板可展开', await waitFor('document.querySelectorAll(".toc-pop .toc-link").length === 7', 2000));
    check('TOC 面板无标题噪声', (await evaluate('document.querySelector(".toc-pop-head")?.textContent.trim() === ""')) === true);
    check(
      'TOC 面板当前项无整行底色',
      (await evaluate('getComputedStyle(document.querySelector(".toc-pop .toc-link.active")).backgroundColor')) === 'rgba(0, 0, 0, 0)',
    );
    await evaluate('document.querySelectorAll(".toc-pop .toc-link")[3].focus()');
    check(
      'TOC 焦点无蓝色整框',
      (await evaluate('(() => { const s = getComputedStyle(document.querySelectorAll(".toc-pop .toc-link")[3]); return s.outlineStyle === "none"; })()')) === true,
    );
    await scrollContentToBottom();
    await evaluate('document.querySelectorAll(".toc-pop .toc-link")[0].click()');
    check(
      'TOC 点击 h1 跳转',
      await waitFor(
        '(() => { const top = document.getElementById("toc-1").getBoundingClientRect().top; return top >= 60 && top <= 130; })()',
        3000,
      ),
    );
    await evaluate('document.getElementById("toc-rail").querySelector(".toc-rail-btn").click()');
    await waitFor('document.querySelectorAll(".toc-pop .toc-link").length === 7', 2000);
    await scrollContentToBottom();
    await evaluate('document.querySelectorAll(".toc-pop .toc-link")[1].click()');
    check(
      'TOC 点击 h2 跳转',
      await waitFor(
        '(() => { const top = document.getElementById("toc-2").getBoundingClientRect().top; return top >= 60 && top <= 130; })()',
        3000,
      ),
    );
    await evaluate('document.getElementById("toc-rail").querySelector(".toc-rail-btn").click()');
    await waitFor('document.querySelectorAll(".toc-pop .toc-link").length === 7', 2000);
    await evaluate(`(() => {
      const card = document.querySelector('.content-card');
      const t = document.getElementById('toc-7');
      if (card && getComputedStyle(card).overflowY === 'auto') {
        card.scrollTop += t.getBoundingClientRect().top - card.getBoundingClientRect().top - 20;
      } else {
        window.scrollTo(0, t.getBoundingClientRect().top + scrollY - 20);
      }
    })()`);
    check('TOC 定位到 Section B', await waitFor('(() => { const top = document.getElementById("toc-7").getBoundingClientRect().top; return top >= 60 && top <= 130; })()', 3000));
    await evaluate('window.dispatchEvent(new Event("scroll")); window.dispatchEvent(new Event("resize"))');
    const tocActive = await waitFor('document.querySelector(".toc-tick.is-active")?.getAttribute("data-target") === "toc-7"', 3000);
    check(
      'TOC 跟随滚动',
      tocActive,
      await evaluate(`(() => {
        const card = document.querySelector('.content-card');
        const y = card && getComputedStyle(card).overflowY === 'auto' ? card.scrollTop : window.scrollY;
        return JSON.stringify({ y, active: document.querySelector('.toc-tick.is-active')?.getAttribute('data-target'), top: document.getElementById('toc-7').getBoundingClientRect().top });
      })()`),
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

    console.log('== toc island ==');
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    check('1600 常驻目录岛', (await evaluate('getComputedStyle(document.getElementById("toc-island")).display')) === 'flex');
    check('1600 目录岛宽度', Math.round(await evaluate('document.getElementById("toc-island").getBoundingClientRect().width')) >= 180);
    check('1600 正文卡片撑满可用宽度', Math.round(await evaluate('document.querySelector(".doc-card").getBoundingClientRect().width')) > 1240);
    check('1600 细轨按钮隐藏', (await evaluate('getComputedStyle(document.querySelector(".toc-rail-btn")).display')) === 'none');
    check(
      '1600 返回顶部在目录岛',
      (await evaluate('getComputedStyle(document.querySelector(".totop")).display')) === 'none' &&
        (await evaluate('!!document.querySelector("#toc-island .toc-top")')) === true,
    );
    check('1600 目录岛标题文本', (await evaluate('document.querySelector("#toc-island .toc-link")?.textContent')) === 'Probe');
    check(
      '1600 回顶固定在岛底',
      (await evaluate(`(() => {
        const island = document.getElementById('toc-island').getBoundingClientRect();
        const button = document.querySelector('#toc-island .toc-top').getBoundingClientRect();
        return Math.abs(island.bottom - button.bottom) <= 1 && button.top > island.top + 100;
      })()`)) === true,
    );
    check(
      '1600 目录岛无标题徽标',
      (await evaluate('!document.querySelector("#toc-island .toc-island-head") && !document.querySelector("#toc-island .toc-island-count")')) === true,
    );
    check(
      '1600 当前项无整行底色',
      (await evaluate('getComputedStyle(document.querySelector("#toc-island .toc-link.active")).backgroundColor')) === 'rgba(0, 0, 0, 0)',
    );
    await scrollContentToBottom();
    await evaluate('document.querySelector("#toc-island .toc-link").click()');
    check(
      '1600 目录岛点击 h1 跳转',
      await waitFor(
        '(() => { const top = document.getElementById("toc-1").getBoundingClientRect().top; return top >= 60 && top <= 130; })()',
        3000,
      ),
    );
    check(
      '1600 目录岛 active 跟随',
      await waitFor('document.querySelector("#toc-island .toc-link.active")?.getAttribute("data-target") === "toc-1"', 3000),
    );

    await goto('/multi-h1.md');
    check('多 h1 文档目录项', (await evaluate('document.querySelectorAll("#toc-island .toc-link").length')) === 13);
    await scrollContentTo(0);
    await evaluate('document.querySelectorAll("#toc-island .toc-link")[3].click()');
    check(
      '多 h1 从顶部点 h1 B',
      await waitFor(
        '(() => { const top = document.getElementById("toc-4").getBoundingClientRect().top; return top >= 60 && top <= 130; })()',
        3000,
      ),
    );
    await scrollContentTo(0);
    await evaluate('document.querySelectorAll("#toc-island .toc-link")[11].click()');
    check(
      '多 h1 从顶部点 h1 D',
      await waitFor(
        `(() => {
          const card = document.querySelector('.content-card');
          const inner = card && getComputedStyle(card).overflowY === 'auto';
          const h = document.getElementById('toc-12');
          const top = h.getBoundingClientRect().top;
          const y = inner ? card.scrollTop : scrollY;
          const vh = inner ? card.clientHeight : innerHeight;
          const sh = inner ? card.scrollHeight : document.body.scrollHeight;
          const nearBottom = Math.abs((y + vh) - sh) < 4;
          return (top >= 60 && top <= 130) || (nearBottom && top > 0 && top < vh);
        })()`,
        3000,
      ),
    );
    await scrollContentToBottom();
    await evaluate('document.querySelectorAll("#toc-island .toc-link")[0].click()');
    check(
      '多 h1 从底部点 h1 A',
      await waitFor(
        '(() => { const top = document.getElementById("toc-1").getBoundingClientRect().top; return top >= 60 && top <= 130; })()',
        3000,
      ),
    );
    await goto('/long.md');
    check(
      '1600 长文档目录岛可滚动',
      (await evaluate('(() => { const list = document.querySelector(".toc-island-list"); return Boolean(list) && list.scrollHeight > list.clientHeight + 1; })()')) === true,
    );
    await scrollContentToBottom();
    check(
      '1600 长文档当前项在岛内',
      await waitFor(`(() => {
        const list = document.querySelector('.toc-island-list');
        const link = list?.querySelector('.toc-link.active');
        if (!list || !link) return false;
        const lb = list.getBoundingClientRect();
        const ab = link.getBoundingClientRect();
        return ab.top >= lb.top - 1 && ab.bottom <= lb.bottom + 1;
      })()`, 3000),
    );
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });

    await goto('/long.md');
    check('长文档刻度数完整', (await evaluate('document.querySelectorAll(".toc-tick").length')) === 61);
    check(
      '长文档细轨可滚动',
      (await evaluate('(() => { const ticks = document.querySelector(".toc-ticks"); return ticks.scrollHeight > ticks.clientHeight + 1; })()')) === true,
    );
    await evaluate('(() => { const target = [...document.querySelectorAll(".markdown-body h2")].pop(); target.scrollIntoView({ block: "start" }); })()');
    await evaluate('window.dispatchEvent(new Event("scroll"))');
    check(
      '长文档当前刻度自动可见',
      await waitFor(`(() => {
        const box = document.querySelector('.toc-ticks');
        const tick = document.querySelector('.toc-tick.is-active');
        const last = [...document.querySelectorAll('.markdown-body h2')].pop();
        if (!box || !tick || !last) return false;
        const rect = tick.getBoundingClientRect();
        const boxRect = box.getBoundingClientRect();
        return tick.dataset.target === last.id && rect.top >= boxRect.top - 1 && rect.bottom <= boxRect.bottom + 1;
      })()`, 3000),
    );

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
    check('导航包含根文件', await evaluate(`!!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/img.png')`));
    check('导航无分组文字', (await evaluate('(() => { const t = document.querySelector("#nav-panel .nav-tree").textContent; return !t.includes("文件") && !t.includes("目录"); })()')) === true);
    check('导航初始不预载深层文件', (await evaluate(`!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).some((a) => a.getAttribute('href') === '/level1/level2/level3/level4/deep.md')`)) === true);
    check('导航当前文件高亮', (await evaluate('document.querySelector("#nav-panel .nav-file.is-active")?.textContent')) === 'page.md');
    await evaluate(`[...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'level1')?.click()`);
    check('一级目录直接展开', await waitFor(`[...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].some((b) => b.textContent.trim() === 'level2')`, 2000));
    await evaluate(`[...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'level2')?.click()`);
    check('二级目录直接展开', await waitFor(`[...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].some((b) => b.textContent.trim() === 'level3')`, 2000));
    check('第三层目录不预载子项', (await evaluate(`!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).some((a) => a.getAttribute('href') === '/level1/level2/level3/sibling.md')`)) === true);
    await evaluate(`[...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'level3')?.click()`);
    check('第三层展开触发懒加载', await waitFor(`!!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/level1/level2/level3/sibling.md')`, 2000));
    check('懒加载请求带 dir', await waitFor(`performance.getEntriesByType('resource').some((entry) => entry.name.includes('/_nav?') && entry.name.includes('dir=level1%2Flevel2%2Flevel3'))`, 2000));
    check('懒加载仍只到一层', (await evaluate(`!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).some((a) => a.getAttribute('href') === '/level1/level2/level3/level4/deep.md')`)) === true);
    await evaluate(`(() => { const row = [...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'level4'); row?.dispatchEvent(new PointerEvent('pointerenter')); })()`);
    check('悬停预热下一层', await waitFor(`performance.getEntriesByType('resource').some((entry) => entry.name.includes('/_nav?') && entry.name.includes('dir=level1%2Flevel2%2Flevel3%2Flevel4'))`, 2000));
    await evaluate(`[...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'level4')?.click()`);
    check('预热后展开第四层', await waitFor(`!!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/level1/level2/level3/level4/deep.md')`, 2000));
    const level4Requests = await evaluate(`performance.getEntriesByType('resource').filter((entry) => entry.name.includes('/_nav?') && entry.name.includes('dir=level1%2Flevel2%2Flevel3%2Flevel4')).length`);
    check('悬停与点击合并请求', level4Requests === 1, String(level4Requests));

    await evaluate('localStorage.removeItem("mdview-nav-expanded")');
    await goto('/page.md');
    await evaluate('document.getElementById("nav-toggle").click()');
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    await evaluate(`[...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'sub')?.click()`);
    check('目录行只展开', await waitFor(`(() => { const row = [...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'sub'); return row?.getAttribute('aria-expanded') === 'true' && document.body.dataset.currentPath === 'page.md'; })()`, 2000));
    check('目录展开显示文件', await evaluate(`!!Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/sub/page.md')`));
    await evaluate('document.getElementById("nav-close").click()');
    await goto('/page.md');
    await evaluate('document.getElementById("nav-toggle").click()');
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    check('展开状态记忆', await waitFor(`(() => { const row = [...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'sub'); return row?.getAttribute('aria-expanded') === 'true'; })()`, 2000));
    await evaluate(`Array.from(document.querySelectorAll('#nav-panel a.nav-file')).find((a) => a.getAttribute('href') === '/sub/page.md').click()`);
    check('点击文件导航', await waitFor('document.body?.dataset.currentPath === "sub/page.md"', 5000));
    check('文件导航后导航收起', (await evaluate('document.documentElement.dataset.navOpen !== "1"')) === true);
    check('新页面导航空闲预取', await waitFor('performance.getEntriesByType("resource").some((entry) => entry.name.includes("/_nav?__mdview=nav") && entry.responseEnd > 0)', 3000));
    await evaluate('document.getElementById("nav-toggle").click()');
    check('新页面打开无全局加载中', (await evaluate('document.querySelector("#nav-panel > .nav-status") === null')) === true);
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    check('当前路径自动展开', await waitFor(`(() => { const row = [...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')].find((b) => b.textContent.trim() === 'sub'); return row?.getAttribute('aria-expanded') === 'true' && document.querySelector('#nav-panel .nav-file.is-active')?.textContent === 'page.md'; })()`, 2000));

    await goto('/level1/level2/level3/level4/deep.md');
    check('深层页预取带 active 脊柱', await waitFor(`performance.getEntriesByType('resource').some((entry) => entry.name.includes('/_nav?') && entry.name.includes('active=level1%2Flevel2%2Flevel3%2Flevel4%2Fdeep.md'))`, 3000));
    await evaluate('document.getElementById("nav-toggle").click()');
    await waitFor('document.querySelectorAll("#nav-panel .nav-file").length > 0', 3000);
    check('深层当前文件自动高亮', await waitFor(`document.querySelector('#nav-panel .nav-file.is-active')?.getAttribute('href') === '/level1/level2/level3/level4/deep.md'`, 2000));
    check('深层祖先自动展开', await waitFor(`(() => { const rows = [...document.querySelectorAll('#nav-panel .nav-dir > .nav-row')]; return ['level1', 'level2', 'level3', 'level4'].every((name) => rows.find((b) => b.textContent.trim() === name)?.getAttribute('aria-expanded') === 'true'); })()`, 2000));
    check('脊柱不触发逐级请求', (await evaluate(`performance.getEntriesByType('resource').every((entry) => !entry.name.includes('/_nav?') || !entry.name.includes('dir='))`)) === true);
    await evaluate('document.getElementById("nav-close").click()');
    await goto('/single.md');
    check('无标题时不显示 TOC' , await waitFor('document.getElementById("toc-rail")?.hidden === true && document.getElementById("toc-slot")?.hidden === true', 2000));
    check('无标题时正文单列', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 1);
    await goto('/page.md');
    await scrollContentTo(500);
    await sleep(250);
    check('顶栏 sticky', (await evaluate('Math.round(document.querySelector(".topbar").getBoundingClientRect().top)')) === 12);
    check('TOC 细轨 sticky', (await evaluate('(() => { const rail = document.querySelector(".toc-rail").getBoundingClientRect().top; const shell = document.getElementById("shell").getBoundingClientRect().top; return Math.round(rail) === Math.round(shell); })()')) === true);
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1000, height: 320, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    check('1000 单列', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 1);
    check('1000 细轨隐藏', (await evaluate('getComputedStyle(document.querySelector(".toc-rail")).display')) === 'none');
    check('1000 内联目录', (await evaluate('getComputedStyle(document.querySelector(".toc-inline")).display')) !== 'none');
    check('1000 无横向溢出', (await evaluate('document.documentElement.scrollWidth <= innerWidth + 1')) === true);
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });

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
    const noReplaceChildren = await page.send('Page.addScriptToEvaluateOnNewDocument', {
      source: 'delete Element.prototype.replaceChildren;',
    });
    await goto('/big.txt');
    check(
      '缺 replaceChildren 仍有行号',
      await waitFor('document.querySelector(".source-chunk .gutter a")?.textContent === "1"', 3000),
    );
    await page.send('Page.removeScriptToEvaluateOnNewDocument', { identifier: noReplaceChildren.identifier });
    await goto('/big.txt');
    await scrollContentToBottom();
    check('源码滚动到末行', await waitFor('!!document.getElementById("L15001")', 3000));
    await goto('/big.txt#L12000');
    check('源码行锚点', await waitFor('!!document.querySelector(".source-chunk .gutter a.target")', 3000));
    check('源码行高亮', (await evaluate('!!document.querySelector(".source-target-line")')) === true);
    check('源码锚点滚动', (await currentScrollTop()) > 0);
    await goto('/wide.txt');
    check('源码长行横向滚动', await waitFor('document.querySelector(".source-wrap").scrollWidth > document.querySelector(".source-wrap").clientWidth + 100', 3000));
    await goto('/big.rs');
    check('大源码按块着色', await waitFor('document.querySelectorAll(".source-chunk code.hljs").length > 0', 3000));
    check('大源码着色有界', (await evaluate('document.querySelectorAll(".source-chunk code.hljs").length')) < 10);
    const initialHighlights = await evaluate('document.querySelectorAll(".source-chunk code.hljs").length');
    await scrollContentToBottom();
    check(
      '大源码滚动后继续着色',
      await waitFor(`document.querySelectorAll(".source-chunk code.hljs").length > ${initialHighlights}`, 4000),
    );
    check('大源码高亮队列清空', (await evaluate('document.querySelectorAll(".source-chunk[data-highlight-queued]").length')) === 0);
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
    check('搜索页头显示查询', (await evaluate('document.querySelector(".search-head h1")?.textContent')) === '搜索 “Probe”');
    check('搜索页头结果徽标', (await evaluate('(() => { const text = document.querySelector(".search-head .page-meta")?.textContent || ""; return text.includes("个文件") && text.includes("条结果"); })()')) === true);
    check('搜索摘要用结果计数', (await evaluate(`(() => {
      const text = document.querySelector('.search-head .page-meta')?.textContent || '';
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
      const head = document.querySelector('.search-head').getBoundingClientRect();
      const title = document.querySelector('.search-head h1').getBoundingClientRect();
      const form = document.querySelector('.search-page-form').getBoundingClientRect();
      return { cardX: card.x, cardRight: card.right, headX: head.x, headRight: head.right, titleX: title.x, formX: form.x, formRight: form.right };
    })()`);
    check('搜索页头为独立岛', Math.round(searchGeom.titleX - searchGeom.headX) <= 32 && Math.abs(searchGeom.headX - searchGeom.cardX - 15) <= 1, JSON.stringify(searchGeom));
    check('搜索页头表单在右侧', searchGeom.formX > searchGeom.titleX && searchGeom.formRight >= searchGeom.headRight - 40, JSON.stringify(searchGeom));
    const docHit = await evaluate(`(() => {
      const link = document.querySelector('.result-group .hit[href*="#L"]');
      return link ? link.getAttribute('href') : null;
    })()`);
    check('Markdown 命中行是链接', /^\/page\.md#L\d+$/.test(docHit || ''), docHit);
    await goto(`/search?__mdview=search&q=${encodeURIComponent('末尾段落')}`);
    const lateHit = await evaluate(`(() => {
      const link = document.querySelector('.result-group .hit[href*="#L"]');
      return link ? link.getAttribute('href') : null;
    })()`);
    check('Markdown 后段行链接', /^\/page\.md#L\d+$/.test(lateHit || ''), lateHit);
    await goto(lateHit || '/page.md');
    check('渲染页行定位高亮', await waitFor('!!document.querySelector(".line-target")', 2000));
    check('渲染页滚动到命中行', (await currentScrollTop()) > 0);
    await goto('/search?__mdview=search&q=plain');
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

    console.log('== encodings ==');
    await goto('/gbk.md');
    check('GBK Markdown 文本', (await evaluate('document.querySelector("article.markdown-body h1")?.textContent')) === '中文标题');
    check('GBK Markdown 标签', (await evaluate('document.querySelector(".topbar-context .page-meta")?.textContent'))?.includes('GBK') === true);
    await goto('/gbk.txt');
    check('GBK 源码文本', (await evaluate('document.querySelector(".source code")?.textContent'))?.includes('编码测试 GBK 文本') === true);
    check('GBK 源码编码标签', (await evaluate('document.querySelector(".source-encoding")?.textContent')) === 'GBK');
    await goto('/utf16le.txt');
    check('UTF-16 源码文本', (await evaluate('document.querySelector(".source code")?.textContent'))?.includes('UTF-16LE 文本') === true);
    check('UTF-16 编码标签', (await evaluate('document.querySelector(".source-encoding")?.textContent')) === 'UTF-16LE BOM');
    await goto(`/search?__mdview=search&q=${encodeURIComponent('中文')}`);
    check('GBK 搜索命中', (await evaluate('document.querySelector(".result-group .hit")?.getAttribute("href")')) === '/gbk.md#L1');

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
    check('目录页 H1 无下划线', (await evaluate('getComputedStyle(document.querySelector(".topbar-context h1")).borderBottomWidth')) === '0px');
    check('目录页头使用顶栏', (await evaluate(`(() => {
      const bar = document.querySelector('.topbar.has-context');
      return Boolean(bar?.querySelector('.topbar-path .crumbs')) && Boolean(bar?.querySelector('.topbar-context h1'));
    })()`)) === true);
    check('目录页面包屑完整', await crumbsComplete('.topbar-path .crumbs', 'sub'));
    check('目录页头显示目录名', (await evaluate('document.querySelector(".topbar-context h1")?.textContent')) === 'sub');
    check('目录页头项目数徽标', (await evaluate('(() => { const text = document.querySelector(".topbar-context .page-meta")?.textContent || ""; return text.includes("个项目"); })()')) === true);
    check('目录页可滚动', (await evaluate('(() => { const card = document.querySelector(".content-card"); return card && getComputedStyle(card).overflowY === "auto" ? card.scrollHeight > card.clientHeight : document.documentElement.scrollHeight > innerHeight; })()')) === true);
    await scrollContentTo(500);
    await sleep(100);
    check('目录页已滚动', (await currentScrollTop()) > 0);
    await evaluate('document.querySelector(".totop").click()');
    check('点击回到顶部', await waitFor('(() => { const card = document.querySelector(".content-card"); return card && getComputedStyle(card).overflowY === "auto" ? card.scrollTop === 0 : window.scrollY === 0; })()', 3000));

    await goto('/page.md?raw=1');
    check('源码页回到顶部按钮', (await evaluate('document.querySelectorAll(".totop").length')) === 1);
    check('源码页标题文件名', (await evaluate('document.querySelector(".topbar-context h1")?.textContent')) === 'page.md');
    check('源码页浏览器标题', (await evaluate('document.title')) === 'page.md · 源码 · mdview');
    check('源码页类型标签', (await evaluate('document.querySelector(".source-kind")?.textContent.trim()')) === 'Markdown');
    check('源码页信息标签', (await evaluate('(() => { const text = document.querySelector(".topbar-context .page-meta")?.textContent || ""; return text.includes("KB") && text.includes("行") && text.includes("更新于"); })()')) === true);
    check('源码页预览按钮', (await evaluate('document.querySelector(".page-actions .action.primary")?.textContent.trim()')) === '预览');
    check('源码页无下载按钮', (await evaluate(`document.querySelectorAll('.page-actions a.action[href*="?download=1"]').length`)) === 0);
    check('源码页 H1 无下划线', (await evaluate('getComputedStyle(document.querySelector(".topbar-context h1")).borderBottomWidth')) === '0px');
    check('源码页头使用顶栏', (await evaluate(`(() => {
      const bar = document.querySelector('.topbar.has-context');
      return Boolean(bar?.querySelector('.topbar-path .crumbs')) && Boolean(bar?.querySelector('.topbar-context h1')) && Boolean(bar?.querySelector('.page-actions .action.primary'));
    })()`)) === true);
    check('源码页行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');
    check('源码页原始内容', (await evaluate('document.querySelector(".source code").textContent')).startsWith('# Probe'));
    check('源码页面包屑完整', await crumbsComplete('.topbar-path .crumbs', 'page.md'));

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

    console.log('== html untrusted second origin ==');
    const gotoUntrusted = async (path) => {
      requests.length = 0;
      await page.send('Page.navigate', { url: `${untrustedBase}${path}` });
      const deadline = Date.now() + 8000;
      while (Date.now() < deadline) {
        if ((await evaluate('document.readyState')) === 'complete') break;
        await sleep(50);
      }
      await sleep(300);
    };
    await gotoUntrusted('/page.html');
    check('未信任 HTML 跳到第二 origin', (await evaluate('location.origin')) === htmlBase);
    check('未信任 HTML 不是 mdview 外壳', (await evaluate('document.body.dataset.page === undefined')) === true);
    check('未信任 HTML 无 iframe/工具栏', (await evaluate('!document.querySelector("iframe") && !document.querySelector(".html-toolbar")')) === true);
    check('未信任 HTML 原文标题', (await evaluate('document.querySelector("h1")?.textContent')) === 'HTML Probe');
    check('未信任 HTML 脚本运行', (await evaluate('document.body.dataset.script')) === 'yes');
    check('未信任 HTML 相对 CSS 生效', (await evaluate('getComputedStyle(document.body).backgroundColor')) === 'rgb(1, 2, 3)');
    check(
      '未信任 HTML localStorage 可用',
      (await evaluate('(() => { try { localStorage.setItem("mdv", "1"); return localStorage.getItem("mdv") === "1"; } catch { return false; } })()')) === true,
    );
    check(
      '未信任 HTML sessionStorage 可用',
      (await evaluate('(() => { try { sessionStorage.setItem("mdv", "1"); return sessionStorage.getItem("mdv") === "1"; } catch { return false; } })()')) === true,
    );
    check('未信任 HTML 同源 fetch 原始文件', (await evaluate('fetch("/page.md").then((response) => response.status).catch(() => 0)')) === 200);
    check('第二 origin 不暴露 mdview 导航', (await evaluate('fetch("/_nav?__mdview=nav").then((response) => response.status).catch(() => 0)')) === 404);
    check('第二 origin 不暴露 mdview 资产', (await evaluate('fetch("/_assets/app.js").then((response) => response.status).catch(() => 0)')) === 404);

    await gotoUntrusted('/origin.html');
    check('第二 origin module 脚本', await waitFor('document.getElementById("origin-module")?.textContent === "module: ok"', 3000));
    check('第二 origin sessionStorage', await waitFor('document.getElementById("origin-storage")?.textContent === "storage: ok"', 3000));
    check('第二 origin fetch', await waitFor('document.getElementById("origin-fetch")?.textContent === "fetch: ok"', 3000));
    check('第二 origin service worker', await waitFor('document.getElementById("origin-sw")?.textContent === "sw: registered"', 5000));
    check('第二 origin 相对 CSS', (await evaluate('getComputedStyle(document.body).backgroundColor')) === 'rgb(4, 5, 6)');

    await gotoUntrusted('/page.html?raw=1');
    check('未信任 HTML 源码页在主 origin', (await evaluate('location.origin')) === untrustedBase);
    check('未信任 HTML 源码页 tabs', (await evaluate('document.querySelectorAll(".html-toolbar .seg").length')) === 2);
    check(
      '未信任 HTML 源码页预览指向第二 origin',
      (await evaluate('document.querySelector(".html-toolbar .seg")?.getAttribute("href")')) === `${htmlBase}/page.html`,
    );
    check('未信任 HTML 源码页无 iframe', (await evaluate('!document.querySelector("iframe")')) === true);
    check('未信任 HTML 源码行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');
    await gotoUntrusted('/evil.svg');
    check('SVG 直开脚本不执行', (await evaluate('document.documentElement.getAttribute("data-x") === null')) === true);

    console.log('== archives ==');
    await goto('/sample.zip/');
    check('压缩包页面标题', (await evaluate('document.querySelector("h1")?.textContent')) === 'sample.zip');
    check('压缩包格式头', (await evaluate('document.querySelector(".topbar-context .page-meta")?.textContent'))?.includes('ZIP'));
    check('压缩包下载入口', (await evaluate('[...document.querySelectorAll(".page-actions .action")].some((a) => a.textContent.includes("下载压缩包"))')) === true);
    check('包内目录入口', (await evaluate(`document.querySelector('a[href="/sample.zip/docs/"]') !== null`)) === true);
    await goto('/sample.zip/docs/a.md');
    check('包内 Markdown 渲染', (await evaluate('document.querySelector("article.markdown-body h1")?.textContent')) === 'Archive A');
    check('包内相对图片', (await evaluate('document.querySelector("article.markdown-body img")?.getAttribute("src")')) === '/sample.zip/docs/pic.png');
    await goto('/sample.zip/docs/page.html');
    check('包内 HTML trusted 原文', (await evaluate('document.querySelector("h1")?.textContent')) === 'Archive HTML');
    check('包内 HTML trusted 无外壳', (await evaluate('!document.querySelector("iframe") && !document.querySelector(".html-toolbar")')) === true);
    await goto('/sample.zip/docs/a.md?raw=1');
    check('包内源码行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');
    await gotoUntrusted('/sample.zip/docs/page.html');
    check('包内 HTML untrusted 第二 origin', (await evaluate('location.origin')) === htmlBase);
    check('包内 HTML untrusted 原文', (await evaluate('document.querySelector("h1")?.textContent')) === 'Archive HTML');
    check(
      '包内 HTML untrusted 无外壳',
      (await evaluate('!document.querySelector("iframe") && !document.querySelector(".html-toolbar")')) === true,
    );

    await goto('/sample.tar.bz2/docs/a.md');
    check('tar.bz2 包内渲染', (await evaluate('document.querySelector("article.markdown-body h1")?.textContent')) === 'Archive A');
    await goto('/sample.jar/');
    check('JAR 页面标签', (await evaluate('document.querySelector(".topbar-context .page-meta")?.textContent'))?.includes('JAR'));
    await goto('/sample.jar/META-INF/MANIFEST.MF');
    check('JAR 清单源码页', (await evaluate('document.querySelector("h1")?.textContent')) === 'MANIFEST.MF');
    check('JAR 清单内容', (await evaluate('document.body.textContent'))?.includes('Manifest-Version'));
    check('JAR 清单标签', (await evaluate('document.body.textContent'))?.includes('Manifest'));
    await goto('/sample.epub/');
    check('EPUB 页面标签', (await evaluate('document.querySelector(".topbar-context .page-meta")?.textContent'))?.includes('EPUB'));
    await goto('/sample.epub/OEBPS/chapter1.xhtml');
    check('EPUB 章节源码页', (await evaluate('document.querySelector("h1")?.textContent')) === 'chapter1.xhtml');
    check('EPUB 章节内容', (await evaluate('document.body.textContent'))?.includes('xhtmlneedle'));
    check('EPUB 章节行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');
    await goto('/sample.cbz/');
    check('CBZ 页面标签', (await evaluate('document.querySelector(".topbar-context .page-meta")?.textContent'))?.includes('CBZ'));
    await goto('/sample.cbz/page-01.png');
    check('CBZ 图片内联', (await evaluate('document.contentType')) === 'image/png');
    await goto('/page.xhtml');
    check('xhtml 源码页', (await evaluate('document.querySelector("h1")?.textContent')) === 'page.xhtml');
    check('xhtml 源码内容', (await evaluate('document.body.textContent'))?.includes('xhtmlneedle'));
    check('xhtml 源码标签', (await evaluate('document.body.textContent'))?.includes('XHTML'));

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
    check('无 JS 搜索入口是链接', (await evaluate('document.getElementById("search-open")?.getAttribute("href") === "/search?__mdview=search" && document.getElementById("search-pop")?.hidden === true')) === true);
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
