#!/usr/bin/env node
// Verify that relative Markdown links in documentation resolve on disk.
// Code fences, inline code, archive pages and server-root URLs are ignored.

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';

const ROOT = process.cwd();
const SKIP_DIRS = new Set(['.git', '.zcode', 'node_modules', 'target', 'web/dist']);
const SKIP_PREFIXES = ['docs/archive/'];

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const rel = relative(ROOT, path).replaceAll('\\', '/');
    if (SKIP_DIRS.has(name) || SKIP_PREFIXES.some((prefix) => rel.startsWith(prefix))) continue;
    const stat = statSync(path);
    if (stat.isDirectory()) walk(path, out);
    else if (name.endsWith('.md')) out.push(path);
  }
  return out;
}

function stripCode(text) {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/~~~[\s\S]*?~~~/g, '')
    .replace(/`[^`\n]*`/g, '');
}

function shouldSkip(target) {
  return !target
    || target.startsWith('#')
    || target.startsWith('/')
    || /^(?:https?:|mailto:|data:|javascript:)/i.test(target);
}

function resolveTarget(file, target) {
  let path = target.split('#', 1)[0].split('?', 1)[0];
  if (!path) return null;
  try {
    path = decodeURIComponent(path);
  } catch {
    // Keep the raw path; the missing-link message will show it.
  }
  return resolve(dirname(file), path);
}

const missing = [];
let checked = 0;
for (const file of walk(ROOT)) {
  const text = stripCode(readFileSync(file, 'utf8'));
  const link = /!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
  let match;
  while ((match = link.exec(text))) {
    const target = match[1];
    if (shouldSkip(target)) continue;
    const resolved = resolveTarget(file, target);
    if (!resolved) continue;
    checked += 1;
    if (!existsSync(resolved)) {
      missing.push({
        file: relative(ROOT, file).replaceAll('\\', '/'),
        target,
        resolved: relative(ROOT, resolved).replaceAll('\\', '/'),
      });
    }
  }
}

if (missing.length) {
  console.error(`doc links: ${missing.length} missing (${checked} checked)`);
  for (const item of missing) {
    console.error(`  ${item.file}: ${item.target} -> ${item.resolved}`);
  }
  process.exit(1);
}
console.log(`doc links: ok (${checked} checked)`);
