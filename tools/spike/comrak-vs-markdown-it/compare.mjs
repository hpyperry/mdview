import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseFragment } from 'parse5';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS = path.join(HERE, 'results');

const PRESERVE = new Set(['pre', 'code', 'textarea', 'script', 'style']);
const TRIM_WS = new Set([
  'body', 'div', 'section', 'article', 'header', 'footer', 'main', 'nav', 'aside',
  'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'blockquote',
  'dl', 'dt', 'dd', 'details', 'summary', 'figure', 'figcaption',
]);
const IGNORED_ATTRS = new Set(['data-line', 'data-vscode-context', 'data-sourcepos', 'sourcepos']);
const IGNORED_CLASSES = new Set(['code-line']);

function readJsonl(file) {
  return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

function canonicalAttrs(node) {
  const attrs = [];
  for (const attr of node.attrs || []) {
    if (IGNORED_ATTRS.has(attr.name)) continue;
    let value = attr.value;
    if (attr.name === 'class') {
      const classes = value.split(/\s+/).filter(Boolean).filter((c) => !IGNORED_CLASSES.has(c)).sort();
      if (classes.length === 0) continue;
      value = classes.join(' ');
    }
    attrs.push([attr.name, value]);
  }
  attrs.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return attrs;
}

function canonText(value, parentTag) {
  if (PRESERVE.has(parentTag)) return { type: 'text', value };
  return { type: 'text', value: value.replace(/\s+/g, ' ') };
}

function canonNode(node, parentTag) {
  if (node.nodeName === '#text') {
    return canonText(node.value, parentTag);
  }
  if (node.nodeName === '#comment') {
    return { type: 'comment', value: node.data };
  }
  if (!node.tagName) {
    return null;
  }
  const tag = node.tagName.toLowerCase();
  const children = [];
  for (const child of node.childNodes || []) {
    const c = canonNode(child, tag);
    if (c) children.push(c);
  }
  if (TRIM_WS.has(tag)) {
    while (children.length && children[0].type === 'text' && /^\s*$/.test(children[0].value)) children.shift();
    while (children.length && children[children.length - 1].type === 'text' && /^\s*$/.test(children[children.length - 1].value)) children.pop();
  }
  return { type: 'element', tag, attrs: canonicalAttrs(node), children };
}

function canonicalize(html) {
  const frag = parseFragment(html);
  const children = [];
  for (const child of frag.childNodes || []) {
    const c = canonNode(child, '');
    if (c) children.push(c);
  }
  while (children.length && children[0].type === 'text' && /^\s*$/.test(children[0].value)) children.shift();
  while (children.length && children[children.length - 1].type === 'text' && /^\s*$/.test(children[children.length - 1].value)) children.pop();
  return { type: 'root', children };
}

function short(value, max = 240) {
  if (value === undefined || value === null) return null;
  const s = typeof value === 'string' ? value : JSON.stringify(value);
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

function diffNode(a, b, pathStr, out, limit = 6) {
  if (out.length >= limit) return;
  if (!a && !b) return;
  if (!a || !b) {
    out.push({ kind: 'missing', path: pathStr, a: a ? short(a) : null, b: b ? short(b) : null });
    return;
  }
  if (a.type !== b.type) {
    out.push({ kind: 'type', path: pathStr, a: a.type, b: b.type });
    return;
  }
  if (a.type === 'text') {
    if (a.value !== b.value) out.push({ kind: 'text', path: pathStr, a: short(a.value), b: short(b.value) });
    return;
  }
  if (a.type === 'comment') {
    if (a.value !== b.value) out.push({ kind: 'comment', path: pathStr, a: short(a.value), b: short(b.value) });
    return;
  }
  if (a.type === 'root') {
    const n = Math.max(a.children.length, b.children.length);
    for (let i = 0; i < n && out.length < limit; i += 1) {
      diffNode(a.children[i], b.children[i], `root[${i}]`, out, limit);
    }
    return;
  }
  if (a.tag !== b.tag) {
    out.push({ kind: 'tag', path: pathStr, a: a.tag, b: b.tag });
    return;
  }
  const amap = Object.fromEntries(a.attrs);
  const bmap = Object.fromEntries(b.attrs);
  const names = [...new Set([...Object.keys(amap), ...Object.keys(bmap)])].sort();
  for (const name of names) {
    if (amap[name] !== bmap[name]) {
      out.push({ kind: 'attr', path: pathStr, name, a: short(amap[name]), b: short(bmap[name]) });
    }
  }
  const n = Math.max(a.children.length, b.children.length);
  for (let i = 0; i < n && out.length < limit; i += 1) {
    diffNode(a.children[i], b.children[i], `${pathStr}/${a.tag}[${i}]`, out, limit);
  }
}

function hasTableAlignmentDiff(diffs) {
  return diffs.some((d) => {
    if (d.kind !== 'attr') return false;
    if (d.name === 'align') return true;
    if (d.name === 'style' && (/text-align/.test(d.a || '') || /text-align/.test(d.b || ''))) return true;
    return false;
  });
}

function classify(entry, diffs, oracleFrontMatter) {
  if (diffs.length === 0) return 'match';
  if (oracleFrontMatter || entry.policy === 'front_matter') return 'front_matter_expected';

  const input = entry.input || '';
  if (/\[[^\]]+\]:\s*(javascript|vbscript|data|file):/i.test(input)) {
    return 'protocol_reference_definition_expected';
  }
  if (/\[[^\]]+\]:\s*</.test(input) && entry.tags.includes('reference')) {
    return 'reference_angle_definition_gap';
  }
  if (hasTableAlignmentDiff(diffs)) return 'table_alignment_expected';
  if (
    entry.tags.includes('autolink') ||
    diffs.some((d) => d.kind === 'attr' && d.name === 'href' && /mailto:|https?:\/\/www\./i.test(d.a || d.b || '')) ||
    (/@/.test(input) && diffs.some((d) => d.kind === 'attr' && d.name === 'href' && /mailto:/i.test(d.a || d.b || '')))
  ) {
    return 'linkify_boundary_gap';
  }
  if (diffs.some((d) => d.kind === 'attr' && d.name === 'alt')) {
    return 'image_alt_text_gap';
  }
  if (diffs.every((d) => d.kind === 'text' && /^\s*$/.test(d.a || '') && /^\s*$/.test(d.b || ''))) {
    return 'serializer_whitespace';
  }
  return 'unexplained';
}

