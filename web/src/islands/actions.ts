function closeMenu(button: HTMLElement, panel: HTMLElement): void {
  panel.hidden = true;
  button.setAttribute('aria-expanded', 'false');
}

export function mountTopbarActions(): void {
  const wrap = document.querySelector<HTMLElement>('.topbar-page-actions');
  if (!wrap) return;
  const button = wrap.querySelector<HTMLElement>('.action-menu-btn');
  const panel = wrap.querySelector<HTMLElement>('.action-panel');
  if (!button || !panel) return;

  function close(): void {
    closeMenu(button!, panel!);
  }

  button.addEventListener('click', (event) => {
    event.stopPropagation();
    panel!.hidden = !panel!.hidden;
    button!.setAttribute('aria-expanded', String(!panel!.hidden));
  });

  document.addEventListener('click', (event) => {
    if (!(event.target as Element | null)?.closest('.topbar-page-actions')) close();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') close();
  });

  panel.addEventListener('click', (event) => {
    const action = (event.target as Element | null)?.closest<HTMLElement>('.action');
    if (!action) return;
    if (action.id === 'export-png') return; // keep the menu open for the check icon
    if ((action.getAttribute('href') || '').includes('?download=1')) {
      window.setTimeout(close, 650);
      return;
    }
    close();
  });
}
