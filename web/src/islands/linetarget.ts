interface SourceRange {
  start: number;
  end: number;
}

const SOURCEPOS = /^(\d+):\d+-(\d+):\d+$/;
const BLOCK_SELECTOR = 'p, h1, h2, h3, h4, h5, h6, ul, ol, li, blockquote, pre, table, thead, tbody, tr, td, th, hr, div';

function parseRange(value: string | undefined): SourceRange | null {
  if (!value) return null;
  const match = SOURCEPOS.exec(value);
  if (!match) return null;
  const start = Number.parseInt(match[1], 10);
  const end = Number.parseInt(match[2], 10);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 1) return null;
  return { start, end };
}

export function mountLineTarget(): void {
  const article = document.querySelector<HTMLElement>('.markdown-body');
  if (!article) return;
  const root = article;
  let highlightTimer = 0;

  function clearHighlight(): void {
    window.clearTimeout(highlightTimer);
    root.querySelectorAll('.line-target').forEach((node) => node.classList.remove('line-target'));
  }

  function apply(): void {
    clearHighlight();
    const match = window.location.hash.match(/^#L(\d+)$/);
    if (!match) return;
    const line = Number.parseInt(match[1], 10);
    if (!Number.isFinite(line) || line < 1) return;

    let best: HTMLElement | null = null;
    let bestSpan = Number.POSITIVE_INFINITY;
    let next: { element: HTMLElement; start: number } | null = null;
    let previous: { element: HTMLElement; end: number } | null = null;

    for (const block of root.querySelectorAll<HTMLElement>(BLOCK_SELECTOR)) {
      if (!block.dataset.sourcepos) continue;
      const range = parseRange(block.dataset.sourcepos);
      if (!range) continue;
      if (line >= range.start && line <= range.end) {
        const span = range.end - range.start;
        if (span < bestSpan) {
          best = block;
          bestSpan = span;
        }
      } else if (range.start > line) {
        if (!next || range.start < next.start) next = { element: block, start: range.start };
      } else if (!previous || range.end > previous.end) {
        previous = { element: block, end: range.end };
      }
    }

    const target = best ?? next?.element ?? previous?.element;
    if (!target) return;
    target.classList.add('line-target');
    highlightTimer = window.setTimeout(() => target.classList.remove('line-target'), 2400);
    window.requestAnimationFrame(() => {
      target.scrollIntoView({ block: 'start', behavior: 'auto' });
    });
  }

  apply();
  window.addEventListener('hashchange', apply);
}
