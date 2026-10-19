import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import MarkdownIt from 'markdown-it';
import yaml from 'js-yaml';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CORPUS = path.join(HERE, 'corpus', 'corpus.jsonl');
const OUT_DIR = path.join(HERE, 'results');
const OUT = path.join(OUT_DIR, 'oracle.jsonl');

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: false,
  breaks: false,
  langPrefix: 'language-',
});
// VS Code's markdown preview sets only fuzzyLink:false.
md.linkify.set({ fuzzyLink: false });

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Mirrors VS Code's markdown-it-front-matter rule: only at document start,
// opening/closing lines exactly `---` at column 0 (trailing spaces allowed).
function splitFrontMatter(src) {
  const lines = src.split('\n');
  if (lines.length === 0) return { front: null, rest: src };
  if (lines[0].replace(/\s+$/, '') !== '---') return { front: null, rest: src };
  let close = -1;
  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].replace(/\s+$/, '') === '---') {
      close = i;
      break;
    }
  }
  if (close < 0) return { front: null, rest: src };
  return {
    front: lines.slice(1, close).join('\n'),
    rest: lines.slice(close + 1).join('\n'),
  };
}

// Mirrors VS Code's front matter table renderer (markdown-language-features).
function renderFrontMatter(content) {
  let data;
  try {
    data = yaml.load(content);
  } catch (err) {
    return `<div class="frontmatter-error" role="alert"><strong>Failed to parse frontmatter</strong><pre>${escapeHtml(err.message || String(err))}</pre></div>\n`;
  }

  let entries;
  if (data == null) entries = [];
  else if (typeof data !== 'object' || Array.isArray(data)) entries = [['', data]];
  else entries = Object.entries(data);
  if (entries.length === 0) return '';

  const valueHtml = (value) => {
    if (value == null) return '';
    if (Array.isArray(value)) {
      if (value.length === 0) return '';
      return `<ul>${value.map((v) => `<li>${valueHtml(v)}</li>`).join('')}</ul>`;
    }
    if (value instanceof Date) return escapeHtml(value.toISOString());
    if (typeof value === 'object') {
      return `<code>${escapeHtml(yaml.dump(value).trimEnd())}</code>`;
    }
    return escapeHtml(String(value));
  };

  const rows = entries
    .map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${valueHtml(value)}</td></tr>`)
    .join('');
  return `<table class="frontmatter" title="Frontmatter"><tbody>${rows}</tbody></table>\n`;
}

function renderEntry(entry) {
  const { front, rest } = splitFrontMatter(entry.input);
  const prefix = front == null ? '' : renderFrontMatter(front);
  return {
    id: entry.id,
    html: prefix + md.render(front == null ? entry.input : rest),
    front_matter: front != null,
  };
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const lines = fs.readFileSync(CORPUS, 'utf8').split('\n').filter(Boolean);
  const outFd = fs.openSync(OUT, 'w');
  let count = 0;
  for (const line of lines) {
    const entry = JSON.parse(line);
    let result;
    try {
      result = { ...renderEntry(entry) };
    } catch (err) {
      result = {
        id: entry.id,
        html: '',
        front_matter: false,
        error: err && err.stack ? err.stack : String(err),
      };
    }
    fs.writeSync(outFd, `${JSON.stringify(result)}\n`);
    count += 1;
  }
  fs.closeSync(outFd);
  console.log(`[oracle] wrote ${count} entries to ${OUT}`);
}

main();