function bump(obj, key) {
  obj[key] = (obj[key] || 0) + 1;
}

function main() {
  const corpus = readJsonl(path.join(HERE, 'corpus', 'corpus.jsonl'));
  const oracle = new Map(readJsonl(path.join(RESULTS, 'oracle.jsonl')).map((r) => [r.id, r]));
  const comrak = new Map(readJsonl(path.join(RESULTS, 'comrak.jsonl')).map((r) => [r.id, r]));

  const summary = {
    total: corpus.length,
    scored_parser: 0,
    match: 0,
    scored_match: 0,
    scored_expected: 0,
    scored_unexplained: 0,
    front_matter_policy: { match: 0, expected: 0 },
    expected_custom_layer: {},
    unexplained: 0,
    by_source: {},
    by_tag: {},
    skipped: { stress: 0, internal: 0 },
  };
  const diffsOut = fs.openSync(path.join(RESULTS, 'diffs.jsonl'), 'w');
  const unexplainedExamples = [];

  for (const entry of corpus) {
    if (entry.policy === 'stress') { summary.skipped.stress += 1; continue; }
    if (entry.policy === 'internal') { summary.skipped.internal += 1; continue; }

    const o = oracle.get(entry.id);
    const c = comrak.get(entry.id);
    const oHtml = o ? o.html : '';
    const cHtml = c ? c.html : '';
    const a = canonicalize(oHtml);
    const b = canonicalize(cHtml);
    const diffs = [];
    diffNode(a, b, '', diffs);
    const kind = classify(entry, diffs, !!(o && o.front_matter));

    const srcKey = entry.source;
    summary.by_source[srcKey] = summary.by_source[srcKey] || { total: 0, match: 0, expected: 0, unexplained: 0 };
    summary.by_source[srcKey].total += 1;
    for (const tag of entry.tags) {
      summary.by_tag[tag] = summary.by_tag[tag] || { total: 0, match: 0, unexplained: 0 };
      summary.by_tag[tag].total += 1;
    }

    if (kind === 'match') {
      summary.match += 1;
      if (entry.policy !== 'front_matter') summary.scored_match += 1;
      else summary.front_matter_policy.match += 1;
      summary.by_source[srcKey].match += 1;
      for (const tag of entry.tags) summary.by_tag[tag].match += 1;
    } else if (kind === 'unexplained') {
      summary.unexplained += 1;
      if (entry.policy !== 'front_matter') summary.scored_unexplained += 1;
      summary.by_source[srcKey].unexplained += 1;
      for (const tag of entry.tags) summary.by_tag[tag].unexplained += 1;
    } else {
      bump(summary.expected_custom_layer, kind);
      if (entry.policy !== 'front_matter') summary.scored_expected += 1;
      else summary.front_matter_policy.expected += 1;
      summary.by_source[srcKey].expected += 1;
    }

    if (entry.policy !== 'front_matter') {
      summary.scored_parser += 1;
    }

    if (diffs.length > 0) {
      const rec = {
        id: entry.id,
        name: entry.name,
        source: entry.source,
        policy: entry.policy,
        tags: entry.tags,
        kind,
        input: short(entry.input, 1200),
        diffs,
        oracle: short(oHtml, 1200),
        comrak: short(cHtml, 1200),
      };
      fs.writeSync(diffsOut, `${JSON.stringify(rec)}\n`);
      if (kind === 'unexplained' && unexplainedExamples.length < 20) {
        unexplainedExamples.push(rec);
      }
    }
  }
  fs.closeSync(diffsOut);

  summary.match_rate_scored = summary.scored_parser
    ? ((summary.scored_match / summary.scored_parser) * 100).toFixed(2) + '%'
    : 'n/a';
  summary.unexplained_rate_scored = summary.scored_parser
    ? ((summary.scored_unexplained / summary.scored_parser) * 100).toFixed(2) + '%'
    : 'n/a';

  fs.writeFileSync(path.join(RESULTS, 'summary.json'), JSON.stringify(summary, null, 2));

  console.log('=== P0 summary ===');
  console.log(`total corpus: ${summary.total}`);
  console.log(`scored parser entries: ${summary.scored_parser}`);
  console.log(`scored match: ${summary.scored_match} (${summary.match_rate_scored})`);
  console.log(`scored expected custom-layer: ${summary.scored_expected}`);
  console.log(`scored unexplained: ${summary.scored_unexplained} (${summary.unexplained_rate_scored})`);
  console.log(`front matter policy entries: ${JSON.stringify(summary.front_matter_policy)}`);
  console.log('expected custom-layer differences (all):', JSON.stringify(summary.expected_custom_layer));
  console.log('skipped:', JSON.stringify(summary.skipped));
  console.log('\nby source:');
  for (const [src, s] of Object.entries(summary.by_source)) {
    console.log(`  ${src.padEnd(16)} total=${s.total} match=${s.match} expected=${s.expected} unexplained=${s.unexplained}`);
  }
  console.log('\ntop unexplained examples:');
  for (const ex of unexplainedExamples.slice(0, 10)) {
    console.log(`\n- ${ex.name} [${ex.source}] tags=${ex.tags.join(',')}`);
    console.log(`  input: ${short(ex.input, 220)}`);
    for (const d of ex.diffs.slice(0, 3)) {
      console.log(`  ${d.kind} ${d.path}${d.name ? ' @' + d.name : ''}`);
      console.log(`    oracle: ${short(d.a, 160)}`);
      console.log(`    comrak: ${short(d.b, 160)}`);
    }
  }
}

main();
