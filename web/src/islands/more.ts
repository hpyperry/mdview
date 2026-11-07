function closeMenu(button: HTMLElement, panel: HTMLElement): void {
  panel.hidden = true;
  button.setAttribute('aria-expanded', 'false');
}

function mountMenu(wrap: HTMLElement, closers: Array<() => void>): void {
  const button = wrap.querySelector<HTMLElement>('.more-btn');
  const panel = wrap.querySelector<HTMLElement>('.more-panel');
  if (!button || !panel) return;

  function close(): void {
    closeMenu(button!, panel!);
  }
  closers.push(close);

  button.addEventListener('click', (event) => {
    event.stopPropagation();
    panel!.hidden = !panel!.hidden;
    button!.setAttribute('aria-expanded', String(!panel!.hidden));
  });

  panel.addEventListener('click', (event) => {
    const action = (event.target as Element | null)?.closest<HTMLElement>('.action, .dl');
    if (!action) return;
    if (action.id === 'export-png') return; // keep open for the completion check
    if ((action.getAttribute('href') || '').includes('?download=1')) {
      window.setTimeout(close, 650);
      return;
    }
    close();
  });
}

/// Mount every "more" popup on the page: the island head and the per-row
/// action menus in directory listings.
export function mountMore(): void {
  const closers: Array<() => void> = [];
  for (const wrap of document.querySelectorAll<HTMLElement>('.more-menu')) {
    mountMenu(wrap, closers);
  }
  if (closers.length === 0) return;

  document.addEventListener('click', (event) => {
    if (!(event.target as Element | null)?.closest('.more-menu')) {
      for (const close of closers) close();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') for (const close of closers) close();
  });
}
