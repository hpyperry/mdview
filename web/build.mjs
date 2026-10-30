import { build } from 'esbuild';

const outdir = process.env.MDVIEW_WEB_OUTDIR || 'dist';

await build({
  entryPoints: ['src/app.ts'],
  bundle: true,
  minify: true,
  sourcemap: false,
  format: 'iife',
  // 浏览器基线 Chromium 86（ADR 0022）。CSS 也走这个 target：
  // 不设时 esbuild 会把 top/right/bottom/left 压成 inset 简写，
  // 把旧内核不支持的语法重新塞回产物。
  target: ['chrome86'],
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
