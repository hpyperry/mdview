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
        window.location.assign('/search?__mdview=search');
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

    document.addEventListener('click', async (event) => {
      const link = (event.target as Element | null)?.closest<HTMLAnchorElement>('a.search-more');
      if (!link) return;
      event.preventDefault();
      if (link.classList.contains('is-loading')) return;
      const wrap = link.closest('.search-more-wrap');
      if (!wrap) return;
      const label = link.querySelector('span');
      link.classList.add('is-loading');
      link.setAttribute('aria-disabled', 'true');
      if (label) label.textContent = '正在加载…';
      try {
        const response = await fetch(link.href, { headers: { Accept: 'text/html' } });
        if (!response.ok) throw new Error(String(response.status));
        const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
        const body = document.querySelector('.page-body');
        const incoming = Array.from(doc.querySelectorAll('.result-group'));
        for (const group of incoming) {
          const imported = document.importNode(group, true);
          body?.insertBefore(imported, wrap);
          imported.querySelectorAll<HTMLElement>('.hit-snippet').forEach((snippet) => markNode(snippet, query));
        }
        const groups = document.querySelectorAll('.result-group').length;
        let hits = 0;
        document.querySelectorAll('.result-group .result-head .badge:last-child').forEach((badge) => {
          const match = /(\d+)/.exec(badge.textContent || '');
          if (match) hits += Number(match[1]);
        });
        const badges = document.querySelectorAll('.search-head .page-meta .badge');
        if (badges[0]) badges[0].textContent = `${groups} 个文件`;
        if (badges[1]) badges[1].textContent = `${hits} 条结果`;
        const next = doc.querySelector('.search-more-wrap');
        if (next) wrap.replaceWith(document.importNode(next, true));
        else wrap.remove();
      } catch {
        if (label) label.textContent = '加载失败，重试';
        link.classList.remove('is-loading');
        link.removeAttribute('aria-disabled');
      }
    });
  }
}
