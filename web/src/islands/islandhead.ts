/**
 * The island head keeps actions on the left and file metadata on the right.
 * When the row no longer fits, the actions collapse into a "more" menu; if the
 * menu button still does not fit next to the metadata, the metadata is hidden.
 */
export function mountIslandHead(): void {
  const head = document.querySelector<HTMLElement>('.island-head');
  if (!head) return;
  const actions = head.querySelector<HTMLElement>('.island-actions');
  const more = head.querySelector<HTMLElement>('.island-more');
  const meta = head.querySelector<HTMLElement>('.island-meta');
  const panel = more?.querySelector<HTMLElement>('.page-actions');
  const button = more?.querySelector<HTMLElement>('.more-btn');
  if (!actions || !more || !meta || !panel) return;

  const inlineNodes = Array.from(actions.children);
  let collapsed = false;

  function expand(): void {
    if (!collapsed) return;
    for (const node of inlineNodes) actions!.appendChild(node);
    panel!.hidden = true;
    button?.setAttribute('aria-expanded', 'false');
    head!.classList.remove('is-collapsed');
    collapsed = false;
  }

  function collapse(): void {
    if (collapsed) return;
    for (const node of Array.from(actions!.children)) panel!.appendChild(node);
    head!.classList.add('is-collapsed');
    collapsed = true;
  }

  let frame = 0;
  function sync(): void {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      expand();
      head!.classList.remove('is-meta-hidden');
      const style = getComputedStyle(head!);
      const padding = (Number.parseFloat(style.paddingLeft) || 0)
        + (Number.parseFloat(style.paddingRight) || 0);
      const available = head!.clientWidth - padding;
      const gap = 16;
      if (actions!.scrollWidth + gap + meta!.offsetWidth > available) collapse();
      if (collapsed && more!.offsetWidth + gap + meta!.offsetWidth > available) {
        head!.classList.add('is-meta-hidden');
      }
    });
  }

  sync();
  window.addEventListener('resize', sync);
}
