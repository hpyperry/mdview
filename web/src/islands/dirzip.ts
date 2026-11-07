/**
 * Folder download: ask the server to build the zip first, keep a full-screen
 * overlay up while it is compressing, then hand the one-time token to the
 * browser so it can save the file without leaving the page.
 */
export function mountDirZip(): void {
  const overlay = document.getElementById('zip-overlay');
  const message = document.getElementById('zip-message');
  const close = document.getElementById('zip-close');
  if (!overlay || !message || !close) return;

  let busy = false;

  function show(text: string, closable: boolean): void {
    message!.textContent = text;
    close!.hidden = !closable;
    overlay!.hidden = false;
  }

  function hide(): void {
    overlay!.hidden = true;
    close!.hidden = true;
  }

  close.addEventListener('click', hide);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !close!.hidden) hide();
  });

  document.addEventListener('click', (event) => {
    const link = (event.target as Element | null)?.closest<HTMLAnchorElement>('a[data-zip]');
    if (!link || busy) return;
    event.preventDefault();
    busy = true;
    show('正在压缩文件夹…', false);

    const prepare = new URL(link.href, location.href);
    prepare.searchParams.set('prepare', '1');
    void fetch(prepare.toString(), { credentials: 'same-origin' })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok || typeof body.token !== 'string') {
          throw new Error(
            typeof body.error === 'string' ? body.error : '压缩失败，请稍后重试',
          );
        }
        const target = new URL(link.href, location.href);
        target.searchParams.set('token', body.token);
        hide();
        const anchor = document.createElement('a');
        anchor.href = target.toString();
        anchor.download = '';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      })
      .catch((error: unknown) => {
        show(
          error instanceof Error ? error.message : '压缩失败，请稍后重试',
          true,
        );
      })
      .finally(() => {
        busy = false;
      });
  });
}
