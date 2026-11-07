import { hasExplicitLanguage, languageOf } from '../utils';
import { highlightInWorker } from '../worker-highlight';

const CHUNK_MARGIN = 1500;
const LINE_HEIGHT = 21;
const MAX_HIGHLIGHT_CHARS = 256 * 1024;

const HIGHLIGHT_QUEUE: HTMLElement[] = [];
let highlightScheduled = false;

function highlightLarge(code: HTMLElement): void {
  if (!hasExplicitLanguage(code)) {
    code.dataset.highlightSkipped = '1';
    return;
  }
  const language = languageOf(code);
  void highlightInWorker(code.textContent || '', language).then((html) => {
    if (html == null) {
      code.dataset.highlightSkipped = '1';
      return;
    }
    code.innerHTML = html;
    code.classList.add('hljs');
  });
}

function highlightSmallSource(source: HTMLElement): void {
  const code = source.querySelector<HTMLElement>('.source .code code');
  if (!code || !hasExplicitLanguage(code)) return;
  if (code.textContent && code.textContent.length > MAX_HIGHLIGHT_CHARS) {
    highlightLarge(code);
    return;
  }
  if (!window.hljs) return;
  try {
    window.hljs.highlightElement(code);
  } catch {
    // keep plain text
  }
}

export function mountSource(): void {
  const source = document.querySelector<HTMLElement>('.source-wrap');
  if (!source) return;
  const card = document.querySelector<HTMLElement>('.content-card');
  const scrollRoot = card && getComputedStyle(card).overflowY === 'auto' ? card : null;
  const wrap = source.classList.contains('source-chunked')
    ? source
    : source.querySelector<HTMLElement>('.source-chunked');
  if (!wrap) {
    highlightSmallSource(source);
    return;
  }
  const chunks = Array.from(wrap.querySelectorAll<HTMLElement>('.source-chunk'));
  if (!chunks.length) return;
  const chunkSize = Number.parseInt(wrap.getAttribute('data-chunk-lines') || '500', 10) || 500;
  const total = Number.parseInt(wrap.getAttribute('data-source-lines') || '0', 10) || 0;

  function startOf(chunk: HTMLElement): number {
    return Number.parseInt(chunk.getAttribute('data-start') || '1', 10) || 1;
  }

  function ensureGutter(chunk: HTMLElement): void {
    if (chunk.dataset.gutterReady === '1') return;
    const start = startOf(chunk);
    const rows = Number.parseInt(chunk.getAttribute('data-rows') || '0', 10) || 0;
    const gutter = chunk.querySelector<HTMLElement>('.gutter');
    if (!gutter || !rows) return;
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < rows; i += 1) {
      const line = start + i;
      const anchor = document.createElement('a');
      anchor.id = `L${line}`;
      anchor.href = `#L${line}`;
      anchor.textContent = String(line);
      fragment.appendChild(anchor);
    }
    if (typeof gutter.replaceChildren === 'function') {
      gutter.replaceChildren(fragment);
    } else {
      gutter.textContent = '';
      gutter.appendChild(fragment);
    }
    chunk.dataset.gutterReady = '1';
  }

  function nearViewport(chunk: HTMLElement): boolean {
    const box = scrollRoot
      ? scrollRoot.getBoundingClientRect()
      : { top: 0, bottom: window.innerHeight || 800 };
    const rect = chunk.getBoundingClientRect();
    return !(rect.bottom < box.top - CHUNK_MARGIN || rect.top > box.bottom + CHUNK_MARGIN);
  }

  function highlightChunk(chunk: HTMLElement): void {
    delete chunk.dataset.highlightQueued;
    if (chunk.dataset.highlightReady === '1') return;
    if (!nearViewport(chunk)) return;
    chunk.dataset.highlightReady = '1';
    const code = chunk.querySelector<HTMLElement>('.code code');
    if (!code || !hasExplicitLanguage(code)) return;
    if (code.textContent && code.textContent.length > MAX_HIGHLIGHT_CHARS) {
      highlightLarge(code);
      return;
    }
    if (!window.hljs) return;
    try {
      window.hljs.highlightElement(code);
    } catch {
      // keep plain text
    }
  }

  function scheduleHighlight(): void {
    if (highlightScheduled) return;
    highlightScheduled = true;
    const run = (): void => {
      highlightScheduled = false;
      const chunk = HIGHLIGHT_QUEUE.shift();
      if (!chunk) return;
      highlightChunk(chunk);
      if (HIGHLIGHT_QUEUE.length > 0) scheduleHighlight();
    };
    const idle = (window as Window & {
      requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
    }).requestIdleCallback;
    if (idle) idle(run, { timeout: 250 });
    else window.setTimeout(run, 16);
  }

  function ensureHighlight(chunk: HTMLElement): void {
    if (chunk.dataset.highlightReady === '1' || chunk.dataset.highlightQueued === '1') return;
    const code = chunk.querySelector<HTMLElement>('.code code');
    if (!code || !hasExplicitLanguage(code)) {
      chunk.dataset.highlightReady = '1';
      return;
    }
    if (code.textContent && code.textContent.length > MAX_HIGHLIGHT_CHARS) {
      chunk.dataset.highlightReady = '1';
      highlightLarge(code);
      return;
    }
    if (!window.hljs) {
      chunk.dataset.highlightReady = '1';
      return;
    }
    chunk.dataset.highlightQueued = '1';
    HIGHLIGHT_QUEUE.push(chunk);
    scheduleHighlight();
  }

  let targetAnchor: HTMLElement | null = null;
  let targetOverlay: HTMLElement | null = null;

  function clearTarget(): void {
    targetAnchor?.classList.remove('target');
    targetAnchor = null;
    targetOverlay?.parentNode?.removeChild(targetOverlay);
    targetOverlay = null;
  }

  function goHash(): void {
    const match = window.location.hash.match(/^#L(\d+)$/);
    if (!match) {
      clearTarget();
      return;
    }
    const line = Number.parseInt(match[1], 10);
    const chunk = line > 0 ? chunks[Math.floor((line - 1) / chunkSize)] : null;
    if (!line || (total && line > total) || !chunk) {
      clearTarget();
      return;
    }
    clearTarget();
    ensureGutter(chunk);
    const anchor = document.getElementById(`L${line}`);
    if (!anchor) return;
    const rows = Number.parseInt(chunk.getAttribute('data-rows') || '0', 10) || 0;
    const offset = line - startOf(chunk);
    if (offset >= 0 && offset < rows) {
      const overlay = document.createElement('div');
      overlay.className = 'source-target-line';
      overlay.style.top = `${14 + offset * LINE_HEIGHT}px`;
      chunk.appendChild(overlay);
      targetOverlay = overlay;
    }
    anchor.classList.add('target');
    targetAnchor = anchor;
    window.requestAnimationFrame(() => anchor.scrollIntoView({ block: 'center' }));
  }

  function enhanceVisible(): void {
    chunks.forEach((chunk) => {
      if (!nearViewport(chunk)) return;
      ensureGutter(chunk);
      ensureHighlight(chunk);
    });
  }

  let scheduled = false;
  function scheduleEnhance(): void {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      enhanceVisible();
    }, 80);
  }

  window.addEventListener('scroll', scheduleEnhance, { passive: true });
  scrollRoot?.addEventListener('scroll', scheduleEnhance, { passive: true });
  window.addEventListener('resize', scheduleEnhance);
  enhanceVisible();
  window.addEventListener('hashchange', goHash);
  if (window.location.hash) goHash();
}
