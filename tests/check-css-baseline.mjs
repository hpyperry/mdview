#!/usr/bin/env node
// Enforce the browser CSS baseline: Chromium 86 (ADR 0022).
//
// The browser probe runs the newest headless Chrome, so it can never see a
// feature that old enterprise Chromium silently drops. This check is the
// only automatic guard: it rejects baseline-breaking syntax in the shipped
// stylesheets and keeps the two dark palettes in app.css in sync.
//
// Usage: node tests/check-css-baseline.mjs

import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.cwd();
const BASELINE = 86;
const STYLE_DIRS = ['web/src/styles', 'assets'];

// Minimum Chromium version for each syntax. Later entries need a newer engine
// than BASELINE, so their presence is a bug. Keep the version in the message so
// raising the baseline is a matter of deleting a line here.
const FORBIDDEN = [
  { needle: /light-dark\(/g, min: 123, label: 'light-dark()' },
  { needle: /color-mix\(/g, min: 111, label: 'color-mix()' },
  { needle: /\b(?:oklch|oklab|lab|lch|color|hwb)\(/g, min: 111, label: 'modern color function' },
  { needle: /\binset(?:-block|-inline)?\s*:/g, min: 87, label: 'inset shorthand' },
  { needle: /\baspect-ratio\s*:/g, min: 88, label: 'aspect-ratio' },
  { needle: /:is\(/g, min: 88, label: ':is()' },
  { needle: /:where\(/g, min: 88, label: ':where()' },
  { needle: /@layer\b/g, min: 99, label: '@layer' },
  { needle: /@container\b/g, min: 105, label: '@container' },
  { needle: /:has\(/g, min: 105, label: ':has()' },
  { needle: /\b(?:dvh|svh|lvh|dvw|svw)\b/g, min: 108, label: 'dynamic viewport unit' },
  { needle: /text-wrap\s*:/g, min: 114, label: 'text-wrap' },
  { needle: /scrollbar-gutter\s*:/g, min: 94, label: 'scrollbar-gutter' },
  { needle: /\bsubgrid\b/g, min: 117, label: 'subgrid' },
  { needle: /overflow\s*:\s*clip/g, min: 90, label: 'overflow: clip' },
  { needle: /\baccent-color\s*:/g, min: 93, label: 'accent-color' },
  { needle: /text-underline-offset\s*:/g, min: 87, label: 'text-underline-offset' },
  { needle: /^\s*&/gm, min: 120, label: 'CSS nesting' },
];

function styleFiles() {
  const files = [];
  for (const dir of STYLE_DIRS) {
    for (const name of readdirSync(join(ROOT, dir))) {
      if (name.endsWith('.css')) files.push(join(ROOT, dir, name));
    }
  }
  return files.sort();
}

// Blank out comments while preserving line numbers.
function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, (block) => block.replace(/[^\n]/g, ' '));
}

function lineAt(text, index) {
  return text.slice(0, index).split('\n').length;
}

const violations = [];
for (const file of styleFiles()) {
  const raw = readFileSync(file, 'utf8');
  const text = stripComments(raw);
  const rel = relative(ROOT, file).replaceAll('\\', '/');
  for (const rule of FORBIDDEN) {
    rule.needle.lastIndex = 0;
    let match;
    while ((match = rule.needle.exec(text))) {
      violations.push({
        file: rel,
        line: lineAt(text, match.index),
        message: `${rule.label} needs Chromium ${rule.min}+ (baseline ${BASELINE}): ${match[0].trim()}`,
      });
    }
  }
}

// The two dark palettes are written out twice (system preference and manual
// toggle). They must stay token-for-token identical or one path silently drifts.
const appCss = readFileSync(join(ROOT, 'web/src/styles/app.css'), 'utf8');
const systemDark = appCss.match(/@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*html:not\(\[data-theme="light"\]\)\s*\{([\s\S]*?)\}\s*\}/);
const manualDark = appCss.match(/html\[data-theme="dark"\]\s*\{([\s\S]*?)\}/);

function tokens(block) {
  const map = new Map();
  for (const line of block.split('\n')) {
    const match = line.match(/^\s*(--[\w-]+)\s*:\s*(.+?);\s*$/);
    if (match) map.set(match[1], match[2].trim());
  }
  return map;
}

if (!systemDark || !manualDark) {
  violations.push({
    file: 'web/src/styles/app.css',
    line: 1,
    message: 'dark palette blocks not found: expected @media(prefers-color-scheme:dark) html:not([data-theme="light"]) and html[data-theme="dark"]',
  });
} else {
  const a = tokens(systemDark[1]);
  const b = tokens(manualDark[1]);
  for (const [name, value] of a) {
    if (!b.has(name)) {
      violations.push({ file: 'web/src/styles/app.css', line: 1, message: `dark palettes out of sync: ${name} missing from [data-theme="dark"]` });
    } else if (b.get(name) !== value) {
      violations.push({ file: 'web/src/styles/app.css', line: 1, message: `dark palettes out of sync: ${name} is ${value} vs ${b.get(name)}` });
    }
  }
  for (const name of b.keys()) {
    if (!a.has(name)) {
      violations.push({ file: 'web/src/styles/app.css', line: 1, message: `dark palettes out of sync: ${name} only in [data-theme="dark"]` });
    }
  }
}

if (violations.length) {
  console.error(`css baseline: ${violations.length} problem(s), target Chromium ${BASELINE}+`);
  for (const item of violations) {
    console.error(`  ${item.file}:${item.line}: ${item.message}`);
  }
  process.exit(1);
}

console.log(`css baseline: ok (${styleFiles().length} stylesheets, Chromium ${BASELINE}+)`);
