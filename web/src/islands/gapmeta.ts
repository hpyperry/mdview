/// The metadata strip lives in the fixed-height gap between the topbar and the
/// main island. When it is wider than the viewport, let the whole page scroll
/// horizontally instead of wrapping or shrinking the strip.
export function mountGapMeta(): void {
  const bar = document.querySelector<HTMLElement>('.gap-meta');
  const inner = bar?.querySelector<HTMLElement>('.gap-meta-inner');
  const app = document.querySelector<HTMLElement>('.app');
  if (!bar || !inner || !app) return;

  function sync(): void {
    const style = getComputedStyle(app!);
    const padding = (Number.parseFloat(style.paddingLeft) || 0)
      + (Number.parseFloat(style.paddingRight) || 0);
    const needed = Math.ceil(inner!.scrollWidth + padding + 2);
    if (needed > window.innerWidth) {
      document.documentElement.style.minWidth = `${needed}px`;
    } else {
      document.documentElement.style.minWidth = '';
    }
  }

  sync();
  window.addEventListener('resize', sync);
  if ('ResizeObserver' in window) new ResizeObserver(sync).observe(inner!);
}
