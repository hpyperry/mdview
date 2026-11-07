function closeMenu(button: HTMLElement, panel: HTMLElement): void {
  panel.hidden = true;
  button.setAttribute('aria-expanded', 'false');
}

export function mountMore(): void {
  const wrap = document.querySelector<HTMLElement>('.more-menu');
  if (!wrap) return;
  const button = wrap.querySelector<HTMLElement>('.more-btn');
  const panel = wrap.querySelector<HTMLElement>('.more-panel');
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
    if (!(event.target as Element | null)?.closest('.more-menu')) close();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') close();
  });

  panel.addEventListener('click', (event) => {
    const action = (event.target as Element | null)?.closest<HTMLElement>('.action');
    if (!action) return;
    if (action.id === 'export-png') return; // keep open for the completion check
    if ((action.getAttribute('href') || '').includes('?download=1')) {
      window.setTimeout(close, 650);
      return;
    }
    close();
  });
}
