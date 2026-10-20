import { hasExplicitLanguage } from '../utils';

const CHUNK_MARGIN = 1500;
const LINE_HEIGHT = 21;
const MAX_HIGHLIGHT_CHARS = 256 * 1024;

export function mountSource(): void {
  const wrap = document.querySelector<HTMLElement>('.source-chunked');
  if (!wrap) return;
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
    gutter.replaceChildren(fragment);
    chunk.dataset.gutterReady = '1';
  }

  function ensureHighlight(chunk: HTMLElement): void {
    if (chunk.dataset.highlightReady === '1') return;
    chunk.dataset.highlightReady = '1';
    const code = chunk.querySelector<HTMLElement>('.code code');
    if (!window.hljs || !code || !hasExplicitLanguage(code)) return;
    if (code.textContent && code.textContent.length > MAX_HIGHLIGHT_CHARS) {
      code.dataset.highlightSkipped = '1';
      return;
    }
    try {
      window.hljs.highlightElement(code);
    } catch {
      // keep plain text
    }
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
    const viewport = window.innerHeight || 800;
    chunks.forEach((chunk) => {
      const rect = chunk.getBoundingClientRect();
      if (rect.bottom < -CHUNK_MARGIN || rect.top > viewport + CHUNK_MARGIN) return;
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
  window.addEventListener('resize', scheduleEnhance);
  enhanceVisible();
  window.addEventListener('hashchange', goHash);
  if (window.location.hash) goHash();
}
