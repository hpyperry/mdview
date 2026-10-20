import { isNarrow } from '../utils';

function markNode(node: Node, needle: string): void {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.nodeValue || '';
    const lower = text.toLowerCase();
    let index = lower.indexOf(needle);
    if (index < 0) return;
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    while (index >= 0) {
      if (index > cursor) fragment.appendChild(document.createTextNode(text.slice(cursor, index)));
      const mark = document.createElement('mark');
      mark.textContent = text.slice(index, index + needle.length);
      fragment.appendChild(mark);
      cursor = index + needle.length;
      index = lower.indexOf(needle, cursor);
    }
    if (cursor < text.length) fragment.appendChild(document.createTextNode(text.slice(cursor)));
    node.parentNode?.replaceChild(fragment, node);
    return;
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return;
  const element = node as Element;
  if (element.tagName === 'MARK' || element.tagName === 'SCRIPT' || element.tagName === 'STYLE') return;
  Array.from(node.childNodes).forEach((child) => markNode(child, needle));
}

export function mountSearch(): void {
  const wrap = document.querySelector<HTMLElement>('.search-wrap');
  if (!wrap) return;
  const link = document.getElementById('search-open');
  const pop = document.getElementById('search-pop');
  const input = document.getElementById('search-input') as HTMLInputElement | null;
  const form = document.getElementById('search-form') as HTMLFormElement | null;
  if (!link || !pop || !input || !form) return;

  function setOpen(open: boolean): void {
    pop!.hidden = !open;
    link!.setAttribute('aria-expanded', String(open));
    if (open) window.setTimeout(() => input!.focus(), 0);
  }

  link.addEventListener('click', (event) => {
    if (isNarrow() || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    setOpen(pop.hidden);
  });

  document.addEventListener('keydown', (event) => {
    const target = event.target as HTMLElement | null;
    const typing = Boolean(target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable));
    if (event.key === 'Escape') setOpen(false);
    if (event.key === '/' && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault();
      if (isNarrow()) {
        window.location.assign('/search');
        return;
      }
      setOpen(true);
    }
  });

  document.addEventListener('click', (event) => {
    if (!(event.target as Element | null)?.closest('.search-wrap')) setOpen(false);
  });

  form.addEventListener('submit', () => setOpen(false));

  if (document.body.dataset.page === 'search') {
    const query = (new URLSearchParams(window.location.search).get('q') || '').trim().toLowerCase();
    if (!query) return;
    document.querySelectorAll<HTMLElement>('.hit-snippet').forEach((snippet) => markNode(snippet, query));
  }
}
