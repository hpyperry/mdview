import { copyText, showToast } from '../utils';
import { saveReturnTarget } from '../return-position';

/**
 * File tools in the island head: copy the whole file to the clipboard and
 * search inside the rendered document (count, previous/next, Esc to close).
 */

function contentRoot(): HTMLElement | null {
  return (
    document.querySelector<HTMLElement>('.markdown-body')
    || document.querySelector<HTMLElement>('.source-wrap')
  );
}

function ignoredNode(node: Text): boolean {
  const el = node.parentElement;
  if (!el) return true;
  return !!el.closest(
    '.gutter, .code-bar, .copy-btn, .find-panel, .sr-only, script, style',
  );
}

function clearMarks(root: HTMLElement): void {
  for (const mark of Array.from(root.querySelectorAll('mark.find-hit'))) {
    const parent = mark.parentNode;
    if (!parent) continue;
    parent.replaceChild(document.createTextNode(mark.textContent || ''), mark);
    parent.normalize();
  }
}

function mountCopy(button: HTMLElement | null): void {
  if (!button) return;
  let timer = 0;
  button.addEventListener('click', () => {
    void (async () => {
      try {
        const res = await fetch(`${location.pathname}?download=1`, {
          credentials: 'same-origin',
        });
        if (!res.ok) throw new Error(`status ${res.status}`);
        await copyText(await res.text());
        button.classList.add('is-done');
        button.dataset.tip = '已复制';
      } catch {
        button.dataset.tip = '复制失败';
        showToast('复制失败：请允许剪贴板权限，或使用下载');
      }
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        button.classList.remove('is-done');
        button.dataset.tip = '复制';
      }, 1500);
    })();
  });
}

function mountFind(): void {
  const root = contentRoot();
  const panel = document.getElementById('find-panel');
  const input = document.getElementById('find-input') as HTMLInputElement | null;
  const count = document.getElementById('find-count');
  const openButton = document.getElementById('find-open');
  if (!root || !panel || !input || !count) return;

  let marks: HTMLElement[] = [];
  let active = -1;
  let timer = 0;

  function paintCount(): void {
    count!.textContent = marks.length
      ? `${active + 1}/${marks.length}`
      : '0/0';
  }

  function activate(next: number): void {
    if (marks.length === 0) {
      active = -1;
      paintCount();
      return;
    }
    if (active >= 0 && marks[active]) marks[active].classList.remove('is-active');
    active = (next + marks.length) % marks.length;
    const mark = marks[active];
    mark.classList.add('is-active');
    paintCount();
    mark.scrollIntoView({ block: 'center', inline: 'nearest' });
  }

  function run(): void {
    clearMarks(root!);
    marks = [];
    active = -1;
    const query = input!.value.trim();
    if (!query) {
      paintCount();
      return;
    }
    const needle = query.toLowerCase();
    const nodes: Text[] = [];
    const walker = document.createTreeWalker(root!, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode as Text;
      const value = node.nodeValue || '';
      if (!value.toLowerCase().includes(needle) || ignoredNode(node)) continue;
      nodes.push(node);
    }
    const limit = 2000;
    let total = 0;
    for (const node of nodes) {
      if (total >= limit) break;
      const value = node.nodeValue || '';
      const lower = value.toLowerCase();
      const offsets: number[] = [];
      let from = 0;
      while (offsets.length < limit) {
        const index = lower.indexOf(needle, from);
        if (index < 0) break;
        offsets.push(index);
        from = index + needle.length;
      }
      const allowed = Math.min(offsets.length, limit - total);
      for (let i = allowed - 1; i >= 0; i--) {
        const scheme = document.createRange();
        scheme.setStart(node, offsets[i]);
        scheme.setEnd(node, offsets[i] + needle.length);
        const mark = document.createElement('mark');
        mark.className = 'find-hit';
        scheme.surroundContents(mark);
      }
      total += allowed;
    }
    marks = Array.from(root!.querySelectorAll<HTMLElement>('mark.find-hit'));
    if (marks.length) activate(0);
    else paintCount();
  }

  function open(): void {
    panel!.hidden = false;
    input!.focus();
    input!.select();
    if (input!.value) run();
  }

  function close(): void {
    panel!.hidden = true;
    clearMarks(root!);
    marks = [];
    active = -1;
    paintCount();
  }

  openButton?.addEventListener('click', () => {
    if (panel!.hidden) open();
    else {
      input!.focus();
      input!.select();
    }
  });
  panel.querySelector('.find-close')?.addEventListener('click', close);
  panel.querySelector('.find-prev')?.addEventListener('click', () => activate(active - 1));
  panel.querySelector('.find-next')?.addEventListener('click', () => activate(active + 1));

  input.addEventListener('input', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(run, 120);
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      activate(active + (event.shiftKey ? -1 : 1));
    } else if (event.key === 'Escape') {
      event.preventDefault();
      close();
    }
  });
  panel.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') close();
  });

  paintCount();
}

/**
 * Remember the current file when leaving through the breadcrumb, so the
 * directory page can scroll back to its row without putting the file name in
 * the URL.
 */
function mountCrumbReturn(): void {
  const links = document.querySelectorAll<HTMLAnchorElement>('.gap-crumb .crumbs a[href]');
  const parent = links[links.length - 1];
  if (!parent) return;
  parent.addEventListener('click', () => {
    const segment = window.location.pathname.split('/').pop() || '';
    let file = '';
    try {
      file = decodeURIComponent(segment);
    } catch {
      return;
    }
    if (!file) return;
    let dir = '';
    try {
      dir = new URL(parent.href, window.location.href).pathname;
    } catch {
      return;
    }
    saveReturnTarget({ dir, file });
  });
}

export function mountFileTools(): void {
  mountCrumbReturn();
  mountCopy(document.getElementById('copy-file'));
  mountFind();
}
