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
  await writeFile(join(root, 'plain.txt'), 'plain text without a language\nsecond line\n');
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

  const { child: chromeChild, wsUrl } = launchChrome(chrome, profile);
  let browser;
  try {
    if (!(await waitHttp(`${base}/`))) {
      throw new Error(`server did not start: ${serverErr}`);
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
    check('文档岛已按需水合', await waitFor('["toc", "code", "zoom"].every((name) => window.__mdviewIslands?.mounted.includes(name))', 3000));
    check('代码块数量', (await evaluate('document.querySelectorAll("pre code").length')) === 2);
    check('highlight.js 着色', await waitFor('document.querySelectorAll("pre code.hljs span").length > 0', 3000));
    check('复制按钮已注入', (await evaluate('document.querySelectorAll(".copy-btn").length')) === 2);
    check('代码块语言条', (await evaluate('document.querySelector(".code-block .code-bar .lang")?.textContent')) === 'python');
    check('无语言围栏不高亮', (await evaluate('[...document.querySelectorAll(".code-block")].some(b => b.querySelector(".lang")?.textContent === "代码" && !b.querySelector("code.hljs"))')) === true);
    check('页内目录已生成', (await evaluate('document.querySelectorAll("#toc-slot .toc-link").length')) === 3);
    check('侧栏当前文件', (await evaluate('document.querySelector(".side-link.active")?.textContent')) === 'page.md');
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
    await evaluate('document.getElementById("theme-toggle").click()');
    check('主题切到深色', (await evaluate('document.documentElement.dataset.themeMode')) === 'dark');
    await evaluate('document.getElementById("theme-toggle").click()');
    check('主题回到系统', (await evaluate('document.documentElement.dataset.themeMode')) === 'system');
    check('侧栏可收起', await evaluate('(() => { document.getElementById("sidebar-toggle").click(); return document.documentElement.dataset.sidebar === "collapsed"; })()'));
    await page.send('Emulation.setDeviceMetricsOverride', { width: 800, height: 600, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    await evaluate('document.getElementById("sidebar-toggle").click()');
    check('移动端打开抽屉', (await evaluate('document.documentElement.dataset.sidebarOpen')) === '1');
    check('移动端遮罩可见', (await evaluate('!document.getElementById("scrim").hidden')) === true);
    await evaluate('document.getElementById("scrim").click()');
    check('移动端遮罩关闭抽屉', (await evaluate('document.documentElement.dataset.sidebarOpen')) === undefined);

    console.log('== three columns ==');
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    if ((await evaluate('document.documentElement.dataset.sidebar')) === 'collapsed') {
      await evaluate('document.getElementById("sidebar-toggle").click()');
    }
    check('三列网格', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 3);
    check('TOC 细轨可见', (await evaluate('getComputedStyle(document.querySelector(".toc-rail")).display')) !== 'none');
    check('正文面使用宽布局', (await evaluate('Math.round(document.querySelector(".doc-card").getBoundingClientRect().width)')) >= 1000);
    check('TOC 当前项', await waitFor('!!document.querySelector(".toc-tick.is-active")', 3000));
    check('TOC 面板初始关闭', (await evaluate('document.querySelector(".toc-pop") === null')) === true);
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
    await evaluate('window.scrollTo(0, 500)');
    await sleep(250);
    check('顶栏 sticky', (await evaluate('Math.round(document.querySelector(".topbar").getBoundingClientRect().top)')) === 12);
    check('侧栏 sticky', (await evaluate('Math.round(document.querySelector(".sidebar").getBoundingClientRect().top)')) === 84);
    check('TOC 细轨 sticky', (await evaluate('Math.round(document.querySelector(".toc-rail").getBoundingClientRect().top)')) === 84);
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 320, deviceScaleFactor: 1, mobile: false });
    await goto('/page.md');
    check('1200 两列', (await evaluate('getComputedStyle(document.getElementById("shell")).gridTemplateColumns.split(" ").length')) === 2);
    check('1200 细轨隐藏', (await evaluate('getComputedStyle(document.querySelector(".toc-rail")).display')) === 'none');
    check('1200 内联目录', (await evaluate('getComputedStyle(document.querySelector(".toc-inline")).display')) !== 'none');

    console.log('== chunked source ==');
    await goto('/plain.txt');
    check('无语言源码不自动高亮', (await evaluate('document.querySelectorAll("pre code.hljs").length')) === 0);
    const chunkedStarted = Date.now();
    await goto('/big.txt');
    check('源码全文分块容器', (await evaluate('document.querySelectorAll(".source-chunked .source-chunk").length')) === 31);
    check('源码页只挂 source 岛', await waitFor('window.__mdviewIslands?.mounted.includes("source") && !window.__mdviewIslands.mounted.includes("toc")', 3000));
    check('源码末行在页面内', (await evaluate('document.querySelector(".source-chunked")?.textContent.includes("line 15000")')) === true);
    check('源码全文提示', (await evaluate('document.querySelector(".source-note")?.textContent.includes("15001 行") && document.querySelector(".source-note")?.textContent.includes("全文已载入")')) === true);
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
    await goto('/page.md');

    console.log('== search ==');
    await goto('/page.md');
    check('搜索岛已水合', await waitFor('window.__mdviewIslands?.mounted.includes("search")', 3000));
    await evaluate('document.getElementById("search-open").click()');
    check('搜索弹层打开', await waitFor('document.getElementById("search-pop")?.hidden === false', 2000));
    await evaluate('(() => { document.getElementById("search-input").value = "Probe"; document.getElementById("search-form").requestSubmit(); })()');
    check('搜索表单可提交', await waitFor('document.body.dataset.page === "search"', 5000));
    check('搜索命中分组', (await evaluate('document.querySelectorAll(".result-group").length')) > 0);
    check('搜索词高亮', await waitFor('document.querySelectorAll(".hit-snippet mark").length > 0', 3000));
    check('搜索页有独立表单', (await evaluate('!!document.querySelector(".search-page-form input")')) === true);

    console.log('== directory and raw pages ==');
    await goto('/sub/');
    check('目录页回到顶部按钮', (await evaluate('document.querySelectorAll(".totop").length')) === 1);
    check('目录页上级链接', (await evaluate('document.querySelector(".side-parent")?.getAttribute("href")')) === '/');
    check('目录页可滚动', (await evaluate('document.documentElement.scrollHeight > innerHeight')) === true);
    await evaluate('window.scrollTo(0, 500)');
    await sleep(100);
    check('目录页已滚动', (await evaluate('window.scrollY')) > 0);
    await evaluate('document.querySelector(".totop").click()');
    check('点击回到顶部', await waitFor('window.scrollY === 0', 3000));

    await goto('/page.md?raw=1');
    check('源码页回到顶部按钮', (await evaluate('document.querySelectorAll(".totop").length')) === 1);
    check('源码页行锚点', (await evaluate('document.querySelector("#L1")?.textContent')) === '1');
    check('源码页原始内容', (await evaluate('document.querySelector(".source code").textContent')).startsWith('# Probe'));

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
