import { build } from 'esbuild';

const outdir = process.env.MDVIEW_WEB_OUTDIR || 'dist';

await build({
  entryPoints: ['src/app.ts'],
  bundle: true,
  minify: true,
  sourcemap: false,
  format: 'iife',
  target: ['es2020'],
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
