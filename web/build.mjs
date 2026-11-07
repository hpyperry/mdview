import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';

const outdir = process.env.MDVIEW_WEB_OUTDIR || 'dist';

await build({
  entryPoints: ['src/app.ts'],
  bundle: true,
  minify: true,
  sourcemap: false,
  format: 'iife',
  // 浏览器基线 Chromium 88（ADR 0024）。CSS 也走这个 target：
  // 不设时 esbuild 会把 top/right/bottom/left 压成 inset 简写，
  // 把基线外语法重新塞回产物。
  target: ['chrome88'],
  outdir,
  entryNames: 'app',
  assetNames: 'app',
  jsx: 'automatic',
  jsxImportSource: 'preact',
  loader: { '.css': 'css' },
  legalComments: 'none',
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'info',
});

// The highlighter worker reuses the already-built highlight.js bundle so large
// source files can be highlighted off the main thread. `window` is aliased to
// `self` because the bundle was written for a page context.
const highlight = await readFile(new URL('../assets/highlight.min.js', import.meta.url), 'utf8');
const workerBootstrap = `
self.window = self;
${highlight}
self.onmessage = function (event) {
  var data = event.data || {};
  if (typeof data.code !== 'string') return;
  try {
    var result = self.hljs.highlight(data.code, {
      language: data.language || 'plaintext',
      ignoreIllegals: true,
    });
    self.postMessage({ id: data.id, html: result.value });
  } catch (error) {
    self.postMessage({ id: data.id, error: String((error && error.message) || error) });
  }
};
`;
await writeFile(`${outdir}/hlworker.js`, workerBootstrap);
