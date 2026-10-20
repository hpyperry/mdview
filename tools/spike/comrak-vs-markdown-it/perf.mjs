import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import MarkdownIt from 'markdown-it';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS = path.join(HERE, 'results');
fs.mkdirSync(RESULTS, { recursive: true });

function repeatToSize(unit, target) {
  const n = Math.max(1, Math.ceil(target / unit.length));
  return unit.repeat(n);
}

const paragraph = 'Some **bold** text, a `code` span, and a [link](u.md).\n\n';
const urlUnit = 'see https://example.com/path?q=1&amp;b=2 and **bold** text ';
const fences = '```python\nprint("x")\n```\n\n';

const cases = [
  { id: 'perf-plain-1mb', name: 'plain-1mb', input: repeatToSize(paragraph, 1024 * 1024) },
  { id: 'perf-plain-10mb', name: 'plain-10mb', input: repeatToSize(paragraph, 10 * 1024 * 1024) },
  { id: 'perf-url-dense-1mb', name: 'url-dense-1mb', input: repeatToSize(urlUnit, 1024 * 1024) },
  { id: 'perf-fences-1mb', name: 'fences-1mb', input: repeatToSize(fences, 1024 * 1024) },
  { id: 'perf-brackets-256k', name: 'brackets-256k', input: '['.repeat(256 * 1024) },
  { id: 'perf-stars-256k', name: 'stars-256k', input: '*'.repeat(256 * 1024) },
];

const md = new MarkdownIt({ html: true, linkify: true, typographer: false, breaks: false, langPrefix: 'language-' });
md.linkify.set({ fuzzyLink: false });

const corpusFd = fs.openSync(path.join(RESULTS, 'perf-corpus.jsonl'), 'w');
const oracleFd = fs.openSync(path.join(RESULTS, 'perf-oracle.jsonl'), 'w');
const timings = [];

for (const c of cases) {
  fs.writeSync(corpusFd, `${JSON.stringify({ id: c.id, name: c.name, input: c.input, policy: 'semantic' })}\n`);
  const start = performance.now();
  const html = md.render(c.input);
  const elapsed = performance.now() - start;
  fs.writeSync(oracleFd, `${JSON.stringify({ id: c.id, elapsed_ms: elapsed, html_len: html.length })}\n`);
  timings.push({ name: c.name, bytes: Buffer.byteLength(c.input), oracle_ms: elapsed });
}

fs.closeSync(corpusFd);
fs.closeSync(oracleFd);
fs.writeFileSync(path.join(RESULTS, 'perf-oracle-summary.json'), JSON.stringify(timings, null, 2));
console.log('markdown-it timings:');
for (const t of timings) {
  console.log(`  ${t.name.padEnd(20)} ${(t.bytes / 1024).toFixed(0).padStart(7)} KiB  ${t.oracle_ms.toFixed(1).padStart(8)} ms`);
}
